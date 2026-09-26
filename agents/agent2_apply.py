"""에이전트② 분류 결과를 data/prod/content_type*.json으로 만든다.

거제(48310, 기본 지역)는 RESULTS(수동 분류, "리센느 원이" 사례로 다른 문서에도
구체 인용된 기록)를 그대로 동결해서 쓴다 — 다시 돌리면 다른 영상 집합이 잡혀
기존 서술이 깨진다.

나머지 5개 사례 지역(여수·울릉·속초·영월·인제)은 agents/prompts/agent2_content_type.md를
agents/llm_client.py로 실제 호출해 분류한다. 원래 하드코딩 RESULTS_OTHER dict였던
부분을 이걸로 교체했다(프로젝트가 "현재 최대 기술부채"로 명시해뒀던 부분 —
docs/meeting-notes/UI/프론트구조_기능조사_및_에이전트연동계획.md 참고). agent3_match.py/
agent5_briefing.py와 같은 패턴: LLM은 판정(유형·신뢰도·근거·언급지점·감성·zone_signal)만
하고, video_id/title/channel/published_at/view_count 등 정적 필드는 코드가 원본에서
그대로 채운다(D-08).

입력은 DB 스냅샷(youtube_case.csv, description/tags 없음)이 아니라 collection/
youtube_collect.py로 재수집한 원본을 쓴다 — DB의 youtube_video 테이블 자체에
description/tags 컬럼이 없어서(팀 공유용 기록: docs/j2nii_진행상황.md §23),
프롬프트가 요구하는 입력(제목·설명·태그)을 DB로는 채울 수 없다.

사용법:
    uv run python collection/youtube_collect.py --region 여수   # 지역별 재수집, 필요시
    uv run python agents/agent2_apply.py --provider upstage
    uv run python agents/agent2_apply.py --dump-prompt          # LLM 호출 없이 요청만 저장
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "agents"))

from validate_data import validate_payload  # noqa: E402
from common import load_prompt  # noqa: E402
from llm_client import LLMError, complete_json  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

RAW_DIR = ROOT / "data" / "raw" / "youtube"
PROD = ROOT / "data" / "prod"
RUNS_DIR = ROOT / "agents" / "runs"
OUT = PROD / "content_type.json"
DEFAULT_REGION = "48310"
PROMPT_PATH = ROOT / "agents" / "prompts" / "agent2_content_type.md"

PROMPT_VERSION = "agent2_content_type_v1.1"
MODEL = "claude-opus-5"
# RESULTS는 API 호출이 아니라 Claude Code 세션 안에서 프롬프트를 적용해 얻은 판정이다.
# (Opus 5는 temperature 파라미터를 받지 않으므로 temperature 기록도 두지 않는다)
PROVIDER = "Claude Code 세션(API 미경유)"
CONFIDENCE_FLOOR = 0.6
# RESULTS가 판정한 수집본. 최신 파일을 자동으로 고르면 다른 수집본(예: 220일치)과
# 조인되어 결과가 조용히 바뀌므로 고정한다. 재분류할 때 함께 바꾼다.
RAW_FILE = "거제_20260912_1320.json"

CONTENT_TYPES = [
    "예능·방송 노출형", "맛집형", "포토스팟형", "체험·액티비티형", "축제·이벤트형",
    "자연경관형", "드라마·영화촬영지형", "코스·일정형", "관광무관",
]

# 재수집한 원본 파일(agents/prompts/agent2_content_type.md로 실제 LLM 분류할 지역).
# RAW_FILE과 같은 이유로 고정한다 — 재수집이 매번 다른 시각의 영상 집합을 낼 수 있다.
OTHER_RAW_FILES = {
    "12130": ("여수시", "여수_20260924_0118.json"),
    "47940": ("울릉군", "울릉_20260924_0118.json"),
    "51210": ("속초시", "속초_20260924_0118.json"),
    "51750": ("영월군", "영월_20260924_0119.json"),
    "51810": ("인제군", "인제_20260924_0119.json"),
}
TOP_N_OTHER = 50

# 수요 쏠림/이탈 신호 (설계결정 D-02).
# 관광무관으로 분류된 영상도 신호는 가질 수 있다 — 집계에서 빠지는 것과
# 신호를 버리는 것은 다르다. 데드존이 지목한 지점은 분산 정책의 목적지 후보다.
ZONE_SIGNALS = {
    "RPIcHaAlQJM": "핫존",   # 원이가 떡상시킨 거제 포차 레전드 근황
    "AieL-kFdglY": "핫존",   # 올 여름 최고 떡상 관광지, 거제 덕포
    "pOlOp2SXdTE": "핫존",   # 거제 바가지, 확답 듣고 왔습니다
    "tkqICH01Zjw": "핫존",   # 발길이 끊이지 않는 거제 맛집 (KBS)
    "S-oHqdG_qj4": "핫존",   # 거제시 물가대책·바가지 신고센터 운영
    "NzrnKlFVKu0": "데드존",  # 해금강 마을, 호텔도 횟집도 파리만 날린다
    "JHoYYHEk5D8": "데드존",  # 거가대교가 바꾼 거제도의 몰락
}

# video_id: (유형, 신뢰도, 근거, 언급 지점, 감성)
RESULTS = {
    "_Z9j2jILw4k": ("관광무관", 0.71, "사투리 강의 형식의 인물 콘텐츠로 방문할 장소에 대한 정보가 전혀 없음", [], "중립"),
    "_bYHFtOe_YA": ("예능·방송 노출형", 0.66, "인물 출연 장면 편집 쇼츠로 해시태그가 인물명 중심(#리센느원이 #미나미)", [], "긍정"),
    "OrCOflk2QmQ": ("예능·방송 노출형", 0.95, "제목 '갸루와 거제에 왔습니다'로 인물의 방문 자체가 콘텐츠이며 이후 파생 콘텐츠의 기점", [], "긍정"),
    "SF29doLuBfc": ("예능·방송 노출형", 0.95, "'갸루와 거제 2편'으로 1편에 이은 인물 방문 콘텐츠", [], "긍정"),
    "zn948OnPonE": ("예능·방송 노출형", 0.88, "태그에 '#예능 #아이돌'이 명시되고 인물 조합('원이x미나미')이 제목 중심", [], "긍정"),
    "_GKSineBozo": ("예능·방송 노출형", 0.92, "'거제의 딸 원이가 인정한 거제 핫플 풀코스'로 인물 추천이 코스 선정 기준", [], "긍정"),
    "eqDd8JEg4Mk": ("체험·액티비티형", 0.86, "해시태그가 '#스노쿨링 #프리다이빙'으로 참여형 활동이 목적", ["구조라해수욕장", "윤돌섬"], "긍정"),
    "yIowLN_Jkok": ("예능·방송 노출형", 0.84, "'리센느 거제도편에 댓글달았다가 여행가게 된 팬' — 콘텐츠 시청이 실제 방문으로 이어진 사례를 콘텐츠 자체가 서술", [], "긍정"),
    "cm3U4TWCPf4": ("예능·방송 노출형", 0.83, "'거제 현지인 원이가 강력 추천하는 곳'으로 장소 선정 근거가 인물 추천", ["외도 보타니아"], "긍정"),
    "Gdez_IKDK-I": ("예능·방송 노출형", 0.90, "아티스트 공식 채널의 '리센느의 방방곡곡 in 거제' 자체 콘텐츠", [], "긍정"),
    "5aQynbQhwJU": ("예능·방송 노출형", 0.72, "'리센느야 고마워'로 인물에 대한 반응이 제목 중심이며 거제여행 태그가 병기됨", [], "긍정"),
    "Lkby3ZUBmQ8": ("관광무관", 0.68, "'거제 영상은 어째서 영화적인가' — 영상 연출 비평으로 방문 정보가 아님", [], "중립"),
    "RPIcHaAlQJM": ("예능·방송 노출형", 0.89, "'원이가 떡상시킨 거제 포차 레전드 근황' — 인물 언급 후 특정 점포에 수요가 몰린 결과를 다룸", ["모래성분식포차"], "긍정"),
    "aFWkJDaTCIk": ("예능·방송 노출형", 0.85, "예능 채널(문명특급)의 '거제 가기 전에 꼭 봐야 할 영상', 태그에 '문명특급 리센느'", [], "긍정"),
    "oNNo9Qu8QeQ": ("예능·방송 노출형", 0.79, "맛집 소재이나 '덕연이 딸' 등 인물 연계가 방문 동기로 제시됨", [], "긍정"),
    "YV9Q9fBNzLs": ("예능·방송 노출형", 0.87, "'리센느 원이픽 거제 코스'로 인물 추천 코스를 그대로 따라가는 구성", ["외도 보타니아", "해금강 십자동굴", "와현해수욕장"], "긍정"),
    "ESfiVMm3Nh8": ("자연경관형", 0.61, "거제식물원 정글돔 등 명소의 규모·특성을 지식 형식으로 소개", ["거제식물원 정글돔"], "긍정"),
    "Exb6lRaPg9A": ("체험·액티비티형", 0.74, "'#낚시 #트레킹 #1박3식'으로 숙박 기반 참여형 활동이 중심", ["이수도"], "긍정"),
    "ePNfrlXrxd8": ("예능·방송 노출형", 0.86, "'거제도 여행 중에 리센느 만난' — 인물 조우가 콘텐츠의 사건", [], "긍정"),
    "AieL-kFdglY": ("예능·방송 노출형", 0.81, "'올 여름 최고 떡상 관광지, 거제 덕포 — 관광 효과 직접 확인'으로 인물 열풍의 방문 효과를 취재", ["덕포해수욕장"], "긍정"),
    "2xfEsHprjHE": ("관광무관", 0.80, "부산 영도 여행 콘텐츠로 거제와 무관하며 검색어 일치로 수집됨", [], "중립"),
    "Z6PcJkDiBec": ("자연경관형", 0.70, "수국 군락지 소개로 자연 경관 자체가 방문 목적", [], "긍정"),
    "2H6lk2dAKp8": ("예능·방송 노출형", 0.80, "'리센느 추천 갈비탕집'으로 점포 선택 근거가 인물 추천", [], "긍정"),
    "44HJcCNCYcw": ("코스·일정형", 0.72, "'거제 숙소부터 맛집, 카페, 둘러볼 곳까지 딱 정리'로 지역 전반의 방문 계획 수립이 목적", [], "긍정"),
    "RDzPGWOnaOA": ("예능·방송 노출형", 0.84, "'리센느가 끌어올린 요즘 대세 거제도'로 인물 열풍을 방문 배경으로 명시", ["칠천도"], "긍정"),
    "S-oHqdG_qj4": ("축제·이벤트형", 0.62, "해수욕장 16개소 개장과 운영기간(7.4~8.23)이 명시된 지자체 안내", ["거제시 해수욕장"], "긍정"),
    "pOlOp2SXdTE": ("예능·방송 노출형", 0.66, "'거제 바가지 확답 듣고 왔습니다' — 인물 열풍에 따른 물가 우려를 취재한 후속 보도", [], "부정"),
    "y79rrmFFTr8": ("관광무관", 0.82, "통영 중앙시장 콘텐츠로 거제와 무관", [], "중립"),
    "tkqICH01Zjw": ("예능·방송 노출형", 0.90, "지상파 생방송에서 '인기 타고 발길이 끊이지 않는 거제 맛집'으로 방문 급증을 보도", [], "긍정"),
    "Z7dfT9EWCXA": ("체험·액티비티형", 0.70, "'1박 3식' 민박과 트레킹 루트가 중심이며 '1일 방문객 1000명'이 제목에 제시됨", ["이수도"], "긍정"),
    "_yeeXFuCC3A": ("맛집형", 0.74, "다큐멘터리에서 오징어·왕우럭조개 등 지역 음식과 식당을 다룸", [], "긍정"),
    "zFVFEAOK1r0": ("맛집형", 0.88, "'거제도 10끼'로 식당 순회가 콘텐츠 전체이며 태그가 '거제맛집, 거제노포'", [], "긍정"),
    "i5jt55wKk18": ("예능·방송 노출형", 0.72, "인물 출연분 편집 콘텐츠로 '#리센느 #원이 #미나미'가 설명 전부", [], "긍정"),
    "NzrnKlFVKu0": ("관광무관", 0.60, "해금강 마을의 상권 침체 르포로 방문 수요를 유발하는 콘텐츠가 아님. 다만 동일 지역 내 데드존 신호로 별도 가치가 있음", ["해금강마을"], "부정"),
    "YWPB7Xn7nbY": ("예능·방송 노출형", 0.82, "'거제 토박이 리센느 원이 추천 거제맛집 6곳'으로 인물 추천이 선정 기준", ["매미성"], "긍정"),
    "LYdnTjn3bKQ": ("예능·방송 노출형", 0.78, "'리센느 원이가 극찬한 맛집'으로 점포 선택 근거가 인물", [], "긍정"),
    "77sn4xtuI8Q": ("관광무관", 0.85, "김해 진영·장유 맛집 콘텐츠로 거제와 무관", [], "중립"),
    "9VPOIBsLEsU": ("맛집형", 0.86, "산오징어회·오징어통찜 등 메뉴와 가격(15만원)을 구체적으로 소개", ["소노캄 거제 인근"], "긍정"),
    "aUO8cgJGpTk": ("예능·방송 노출형", 0.85, "'리센느 원이의 추천은 계속된다'로 인물 추천 코스를 이어가는 시리즈 2편", ["망치몽돌해수욕장", "지세포진성", "흥남철수기념공원", "매미성"], "긍정"),
    "oYy3GzigOxo": ("코스·일정형", 0.88, "'현지인이 완벽하게 짜준 1박 2일 거제여행 코스'로 일정 단위가 제목에 명시되고 이동 순서로 구성됨", ["신선대"], "긍정"),
    "Q6uAbGVC6tI": ("관광무관", 0.84, "하동·사천 패키지 여행 콘텐츠로 거제와 무관", [], "중립"),
    "nXo6TemgLPU": ("코스·일정형", 0.74, "'1박3식 패키지'로 숙박·식사·요트·케이블카가 정해진 일정으로 묶여 제시됨", [], "긍정"),
    "-PGvCaBvamo": ("예능·방송 노출형", 0.83, "태그에 '순대리아, 거제현지인맛집'과 인물명이 함께 있고 인물 추천이 방문 근거", ["순대리아"], "긍정"),
    "bzDv0XfRMVU": ("자연경관형", 0.72, "지세포진성 꽃동산·칠천도·씨릉섬 출렁다리 등 경관 자원을 지자체가 소개", ["지세포진성 꽃동산", "칠천도", "씨릉섬 출렁다리"], "긍정"),
    "Ko1D9hdjgmM": ("관광무관", 0.85, "통영 숙소 소개 콘텐츠로 거제와 무관", [], "중립"),
    "RRgTIg2-qzQ": ("자연경관형", 0.68, "수국·몽돌해수욕장·바람의 언덕 등 경관 명소 나열", ["바람의 언덕", "몽돌해수욕장"], "긍정"),
    "JHoYYHEk5D8": ("관광무관", 0.72, "거가대교 이후 지역경제 변화를 다룬 분석 콘텐츠로 방문 안내가 아님. 체류 없는 통과형 관광의 문제를 지적", [], "부정"),
    "JXP_9qsC0o0": ("축제·이벤트형", 0.66, "6월 여행지 목록에 '거제 수국축제'가 기간 행사로 포함됨", ["거제 수국축제"], "긍정"),
    "qDnEXDIisaU": ("축제·이벤트형", 0.68, "저구항수국축제·지세포진성꽃동산 등 기간 한정 꽃 행사 중심", ["저구항", "지세포진성 꽃동산"], "긍정"),
    "jjzEbmpDSqg": ("맛집형", 0.84, "수제버거 단일 점포의 맛과 구성을 상세히 평가", [], "긍정"),
    "BKZZX417Ej0": ("축제·이벤트형", 0.52, "6월 여행지 목록으로 거제 관련 비중이 불분명", [], "긍정"),
    "8SW1pTTBLXE": ("예능·방송 노출형", 0.91, "설명에 '리센느 거제 영상 보고 다녀온 거제 당일치기'로 콘텐츠 시청이 방문 동기임을 직접 진술", ["모래성분식포차", "덕포해수욕장", "w181카페"], "긍정"),
    "xQTZtFT4NQE": ("예능·방송 노출형", 0.85, "'리센느 원이 치킨집'을 코스로 명시하고 '요즘 핫한 리센느'를 방문 배경으로 언급", ["원이 치킨집"], "긍정"),
    "9Mrta-DFiq0": ("예능·방송 노출형", 0.87, "'덕연이 딸 시작된 전설의 식당'으로 인물 서사가 점포 방문의 이유", ["모래성분식포차"], "긍정"),
    "myWJZGKPagY": ("예능·방송 노출형", 0.86, "'리센느 원이 추천 거제맛집 5곳'으로 점포 목록이 인물 추천에서 도출됨", ["금농갈비", "순대리아"], "긍정"),
    "Jb6TdlSt4HY": ("예능·방송 노출형", 0.88, "'리센느 원이 거제 단골 맛집 급습'으로 인물의 단골 여부가 선정 기준", ["순대리아"], "긍정"),
    "ZgsYyEiP4s0": ("맛집형", 0.87, "타임라인에 점포 7곳이 시간대별로 나열되어 식당 순회가 콘텐츠 전체", ["우리들회식당", "바다식당", "버거섬", "도시농부밥상", "화간짬뽕", "명가순두부", "인생미역"], "긍정"),
    "pNPqIWMuoHM": ("예능·방송 노출형", 0.85, "'리센느 원이 맛집 다 뿌시기'로 인물 추천 목록을 순회하는 구성", ["금농갈비", "매미성", "외도 보타니아", "순대리아", "옥포밀면"], "긍정"),
    "zKlpyWBCM68": ("예능·방송 노출형", 0.86, "'리센느 원이의 고향으로 한참 뜨고 있는 거제'를 방문 이유로 서술", ["순대리아", "금농갈비", "매미성"], "긍정"),
}


def summarize(items: list[dict]) -> tuple[list[dict], list[dict]]:
    counted = [i for i in items if i["confidence"] >= CONFIDENCE_FLOOR and i["content_type"] != "관광무관"]
    by_type: dict[str, list] = {}
    for item in counted:
        by_type.setdefault(item["content_type"], []).append(item)
    summary = [
        {
            "content_type": ctype,
            "count": len(group),
            "ratio": round(len(group) / len(counted), 4),
            "total_views": sum(i["view_count"] for i in group),
        }
        for ctype, group in sorted(by_type.items(), key=lambda kv: -sum(i["view_count"] for i in kv[1]))
    ]
    return counted, summary


def zone_signals(items: list[dict]) -> dict:
    return {
        "핫존": sum(1 for i in items if i.get("zone_signal") == "핫존"),
        "데드존": sum(1 for i in items if i.get("zone_signal") == "데드존"),
        "데드존_지점": sorted({
            poi for i in items if i.get("zone_signal") == "데드존" for poi in i["poi_mentioned"]
        }),
    }


def build_geoje() -> None:
    raw_path = RAW_DIR / RAW_FILE
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    items = []
    for video in raw["videos"]:
        verdict = RESULTS.get(video["video_id"])
        if verdict is None:
            print(f"  [건너뜀] 분류 결과 없음: {video['video_id']} {video['title'][:30]}")
            continue
        content_type, confidence, evidence, pois, sentiment = verdict
        item = {
            "video_id": video["video_id"],
            "title": video["title"],
            "channel": video["channel"],
            "published_at": video["published_at"],
            "view_count": video["view_count"],
            "like_count": video["like_count"],
            "comment_count": video["comment_count"],
            "content_type": content_type,
            "confidence": confidence,
            "evidence": evidence,
            "poi_mentioned": pois,
            "sentiment": sentiment,
        }
        if video["video_id"] in ZONE_SIGNALS:
            item["zone_signal"] = ZONE_SIGNALS[video["video_id"]]
        items.append(item)

    counted, summary = summarize(items)

    payload = {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "YouTube Data API v3",
                "provider": "Google",
                "retrieved_at": raw["collected_at"][:10],
                "note": f"검색어 {', '.join(raw['queries'])} / 최근 {raw['period_days']}일 업로드분 {raw['count']}건",
            }
        ],
        "period": {
            "start": min(i["published_at"] for i in items),
            "end": max(i["published_at"] for i in items),
            "granularity": "일",
        },
        "caveat": [
            "검색 결과 상위 영상만 수집해 소규모 채널 콘텐츠가 과소 대표된다.",
            "조회수는 수집 시점 기준이며 이후 계속 변동한다.",
            "신뢰도 0.6 미만과 '관광무관'은 집계에서 제외했다. 제외 건수는 unclassified_count로 표시한다.",
            "zone_signal은 집계 제외 항목에도 부여된다. 데드존이 지목한 지점은 분산 정책의 목적지 후보로 쓰인다.",
            "분류는 제목·설명·태그 텍스트만으로 수행했으며 영상 내용을 시청해 검증하지 않았다.",
        ],
        "data": {
            "region": {"code": "48310", "name": "거제시"},
            "model": {"name": MODEL, "provider": PROVIDER, "prompt_version": PROMPT_VERSION},
            "items": items,
            "summary": summary,
            "unclassified_count": len(items) - len(counted),
            "zone_signals": zone_signals(items),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"입력: {raw_path.relative_to(ROOT)} ({len(raw['videos'])}건)")
    print(f"출력: {OUT.relative_to(ROOT)}\n")
    print(f"집계 대상 {len(counted)}건 / 제외 {len(items) - len(counted)}건\n")
    for row in summary:
        print(f"  {row['content_type']:<16} {row['count']:>3}건  조회수 {row['total_views']:>12,}  비중 {row['ratio']:.1%}")

    poi_counts = Counter(poi for item in counted for poi in item["poi_mentioned"])
    print("\n언급 지점 상위 (수요 집중 지표):")
    for poi, count in poi_counts.most_common(8):
        print(f"  {poi:<22} {count}회")

    zones = payload["data"]["zone_signals"]
    print(f"\n쏠림/이탈 신호: 핫존 {zones['핫존']}건 · 데드존 {zones['데드존']}건")
    if zones["데드존_지점"]:
        print(f"  데드존 지목 지점(분산 후보): {', '.join(zones['데드존_지점'])}")


def output_schema(video_ids: list[str]) -> dict:
    # video_id를 enum으로 묶어 존재하지 않는 항목을 만들거나 빠뜨릴 수 없게 한다 (D-08)
    def obj(props: dict, required: list[str] | None = None) -> dict:
        return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}

    judgment = obj({
        "video_id": {"type": "string", "enum": video_ids},
        "content_type": {"type": "string", "enum": CONTENT_TYPES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": "string", "minLength": 5},
        "poi_mentioned": {"type": "array", "items": {"type": "string"}},
        "sentiment": {"type": "string", "enum": ["긍정", "중립", "부정"]},
        "zone_signal": {"type": "string", "enum": ["핫존", "데드존"]},
    }, required=["video_id", "content_type", "confidence", "evidence", "poi_mentioned", "sentiment"])
    return obj({"judgments": {"type": "array", "items": judgment}})


def schema_errors(data: dict, schema: dict) -> list[str]:
    return [e.message for e in Draft7Validator(schema).iter_errors(data)]


# 한 번에 50건을 다 판정시키면 solar-pro3가 스키마는 지키면서도(구조 오류는 없음)
# 배열 일부 항목을 그냥 빠뜨린다 — max_tokens을 늘리거나 배치를 줄여도 가끔 재현된다.
# "빠진 것만 다시 물어본다"를 스키마가 완전할 때까지 반복하는 게 재시도보다 안정적이다.
BATCH_SIZE = 20
MAX_ROUNDS = 4


def classify_batch(region_name: str, videos: list[dict], args, prompt_version: str, system: str) -> dict:
    by_id = {v["video_id"]: v for v in videos}
    pending = list(by_id)
    judgments: dict[str, dict] = {}
    model_info = None
    replayed = False

    for round_no in range(1, MAX_ROUNDS + 1):
        subset = [by_id[vid] for vid in pending]
        user = json.dumps({
            "region": region_name,
            "videos": [
                {k: v[k] for k in ("video_id", "title", "channel", "published_at", "description", "tags",
                                    "view_count", "comment_count") if k in v}
                for v in subset
            ],
        }, ensure_ascii=False, indent=1)
        schema = output_schema(pending)
        try:
            result = complete_json(system, user, schema, provider=args.provider, model=args.model,
                                   base_url=args.base_url, response_path=args.response,
                                   max_tokens=16000, reasoning_effort="low")
        except LLMError as e:
            sys.exit(f"LLM 호출 실패({region_name}): {e}")
        model_info = (result.model, result.provider)
        replayed = result.provider.startswith("replay")

        errs = schema_errors(result.data, schema)
        if errs:
            sys.exit(f"LLM 응답이 스키마를 어겼다({region_name}, {round_no}회차): {errs[:3]}")
        if not replayed:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log = RUNS_DIR / f"agent2_{region_name}_{stamp}_{round_no}.json"
            log.write_text(json.dumps({"prompt_version": prompt_version, "provider": result.provider,
                                       "model": result.model, "user": user, "response": result.data},
                                       ensure_ascii=False, indent=2), encoding="utf-8")

        for j in result.data["judgments"]:
            judgments.setdefault(j["video_id"], j)  # 중복 응답 시 첫 판정을 쓴다
        pending = [vid for vid in pending if vid not in judgments]
        if not pending or replayed:
            break
        print(f"  {region_name} {round_no}회차: {len(judgments)}/{len(by_id)}건 판정, {len(pending)}건 재요청")

    if pending:
        sys.exit(f"LLM이 {MAX_ROUNDS}회 재요청 후에도 판정을 못 채웠다({region_name}): {pending}")

    return {"judgments": judgments, "model": model_info[0], "provider": model_info[1]}


def build_other(region: str, region_name: str, args) -> dict | None:
    filename = OTHER_RAW_FILES[region][1]
    raw_path = RAW_DIR / filename
    if not raw_path.exists():
        print(f"[건너뜀] {filename}이 없다 — collection/youtube_collect.py --region {region_name[:2]}로 재수집 필요")
        return None
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    # 재수집은 "오늘로부터 최근 90일"이라 signal_status 등 다른 실측 계약(데이터랩 8월분까지만
    # 공개돼 있어 as_of가 그 이전에 멈춰 있음)보다 최신 영상까지 잡힌다. 같은 지역 화면에서
    # "8월 기준 경보" 옆에 "9월 콘텐츠"가 뜨는 시점 불일치를 막기 위해, signal_status의
    # as_of 이후 업로드분은 분류 대상에서 제외한다(하드코딩 아님 — as_of가 갱신되면 자동으로 따라간다).
    signal_path = PROD / f"signal_status_{region}.json"
    as_of = json.loads(signal_path.read_text(encoding="utf-8"))["data"]["as_of"]
    all_videos = raw["videos"]
    eligible = [v for v in all_videos if v["published_at"] <= as_of]
    excluded_recent = len(all_videos) - len(eligible)

    videos = sorted(eligible, key=lambda v: -v["view_count"])[:TOP_N_OTHER]
    video_ids = [v["video_id"] for v in videos]

    system, prompt_version = load_prompt(PROMPT_PATH)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    if args.dump_prompt:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        user = json.dumps({"region": region_name, "videos": videos}, ensure_ascii=False, indent=1)
        path = RUNS_DIR / f"agent2_request_{region}_{stamp}.json"
        path.write_text(json.dumps({"prompt_version": prompt_version, "system": system, "user": user,
                                   "schema": output_schema(video_ids)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"요청 저장: {path.relative_to(ROOT)} ({region_name}, {len(videos)}건, 배치 크기 {BATCH_SIZE})")
        return None

    judgments: dict[str, dict] = {}
    model_info = None
    for i in range(0, len(videos), BATCH_SIZE):
        batch = videos[i:i + BATCH_SIZE]
        result = classify_batch(region_name, batch, args, prompt_version, system)
        judgments.update(result["judgments"])
        model_info = (result["model"], result["provider"])

    by_id = {v["video_id"]: v for v in videos}
    items = []
    for video_id in video_ids:
        video, j = by_id[video_id], judgments[video_id]
        item = {
            "video_id": video_id,
            "title": video["title"],
            "channel": video["channel"],
            "published_at": video["published_at"],
            "view_count": video["view_count"],
            "like_count": video["like_count"],
            "comment_count": video["comment_count"],
            "content_type": j["content_type"],
            "confidence": j["confidence"],
            "evidence": j["evidence"],
            "poi_mentioned": j["poi_mentioned"],
            "sentiment": j["sentiment"],
        }
        if j.get("zone_signal"):
            item["zone_signal"] = j["zone_signal"]
        items.append(item)

    counted, summary = summarize(items)
    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "YouTube Data API v3",
                "provider": "Google",
                "retrieved_at": raw["collected_at"][:10],
                "note": f"검색어 {', '.join(raw['queries'])} / 최근 {raw['period_days']}일 업로드분 {raw['count']}건 중 "
                        f"{as_of} 이전 업로드 {len(eligible)}건 중 조회수 상위 {len(items)}건 분류",
            }
        ],
        "period": {
            "start": min(i["published_at"] for i in items),
            "end": max(i["published_at"] for i in items),
            "granularity": "일",
        },
        "caveat": [
            f"영상은 signal_status 기준일(as_of={as_of}) 이전 업로드분만 포함했다 — 다른 실측 계약(signal_status/"
            f"visitor_profile/hotspots)과 시점을 맞추기 위함이다. 이후 업로드된 {excluded_recent}건은 제외했다.",
            f"수집된 영상 중 조회수 상위 {TOP_N_OTHER}건만 분류했다(기준일 이전 {len(eligible)}건 중). 소규모 채널·최근 업로드 콘텐츠는 과소 대표된다.",
            "조회수는 수집 시점 기준이며 이후 계속 변동한다.",
            "신뢰도 0.6 미만과 '관광무관'은 집계에서 제외했다. 제외 건수는 unclassified_count로 표시한다.",
            "zone_signal은 집계 제외 항목에도 부여된다. 데드존이 지목한 지점은 분산 정책의 목적지 후보로 쓰인다.",
            "분류는 제목·설명·태그 텍스트만으로 수행했으며 영상 내용을 시청해 검증하지 않았다.",
        ],
        "data": {
            "region": {"code": region, "name": region_name},
            "model": {"name": model_info[0], "provider": model_info[1], "prompt_version": prompt_version},
            "items": items,
            "summary": summary,
            "unclassified_count": len(items) - len(counted),
            "zone_signals": zone_signals(items),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="에이전트② 콘텐츠 유형 분류")
    parser.add_argument("--provider", choices=["anthropic", "upstage", "openai", "replay"],
                        help="기본: LLM_PROVIDER, 없으면 .env에 있는 키로 선택")
    parser.add_argument("--model")
    parser.add_argument("--base-url", help="openai 백엔드 주소")
    parser.add_argument("--response", type=Path, help="replay 백엔드가 읽을 응답 파일")
    parser.add_argument("--dump-prompt", action="store_true", help="LLM을 호출하지 않고 요청만 저장")
    parser.add_argument("--region", action="append",
                        help="특정 지역 코드만 처리(반복 지정 가능). 기본: 전체(거제 포함)")
    args = parser.parse_args()
    regions = set(args.region) if args.region else None

    if regions is None or "48310" in regions:
        if (RAW_DIR / RAW_FILE).exists():
            build_geoje()
        else:
            print(f"[건너뜀] 거제: {RAW_FILE}이 없다 (data/raw/youtube는 gitignore 대상 — 기존 data/prod/content_type.json 유지)")

    for region, (region_name, _) in OTHER_RAW_FILES.items():
        if regions is not None and region not in regions:
            continue
        payload = build_other(region, region_name, args)
        if payload is None:
            continue
        errors = validate_payload("content_type", payload)
        if errors:
            sys.exit(f"[스키마 실패] {region}: {errors[:3]}")
        out_path = PROD / f"content_type_{region}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        d = payload["data"]
        print(f"\n{region_name:<5} {len(d['items'])}건 분류 (집계 {len(d['items']) - d['unclassified_count']}건) → data/prod/{out_path.name}")
        for row in d["summary"][:3]:
            print(f"  {row['content_type']:<16} {row['count']:>2}건  조회수 {row['total_views']:>10,}")
        zones = d["zone_signals"]
        if zones["핫존"] or zones["데드존"]:
            print(f"  쏠림/이탈 신호: 핫존 {zones['핫존']}건 · 데드존 {zones['데드존']}건")


if __name__ == "__main__":
    main()
