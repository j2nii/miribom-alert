"""data/prod/hotspots*.json을 실데이터로 만든다 (규칙 처리, LLM 미사용).

DB의 major_attraction_visitors_monthly(문화체육관광부 주요관광지점 입장객 통계)에서
지역별 상위 관광지 방문자수·전월 대비 증감률을 뽑는다. 매뉴얼 p.13 공간유형 4분류는
DB에 없는 값이라 자동 판정이 불가능하다 — 지역당 상위 10곳 내외라 사람이 채운
소규모 룩업 테이블(POI_SPATIAL_TYPE)로 분류한다(발명 금지 원칙: 분류 없는 POI는
순위에서 제외하지, 임의로 추정하지 않는다).

coord(좌표)·visitor_mix(현지인/외지인)·congestion_level·bottleneck은 이 DB로는
구할 수 없어 비운다 — visitor_mix를 내국인/외국인 비율로 대체하면 스키마가 뜻하는
"현지인/외지인"(거주지 기준)과 다른 값이 되므로 일부러 채우지 않는다.

사용법:
    uv run python collection/db_export.py        # DB 스냅샷이 없을 때
    uv run python agents/agent_hotspots.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_data import validate_payload  # noqa: E402

DB_DIR = ROOT / "data" / "raw" / "db"
PROD = ROOT / "data" / "prod"
DEFAULT_REGION = "48310"
CASE_REGIONS = ["48310", "51750", "12130", "47940", "51210", "51810"]
TOP_N = 10

# 지역당 상위 10곳 내외의 사람이 채운 분류 (매뉴얼 p.13 4분류). 이름은
# major_attraction_visitors_monthly.attraction_name과 정확히 일치해야 한다.
POI_SPATIAL_TYPE = {
    # 거제 (48310)
    "거제식물원(정글돔)": "실내 공간 가치 체류 중심형",
    "도장포어촌체험마을": "실외 공간 가치 체류 중심형",
    "포로수용소유적공원": "실내 공간 가치 체류 중심형",
    "김영삼전대통령생가·기록전시관": "실내 공간 가치 체류 중심형",
    "거제파노라마케이블카": "지형·경사 이동·저항 흐름형",
    "해금강,외도": "실외 공간 가치 체류 중심형",
    "조선해양문화관": "실내 공간 가치 체류 중심형",
    "근포땅굴": "실내 공간 가치 체류 중심형",
    "이수도": "실외 공간 가치 체류 중심형",
    "거제뷰컨트리클럽": "실외 공간 가치 체류 중심형",
    # 여수 (12130)
    "돌산공원(여수해상케이블카)": "지형·경사 이동·저항 흐름형",
    "(주)여수예술랜드": "실외 공간 가치 체류 중심형",
    "전라좌수영거북선": "실외 공간 가치 체류 중심형",
    "아쿠아플라넷여수": "실내 공간 가치 체류 중심형",
    "유월드 루지테마파크": "지형·경사 이동·저항 흐름형",
    "금오도": "실외 공간 가치 체류 중심형",
    "유람선(오동도 코스)": "네트워크 보행 흐름형",
    "디오션리조트 워터파크": "실외 공간 가치 체류 중심형",
    "전라남도 해양수산과학관": "실내 공간 가치 체류 중심형",
    "거문도": "실외 공간 가치 체류 중심형",
    # 울릉 (47940)
    "독도": "실외 공간 가치 체류 중심형",
    "관음도": "지형·경사 이동·저항 흐름형",
    "봉래폭포": "지형·경사 이동·저항 흐름형",
    "태하향목관광 모노레일": "지형·경사 이동·저항 흐름형",
    "독도박물관": "실내 공간 가치 체류 중심형",
    "독도 및 해돋이관광 케이블카": "지형·경사 이동·저항 흐름형",
    "죽도": "실외 공간 가치 체류 중심형",
    # 속초 (51210)
    "설악산국립공원(설악동)": "지형·경사 이동·저항 흐름형",
    "아바이마을(갯배)": "네트워크 보행 흐름형",
    "설악워터피아": "실내 공간 가치 체류 중심형",
    "척산온천휴양촌": "실내 공간 가치 체류 중심형",
    "국립산악박물관": "실내 공간 가치 체류 중심형",
    "뮤지엄엑스": "실내 공간 가치 체류 중심형",
    "속초시박물관": "실내 공간 가치 체류 중심형",
    "엑스포타워": "실내 공간 가치 체류 중심형",
    "척산온천": "실내 공간 가치 체류 중심형",
    "얼라이브하트": "실내 공간 가치 체류 중심형",
    # 영월 (51750)
    "청령포": "실외 공간 가치 체류 중심형",
    "단종장릉": "실외 공간 가치 체류 중심형",
    "영월관광센터": "실내 공간 가치 체류 중심형",
    "동강시스타 골프장": "실외 공간 가치 체류 중심형",
    "젊은달 와이파크(술샘박물관)": "실내 공간 가치 체류 중심형",
    "별마로천문대": "지형·경사 이동·저항 흐름형",
    "영월동굴생태관": "실내 공간 가치 체류 중심형",
    "망경대산자연휴양림": "실외 공간 가치 체류 중심형",
    "고씨동굴관광지": "지형·경사 이동·저항 흐름형",
    "라디오스타박물관": "실내 공간 가치 체류 중심형",
    # 인제 (51810)
    "농촌체험마을(황태마을)": "실외 공간 가치 체류 중심형",
    "농촌체험마을(하추리마을)": "실외 공간 가치 체류 중심형",
    "dmz평화생명동산": "실외 공간 가치 체류 중심형",
    "합강정공원(번지점프)": "지형·경사 이동·저항 흐름형",
    "농촌체험마을(냇강마을)": "실외 공간 가치 체류 중심형",
    "농촌체험마을(신월리마을)": "실외 공간 가치 체류 중심형",
    "농촌체험마을(산채마을)": "실외 공간 가치 체류 중심형",
    "농촌체험마을(소치마을)": "실외 공간 가치 체류 중심형",
}


def load_attractions() -> pd.DataFrame:
    df = pd.read_csv(DB_DIR / "major_attraction_visitors_monthly.csv", dtype={"region_id": str},
                      parse_dates=["observed_month"])
    return df[df["visitor_type"] == "합계"].copy()


def build(region: str, region_name: str, tot: pd.DataFrame, meta: dict) -> dict | None:
    g = tot[tot["region_id"] == region].sort_values("observed_month")
    if g.empty:
        return None
    latest_m = g["observed_month"].max()
    prev_m = latest_m - pd.DateOffset(months=1)
    latest = g[g["observed_month"] == latest_m].set_index("attraction_name")["visitor_count"]
    prev = g[g["observed_month"] == prev_m].set_index("attraction_name")["visitor_count"]
    # 전월 값이 있고 0이 아닌 곳만 증감률을 계산할 수 있다 (change_rate는 스키마상 필수값)
    comparable = [name for name in latest.index.intersection(prev.index) if prev[name] > 0]
    ranked = latest.loc[comparable].sort_values(ascending=False)

    ranking = []
    skipped_unclassified = []
    for name, visitors in ranked.items():
        if len(ranking) >= TOP_N:
            break
        spatial_type = POI_SPATIAL_TYPE.get(name)
        if spatial_type is None:
            skipped_unclassified.append(name)
            continue
        change_rate = round(float((visitors - prev[name]) / prev[name]), 4)
        ranking.append({
            "rank": len(ranking) + 1,
            "poi_name": name,
            "visitors": int(visitors),
            "change_rate": change_rate,
            "spatial_type": spatial_type,
        })

    if not ranking:
        return None

    prev_start = prev_m.strftime("%Y-%m-01")
    prev_end = (prev_m + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
    latest_end = (latest_m + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")

    caveat = [
        "순위·증감률은 문화체육관광부 주요관광지점 입장객 통계(월별) 기준이다. 통신사 유동인구가 아니라 "
        "관광지점이 자체 집계·제출한 입장객 수라 무료 개방지·비집계 지점은 실제 방문자보다 과소 대표될 수 있다.",
        "증감률은 직전월 대비다(전월 값이 0이거나 없는 지점은 증감률을 계산할 수 없어 순위에서 제외했다).",
        "coord(좌표)·visitor_mix(현지인/외지인)·congestion_level·bottleneck은 이 DB에 없어 비웠다. "
        "visitor_mix를 내국인/외국인 비율로 대체하지 않았다 — 스키마가 뜻하는 거주지 기준 현지인/외지인과 다르다.",
        "spatial_type(매뉴얼 p.13 공간유형)은 DB에 없는 값이라 사람이 지점별로 분류했다(현장 확인 전 잠정 분류).",
    ]
    if skipped_unclassified:
        caveat.append(f"공간유형 분류가 없어 순위에서 제외한 지점: {', '.join(skipped_unclassified)}")

    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "주요관광지점 입장객 통계",
                "provider": "문화체육관광부 — 팀 DB major_attraction_visitors_monthly",
                "retrieved_at": meta["exported_at"][:10],
                "note": "지역 매핑은 attraction_region_map(문자열 시군구명 → canonical_region_id)을 사용했다.",
            }
        ],
        "period": {"start": prev_start, "end": latest_end, "granularity": "월"},
        "caveat": caveat,
        "data": {
            "region": {"code": region, "name": region_name},
            "baseline_period": {"start": prev_start, "end": prev_end, "granularity": "월"},
            "ranking": ranking,
        },
    }


def main() -> None:
    manifest = json.loads((DB_DIR / "manifest.json").read_text(encoding="utf-8"))
    regions = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str}).set_index("region_id")["region_name"]
    tot = load_attractions()
    meta = {"exported_at": manifest["exported_at"]}

    PROD.mkdir(parents=True, exist_ok=True)
    for region in CASE_REGIONS:
        payload = build(region, regions[region], tot, meta)
        if payload is None:
            print(f"{regions[region]:<5} 데이터 없음 — 건너뜀")
            continue
        errors = validate_payload("hotspots", payload)
        if errors:
            sys.exit(f"[스키마 실패] {region}: {errors[:3]}")
        name = "hotspots.json" if region == DEFAULT_REGION else f"hotspots_{region}.json"
        (PROD / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        d = payload["data"]
        print(f"{regions[region]:<5} {d['baseline_period']['end']} 기준 상위 {len(d['ranking'])}곳 → data/prod/{name}")
        for r in d["ranking"][:3]:
            print(f"        {r['rank']}. {r['poi_name']:<20} {r['visitors']:>8,}명  {r['change_rate']:+.1%}  {r['spatial_type']}")


if __name__ == "__main__":
    main()
