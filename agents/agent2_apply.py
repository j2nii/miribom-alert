"""에이전트② 분류 결과를 data/prod/content_type*.json으로 만든다.

분류 자체는 agents/prompts/agent2_content_type.md 프롬프트로 수행하고,
이 스크립트는 그 판정 결과를 원본 수집 데이터와 조인해 스키마 형식으로 내보낸다.

RESULTS의 값은 프롬프트 실행 결과다. 재실행 시 이 표를 교체한다.

거제(48310, 기본 지역)는 기존처럼 수집 원본(data/raw/youtube/*.json, gitignore됨)을
쓴다. 나머지 5개 사례 지역은 그 원본이 없어 DB 스냅샷(data/raw/db/youtube_case.csv)을
쓰되, 지역당 950~1500개 영상 전체를 분류하는 건 이번 범위를 벗어나 **조회수 상위
TOP_N_OTHER개만** 분류한다(거제도 원래 "검색 결과 상위 영상만 수집"이었으므로 같은
성격의 표본 제한이다 — caveat에 명시).

사용법:
    uv run python agents/agent2_apply.py
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_data import validate_payload  # noqa: E402

RAW_DIR = ROOT / "data" / "raw" / "youtube"
DB_DIR = ROOT / "data" / "raw" / "db"
PROD = ROOT / "data" / "prod"
OUT = PROD / "content_type.json"
DEFAULT_REGION = "48310"
OTHER_REGIONS = ["51750", "12130", "47940", "51210", "51810"]
TOP_N_OTHER = 15

PROMPT_VERSION = "agent2_content_type_v1.1"
MODEL = "claude-opus-5"
# RESULTS는 API 호출이 아니라 Claude Code 세션 안에서 프롬프트를 적용해 얻은 판정이다.
# (Opus 5는 temperature 파라미터를 받지 않으므로 temperature 기록도 두지 않는다)
PROVIDER = "Claude Code 세션(API 미경유)"
CONFIDENCE_FLOOR = 0.6
# RESULTS가 판정한 수집본. 최신 파일을 자동으로 고르면 다른 수집본(예: 220일치)과
# 조인되어 결과가 조용히 바뀌므로 고정한다. 재분류할 때 함께 바꾼다.
RAW_FILE = "거제_20260912_1320.json"

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


# 나머지 5개 사례 지역 — youtube_case.csv 조회수 상위 TOP_N_OTHER개만 분류(제목/채널/검색어
# 텍스트 기준, 설명·태그는 이 스냅샷에 없다). video_id: (유형, 신뢰도, 근거, 언급 지점, 감성, zone_signal|None)
RESULTS_OTHER: dict[str, dict[str, tuple]] = {
    "12130": {  # 여수
        "UzOZm0lAaZM": ("관광무관", 0.75, "랜덤댄스 챌린지 콘텐츠로 여수는 촬영 배경일 뿐 방문 정보가 없음", [], "중립", None),
        "TAl2OpcSVJk": ("자연경관형", 0.70, "'아름다운 해양 도시 여수'로 도시 경관 소개가 중심인 홍보 영상", [], "긍정", None),
        "llRpHE9r4HI": ("예능·방송 노출형", 0.85, "KBS '1박2일' 방영분으로 예능 프로그램 노출 콘텐츠", [], "긍정", None),
        "KAbmaWvTHtU": ("맛집형", 0.70, "특정 식당의 손님 응대 논란을 다룬 보도", [], "부정", "데드존"),
        "kd18fTVCUL4": ("예능·방송 노출형", 0.80, "'현재 난리난 또간집 여수식당'으로 방송 노출 후 화제가 된 식당을 다룸", [], "긍정", None),
        "MBYSq-fikyQ": ("예능·방송 노출형", 0.80, "KBS '1박2일' 방영분(위 영상과 동일 소재)", [], "긍정", None),
        "N1LGDrTP8Jg": ("코스·일정형", 0.55, "'여수 홍보'로 제목이 포괄적이며 여러 지점을 다루는 지역 홍보 영상으로 추정", [], "긍정", None),
        "zjHA1TjLoGI": ("맛집형", 0.85, "'장인어른의 현지인 여수 맛집 대방출'로 맛집 순회가 콘텐츠 전체", [], "긍정", None),
        "bAcN_uD2fxk": ("관광무관", 0.90, "영아 학대 사건을 다룬 사건·사고 보도로 방문 수요와 무관", [], "중립", None),
        "FUuaRBz_-n8": ("관광무관", 0.65, "'여수 섬 박람회가 돈을 펑펑 쓴 곳'으로 예산 집행을 비판하는 시사 콘텐츠", [], "부정", None),
        "G7gAzJn1Q_s": ("관광무관", 0.70, "유튜버 사기·잠적 사건을 다룬 콘텐츠로 여수 방문 정보가 아님", [], "부정", None),
        "MsM0jdfPxsY": ("예능·방송 노출형", 0.85, "'식신 정준하가 정중하게 고른 여수 맛집'으로 인물 추천이 선정 기준", [], "긍정", None),
        "kf77xjc8Mw0": ("맛집형", 0.65, "'혼밥 손님 홀대한 여수 맛집 논란' 보도(KAbmaWvTHtU와 같은 사건)", [], "부정", "데드존"),
        "w0v35RJPesw": ("관광무관", 0.85, "폐가에서 백골 발견 사건을 다룬 미스터리 콘텐츠", [], "중립", None),
        "ImEdYn0xMc0": ("예능·방송 노출형", 0.75, "'또간집' 후속으로 혼밥 손님 논란 당사자를 직접 취재", [], "중립", None),
    },
    "47940": {  # 울릉 — 바가지·상권침체 논란이 상위권에 집중된 지역(데드존 신호 다수)
        "K4Niws_6v3s": ("관광무관", 0.70, "제철 기술로 백화현상에 대응한 산업 기술을 다룬 콘텐츠", [], "중립", None),
        "_lJeZzSpJiQ": ("관광무관", 0.75, "'다시는 안 볼 것처럼 장사하는 울릉도 주민들'로 바가지 여론을 다룬 비판 콘텐츠", [], "부정", "데드존"),
        "eXNz7CXcrJ8": ("체험·액티비티형", 0.80, "'정신나갈거 같은 울릉도 체험'으로 체험형 활동이 소재", [], "긍정", None),
        "MYA63ADIBH8": ("관광무관", 0.70, "'올해 완전히 망한 울릉도 근황'으로 상권 침체를 다룬 르포", [], "부정", "데드존"),
        "DfKkgLEeCfs": ("관광무관", 0.75, "철강 부산물을 이용한 해양 기술을 다룬 산업 콘텐츠", [], "중립", None),
        "9zafUsI9_UY": ("코스·일정형", 0.65, "실제 방문 브이로그로 방문 경험을 서술(부정적 반응 포함)", [], "부정", None),
        "kIezWDJIPuU": ("관광무관", 0.75, "군 부대 근무 환경을 다룬 국방 관련 콘텐츠(케이블카는 군 시설용)", [], "중립", None),
        "rFHd6c2N1-k": ("관광무관", 0.80, "'울릉도 여행 취소했다' 논란을 다룬 뉴스 보도", [], "부정", "데드존"),
        "bSZ_sm6-Kls": ("예능·방송 노출형", 0.60, "예능인 방문 반응을 다룬 예능 클립", [], "긍정", None),
        "CF7MuwLElhY": ("관광무관", 0.85, "'울릉도도 울고 갈 바가지'로 바가지 요금 논란을 다룬 보도", [], "부정", "데드존"),
        "8RTLNqtFbbY": ("관광무관", 0.80, "화산 지질 연구를 다룬 과학 콘텐츠", [], "중립", None),
        "FCX1FbO-J0o": ("관광무관", 0.60, "'울릉도까지 가실 필요 있나요?'로 방문 회의감을 표현한 숏폼", [], "부정", None),
        "KQKyIiDkfO8": ("맛집형", 0.65, "'돌아버린 12만원어치 회'로 가격 불만을 다룬 맛집 콘텐츠", [], "부정", "데드존"),
        "RsG_dENchcg": ("관광무관", 0.75, "제철 부산물 해양 투기 문제를 다룬 환경 콘텐츠", [], "부정", None),
        "YcztpsSZ1PI": ("관광무관", 0.85, "'여수 이어 울릉도 취소' 바가지 논란 연쇄 보도", [], "부정", "데드존"),
    },
    "51210": {  # 속초
        "Z37Pn3tWMq8": ("맛집형", 0.85, "-40도 철판 오레오 아이스크림 등 특정 디저트 메뉴를 다룬 맛집 콘텐츠", [], "긍정", None),
        "raGhNxdrKao": ("예능·방송 노출형", 0.60, "코미디 채널 '숏박스'의 로드트립 소재 콩트", [], "긍정", None),
        "UrrjvJyhTms": ("관광무관", 0.80, "'속초 언제 터지나 했어' 국민 분노 보도로 바가지 논란을 다룸", [], "부정", "데드존"),
        "Nent_p64dUU": ("코스·일정형", 0.75, "'속초 민박집 사장님의 폭주 여행 가이드'로 현지인 추천 코스 구성", [], "긍정", None),
        "MzhK0vZAZ3U": ("맛집형", 0.85, "팔도대게 판매 현장을 다룬 맛집 콘텐츠", ["팔도대게"], "긍정", None),
        "VmY3B8PR-pI": ("맛집형", 0.80, "팔도대게 시리즈 콘텐츠(위 영상과 동일 점포)", ["팔도대게"], "긍정", None),
        "wJcbEtlr608": ("맛집형", 0.85, "'지금 절대 놓치면 안되는 속초맛집 10곳'으로 맛집 목록형 콘텐츠", [], "긍정", None),
        "i2L4YS3aG5I": ("관광무관", 0.75, "스탠드업 코미디 콘텐츠로 방문 정보가 아님", [], "중립", None),
        "2dzGRua5lTw": ("코스·일정형", 0.75, "'5성급 호텔은 처음인 속초에서 노는법'으로 숙박·먹투어 일정 구성", [], "긍정", None),
        "H7KPpCq6X_c": ("맛집형", 0.80, "팔도대게 시리즈 콘텐츠", ["팔도대게"], "긍정", None),
        "TZIbfRhOA7M": ("맛집형", 0.75, "팔도대게 시리즈 콘텐츠", ["팔도대게"], "긍정", None),
        "D2B_NaP4siM": ("관광무관", 0.85, "축구선수 밈을 다룬 스포츠 콘텐츠로 지역명은 말장난('겉바속초')", [], "중립", None),
        "AwNCgOycSzk": ("맛집형", 0.80, "'100만원 넘게 쓰고 찾은 속초 레전드 맛집'으로 맛집 순회 콘텐츠", [], "긍정", None),
        "_WA8KpiXV0k": ("체험·액티비티형", 0.65, "프라이빗 가족탕 온천 체험을 다룬 콘텐츠", [], "긍정", None),
        "WlorhkQco-0": ("체험·액티비티형", 0.75, "설악워터피아 수영대회 참가 체험 콘텐츠", ["설악워터피아"], "긍정", None),
    },
    "51750": {  # 영월 — 단종 역사 서사 채널이 다수라 관광무관 비중이 높다(역사 교양 ≠ 방문 정보)
        "0bQE4hA2U3w": ("관광무관", 0.85, "반려견 소재 브이로그로 영월은 태그로만 언급됨", [], "중립", None),
        "dVh4TZRWfo4": ("관광무관", 0.60, "'단종의 묘는 어떻게 발견됐을까?' 역사 서사 콘텐츠로 방문 정보 없음", ["단종장릉"], "중립", None),
        "1zxpr307R0U": ("관광무관", 0.65, "'고소당한 김삿갓계곡 근황'으로 법적 분쟁을 다룬 콘텐츠", ["김삿갓계곡"], "부정", None),
        "FdEnIDAsejg": ("포토스팟형", 0.70, "'청령포에 배 타려고 끝없는 줄 서는 진짜 이유'로 실제 대기 혼잡 상황을 다룸", ["청령포"], "중립", "핫존"),
        "xIIITdEZ-wk": ("관광무관", 0.60, "'정순왕후는 왜 영월에 가지 못했을까?' 역사 서사 콘텐츠", ["단종장릉"], "중립", None),
        "7f_BAjPTGaQ": ("예능·방송 노출형", 0.60, "'나는 자연인이다' 계열 예능 콘텐츠(태그에 영월여행·고씨동굴)", ["고씨동굴"], "긍정", None),
        "du7gz6izA1k": ("관광무관", 0.60, "'단종의 하루가 이랬습니다' 역사 서사 콘텐츠", ["단종장릉"], "중립", None),
        "I7XmJzb8eas": ("코스·일정형", 0.70, "'영월을 롤러코스터로 관광하기'로 실제 관광 동선을 다룬 브이로그", [], "긍정", None),
        "MYRixH2-eRc": ("관광무관", 0.60, "'유배지에서 단종은 밥은 어떻게 먹었을까?' 역사 서사 콘텐츠", ["청령포"], "중립", None),
        "5PQ_ASG0vx0": ("관광무관", 0.65, "'이름조차 남기지 못한 단종의 궁녀들' 역사 서사 콘텐츠", [], "중립", None),
        "TczOM_s1_Ak": ("포토스팟형", 0.65, "'청령포의 인기실감!'으로 현장 인기·체감 혼잡을 다룸", ["청령포"], "긍정", "핫존"),
        "nxukV1yfvCA": ("맛집형", 0.85, "'요즘 핫한 영월 여행' 현지인 맛집 풀코스로 맛집 순회가 콘텐츠 전체", [], "긍정", None),
        "TKjoP9LyQgg": ("관광무관", 0.60, "'역사가 기록하지 못한 4개월 영월 사람들의 뜨거운 정' 역사 서사 콘텐츠", [], "중립", None),
        "OviDUGVzyh0": ("관광무관", 0.60, "'17살에 끌려간 소년왕' 역사 서사 콘텐츠", [], "중립", None),
        "hUy8-tFT3aY": ("관광무관", 0.85, "'파란 보석 5천만 톤 영월서 터졌다' 광물자원 발견을 다룬 경제 뉴스", [], "중립", None),
    },
    "51810": {  # 인제 — 검색어(인제)와 우연히 겹치는 무관 콘텐츠가 상위권 다수
        "GI7k1QszJXU": ("관광무관", 0.60, "지역 밀착 브이로그로 방문 유발보다 인물 소재가 중심", [], "중립", None),
        "qwNHoH_7B7M": ("관광무관", 0.60, "백담계곡 급류 안전 경고 영상으로 방문 유도가 아닌 위험 경고", ["백담계곡"], "부정", None),
        "yE9-ENNbXsU": ("관광무관", 0.90, "중국 공대 인재 현황을 다룬 다큐멘터리로 인제와 무관(키워드 우연 일치)", [], "중립", None),
        "toYQCP0Q-nc": ("관광무관", 0.85, "'인제프(INJEF)' 밈 애니메이션으로 지명과 무관한 콘텐츠", [], "중립", None),
        "0-nPEj6euio": ("관광무관", 0.90, "중국 인재전쟁을 다룬 다큐멘터리로 인제와 무관", [], "중립", None),
        "BF2hbsM7zOE": ("관광무관", 0.55, "내용을 특정할 수 없는 짧은 코멘트형 영상", [], "중립", None),
        "OFkuwVC37Wo": ("예능·방송 노출형", 0.70, "방송인들의 인제 방문을 다룬 예능 콘텐츠", [], "긍정", None),
        "VpCtHHQ8l88": ("코스·일정형", 0.55, "'인제 홍보'로 제목이 포괄적인 지역 홍보 영상", [], "긍정", None),
        "RaXWtZFCOus": ("체험·액티비티형", 0.55, "인제스피디움으로 추정되는 서킷에서의 차량 테스트 콘텐츠", ["인제스피디움"], "중립", None),
        "VkHG6Fl2_8w": ("자연경관형", 0.70, "'백담계곡은 아셔도 여기는 잘 모르실겁니다'로 숨은 경관 명소를 소개", [], "긍정", None),
        "LxKhkNcmddM": ("관광무관", 0.80, "'그것이 알고싶다' 시사 프로그램의 실종 사건 소재", [], "중립", None),
        "PO70p_-qbtM": ("관광무관", 0.75, "인제양양터널을 소재로 한 고속도로 인프라 상식 콘텐츠", [], "중립", None),
        "wIl7jmVNPlk": ("관광무관", 0.85, "IQ 퀴즈 콘텐츠로 인제와 무관", [], "중립", None),
        "S78Srg5cRJ8": ("예능·방송 노출형", 0.55, "가수의 인제 해병대 행사 참석을 다룬 예능성 콘텐츠", [], "긍정", None),
        "hkcZ8YiZ_BM": ("체험·액티비티형", 0.75, "인제스피디움 서킷 주행 콘텐츠", ["인제스피디움"], "긍정", None),
    },
}


def build_other(region: str, region_name: str, cases: "pd.DataFrame") -> dict | None:
    results = RESULTS_OTHER.get(region)
    if not results:
        return None
    g = cases[cases["region_id"] == region].drop_duplicates(subset=["video_id"])
    top = g.sort_values("view_count", ascending=False).head(TOP_N_OTHER)

    items = []
    for _, video in top.iterrows():
        verdict = results.get(video["video_id"])
        if verdict is None:
            continue
        content_type, confidence, evidence, pois, sentiment, zone = verdict
        item = {
            "video_id": video["video_id"],
            "title": video["title"],
            "channel": video["channel_name"],
            "published_at": str(video["published_at"])[:10],
            "view_count": int(video["view_count"]) if pd.notna(video["view_count"]) else 0,
            "like_count": int(video["like_count"]) if pd.notna(video["like_count"]) else 0,
            "comment_count": int(video["comment_count"]) if pd.notna(video["comment_count"]) else 0,
            "content_type": content_type,
            "confidence": confidence,
            "evidence": evidence,
            "poi_mentioned": pois,
            "sentiment": sentiment,
        }
        if zone:
            item["zone_signal"] = zone
        items.append(item)
    if not items:
        return None

    counted, summary = summarize(items)
    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "YouTube Data API v3",
                "provider": "Google — 팀 DB youtube_case",
                "retrieved_at": datetime.now().astimezone().strftime("%Y-%m-%d"),
                "note": f"지역명 검색어로 수집된 {len(g)}건 중 조회수 상위 {len(items)}건만 분류했다.",
            }
        ],
        "period": {
            "start": min(i["published_at"] for i in items),
            "end": max(i["published_at"] for i in items),
            "granularity": "일",
        },
        "caveat": [
            f"수집된 영상 중 조회수 상위 {TOP_N_OTHER}건만 분류했다(거제는 검색 결과 상위 수집이었고, "
            f"이 지역들은 DB 스냅샷 전체({len(g)}건)가 커서 상위 조회수 기준으로 추가 표본 제한을 뒀다). "
            "소규모 채널·최근 업로드 콘텐츠는 과소 대표된다.",
            "조회수는 DB 적재 시점 기준이며 이후 계속 변동한다.",
            "신뢰도 0.6 미만과 '관광무관'은 집계에서 제외했다. 제외 건수는 unclassified_count로 표시한다.",
            "zone_signal은 집계 제외 항목에도 부여된다. 데드존이 지목한 지점은 분산 정책의 목적지 후보로 쓰인다.",
            "분류는 제목·채널명·검색 키워드 텍스트만으로 수행했다(이 스냅샷에는 설명·태그가 없다) — "
            "거제(RAW_FILE 기반)보다 근거가 더 제한적이다.",
        ],
        "data": {
            "region": {"code": region, "name": region_name},
            "model": {"name": MODEL, "provider": PROVIDER, "prompt_version": PROMPT_VERSION},
            "items": items,
            "summary": summary,
            "unclassified_count": len(items) - len(counted),
            "zone_signals": zone_signals(items),
        },
    }


def main() -> None:
    if (RAW_DIR / RAW_FILE).exists():
        build_geoje()
    else:
        print(f"[건너뜀] {RAW_FILE}이 없다 (data/raw/youtube는 gitignore 대상 — 기존 data/prod/content_type.json 유지)")

    cases = pd.read_csv(DB_DIR / "youtube_case.csv", dtype={"region_id": str})
    regions = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str}).set_index("region_id")["region_name"]
    for region in OTHER_REGIONS:
        payload = build_other(region, regions[region], cases)
        if payload is None:
            print(f"\n{regions[region]:<5} 분류 결과 없음 — 건너뜀")
            continue
        errors = validate_payload("content_type", payload)
        if errors:
            sys.exit(f"[스키마 실패] {region}: {errors[:3]}")
        out_path = PROD / f"content_type_{region}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        d = payload["data"]
        print(f"\n{regions[region]:<5} {len(d['items'])}건 분류 (집계 {len(d['items']) - d['unclassified_count']}건) → data/prod/{out_path.name}")
        for row in d["summary"][:3]:
            print(f"  {row['content_type']:<16} {row['count']:>2}건  조회수 {row['total_views']:>10,}")


if __name__ == "__main__":
    main()
