"""에이전트④ — 선례 조사 (`precedent`).

무엇을 하는가
    지금 이 지역과 **같은 공간 유형**을 다룬 혼잡도 사례를 골라 카드로 내보낸다.
    사례 본문(상황·조치·결과)은 `manual/precedent_cases.json`에 있는 **원문 그대로**이고,
    이 스크립트는 **고르고 정렬만** 한다.

왜 LLM을 쓰지 않는가
    사례가 6건뿐이라 "무엇을 고를까"에 판단의 여지가 거의 없다. 반면 LLM에 요약을
    맡기면 원문에 없는 조치나 성과를 지어낼 위험이 생긴다. 조치 문장과 쪽수를 코드가
    그대로 넣는 것은 에이전트③에서 이미 쓰는 방식이다(D-08).
    → **선택은 규칙, 문장은 원문.** 사유(why)도 어떤 조건이 맞았는지 사실만 적는다.

사례 출처 (전부 공개 자료)
    주요 관광지 혼잡도 측정 방안 연구 보고서(한국관광공사, 2025, 192쪽)
      p.16~17 Ⅱ-02 혼잡도 분석 사례 — 제주관광공사·서울교통공사·서울여대·한국교통연구원
      p.19    Ⅱ-03 선행연구 분석 — 행정안전부·한국교통연구원

정직하게 적어 두는 한계
    1. 이 사례들은 "어느 지역이 혼잡에 대응해 무엇을 했고 결과가 어땠다"가 아니라
       **"어느 기관이 혼잡도를 이렇게 측정·분석했다"**에 가깝다.
    2. 공개된 성과 수치가 없어 전부 `outcome.measured = false`(정성 사례)다.
    3. 공간 유형은 원문에 없어 **우리가 분류**했다. 근거를 카드마다 남긴다.

사용법
    uv run python agents/agent4_precedent.py                 # 거제(기본)
    uv run python agents/agent4_precedent.py --region 51750  # 영월
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

CASES = ROOT / "manual" / "precedent_cases.json"
PROD = ROOT / "data" / "prod"
KST = timezone(timedelta(hours=9))
BASE_REGION = "48310"          # 기본 지역(거제)은 파일명에 접미사가 없다
MAX_CASES = 3                  # 화면 카드 수. 너무 많으면 담당자가 안 읽는다


def load_region_inputs(region: str | None):
    """그 지역의 핫스팟 공간 유형·콘텐츠 유형·경보 단계를 읽는다. 선례를 고르는 기준이 된다."""
    suffix = f"_{region}" if region and region != BASE_REGION else ""

    def read(name: str):
        path = PROD / f"{name}{suffix}.json"
        if not path.exists():
            sys.exit(f"{path.name}이 없다. 먼저 그 지역 {name}을 만들어야 한다.")
        return json.loads(path.read_text(encoding="utf-8"))

    hotspots, content, signal = read("hotspots"), read("content_type"), read("signal_status")
    ranking = hotspots["data"]["ranking"]
    top_content = max(content["data"]["summary"], key=lambda row: row["count"])
    return {
        "region": signal["data"]["region"],
        "spatial_types": [row["spatial_type"] for row in ranking if row.get("spatial_type")],
        "top_spatial_type": ranking[0].get("spatial_type") if ranking else None,
        "content_type": top_content["content_type"],
        "alert_level": signal["data"]["alert_level"],
    }


def score(case: dict, context: dict) -> tuple[float, list[str]]:
    """사례와 지역이 얼마나 맞는지. 맞은 조건만 사유로 남긴다(추정하지 않는다)."""
    points, reasons = 0.0, []
    if case["spatial_type"] == context["top_spatial_type"]:
        points += 0.6
        reasons.append(f"핫스팟 1위와 같은 공간 유형({case['spatial_type']})")
    elif case["spatial_type"] in context["spatial_types"]:
        points += 0.4
        reasons.append(f"상위 핫스팟 중 같은 공간 유형({case['spatial_type']})이 있음")
    if case.get("content_type") and case["content_type"] == context["content_type"]:
        points += 0.3
        reasons.append(f"콘텐츠 유형 일치({case['content_type']})")
    if not reasons:
        points += 0.1
        reasons.append("공간·콘텐츠 유형은 다르지만 혼잡도 측정·대응 사례로 참고 가능")
    return round(min(points, 1.0), 2), reasons


def to_card(case: dict, similarity: float, reasons: list[str]) -> dict:
    """스키마가 요구하는 모양으로 옮긴다. 문장은 원문 그대로 둔다."""
    basis = case["근거"]
    return {
        "case_id": case["case_id"],
        "region_name": case["region_name"],
        "year": case["year"],
        "situation": case["situation"],
        "spatial_type": case["spatial_type"],
        **({"content_type": case["content_type"]} if case.get("content_type") else {}),
        "actions": case["actions"],
        "outcome": case["outcome"],
        "similarity": similarity,
        "source": {
            "name": f"{basis['기관']} {basis['사업명']}",
            "provider": "한국관광공사",
            "retrieved_at": "2026-09-26",
            "note": f"주요 관광지 혼잡도 측정 방안 연구 보고서 p.{basis['쪽']} · {basis['절']} "
                    f"· 선정 사유: {', '.join(reasons)}",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="지역 코드(예: 51750). 기본은 거제")
    parser.add_argument("--max", type=int, default=MAX_CASES)
    args = parser.parse_args()

    catalog = json.loads(CASES.read_text(encoding="utf-8"))
    context = load_region_inputs(args.region)
    region_code = context["region"]["code"]

    ranked = []
    for case in catalog["cases"]:
        similarity, reasons = score(case, context)
        ranked.append((similarity, reasons, case))
    ranked.sort(key=lambda item: (-item[0], item[2]["case_id"]))
    picked = ranked[: args.max]

    document = {
        "_mock": False,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source": [{
            "name": catalog["_출처문서"]["제목"],
            "provider": catalog["_출처문서"]["발행"],
            "retrieved_at": "2026-09-26",
            "note": f"{catalog['_출처문서']['쪽수']}쪽 · p.16~17 혼잡도 분석 사례, p.19 선행연구 분석",
        }],
        "period": {"start": "2023-01-01", "end": "2025-12-31", "granularity": "년"},
        "caveat": [
            "사례의 상황·조치·결과 문장은 연구보고서 원문을 그대로 옮긴 것이다. 요약하거나 다듬지 않았다.",
            "이 사례들은 '어느 지역이 혼잡에 대응해 무엇을 했고 결과가 어땠다'가 아니라 "
            "'어느 기관이 혼잡도를 이렇게 측정·분석했다'에 가깝다. 조치 참고용으로만 읽을 것.",
            "공개된 성과 수치가 없어 모든 사례가 정성 사례(measured=false)다. 수치를 추정해 넣지 않았다.",
            "공간 유형은 원문에 표기가 없어 분석 대상을 보고 분류한 값이다. 근거는 각 사례의 출처 note에 있다.",
            "유사도는 핫스팟 1위의 공간 유형 일치(0.6)·상위 핫스팟 일치(0.4)·콘텐츠 유형 일치(0.3)를 "
            "더해 산출한 규칙 값이며, 통계적 유사도가 아니다.",
        ],
        "data": {
            "region": context["region"],
            "matched_for": {
                "spatial_type": context["top_spatial_type"],
                "content_type": context["content_type"],
                "alert_level": context["alert_level"],
            },
            "cases": [to_card(case, similarity, reasons) for similarity, reasons, case in picked],
        },
    }

    suffix = "" if region_code == BASE_REGION else f"_{region_code}"
    path = PROD / f"precedent{suffix}.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{context['region']['name']}({region_code}) → {path.relative_to(ROOT)}")
    print(f"  기준: 핫스팟 1위 공간유형 {context['top_spatial_type']} · "
          f"콘텐츠 {context['content_type']} · 경보 {context['alert_level']}")
    for similarity, reasons, case in picked:
        print(f"  [{case['case_id']}] {case['region_name']} ({case['근거']['기관']}) "
              f"유사도 {similarity} · p.{case['근거']['쪽']}")
        print(f"      사유: {', '.join(reasons)}")
    print(f"  선정 {len(picked)}건 / 전체 {len(catalog['cases'])}건")


if __name__ == "__main__":
    main()
