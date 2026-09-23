"""data/prod/visitor_profile*.json을 실데이터로 만든다 (규칙 처리, LLM 미사용).

DB의 datalab_detail_row(성연령/거리/거주지/소비/동반유형 원자료)를 스키마 필드로
매핑한다. 같은 항목도 수집 시점마다 다른 query_start_month~query_end_month
구간으로 여러 번 적재돼 있어, 지역별로 **가장 최근 구간**(query_end_month 최댓값)
한 벌만 쓴다 — 여러 구간을 섞으면 서로 다른 시점의 분포가 합쳐진다.

total_visitors는 이미 실측인 datalab_monthly_panel(judge_signal_status.py와 동일
소스)의 최신월 visitors를 쓴다. local_external_mix는 이 패널의 소비 비중 필드가
"현지인/외지인" 정의와 정확히 일치하는지 확인되지 않아 비워 둔다(발명 금지).

거리 구간·연령대·동반유형은 DB 구간과 스키마 구간(enum)이 달라 재매핑이 필요하다
(REMAP 표 참고). spending은 내국인 데이터가 금액(원)이 없어 외국인 소비 데이터로
채운다 — caveat에 명시한다.

사용법:
    uv run python collection/db_export.py             # DB 스냅샷이 없을 때
    uv run python agents/agent_visitor_profile.py
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
TOP_RESIDENCE = 8

# DB 연령 밴드(0~9세 단위) → 스키마 연령대. 0~9세는 스키마에 대응 밴드가 없어 제외한다.
AGE_REMAP = {
    "10~19세": "10대", "20~29세": "20대", "30~39세": "30대",
    "40~49세": "40대", "50~59세": "50대", "60~69세": "60대이상", "70세 이상": "60대이상",
}

# DB 거리 구간(6개) → 스키마 4구간. 경계가 어긋나는 구간은 구간 폭 비례로 나눈다
# (구간 내 균등분포 가정 — caveat에 명시).
DISTANCE_REMAP = {
    "30km 미만": [("50km 미만", 1.0)],
    "30km 이상 70km 미만": [("50km 미만", 0.5), ("50~100km", 0.5)],
    "70km 이상 140km 미만": [("50~100km", 30 / 70), ("100~200km", 40 / 70)],
    "140km 이상 190km 미만": [("100~200km", 1.0)],
    "190km 이상 240km 미만": [("100~200km", 10 / 50), ("200km 이상", 40 / 50)],
    "240km 이상": [("200km 이상", 1.0)],
}
DISTANCE_BANDS = ["50km 미만", "50~100km", "100~200km", "200km 이상"]

# DB 동반유형명 → 스키마 4분류
COMPANION_REMAP = {
    "싱글": "나홀로",
    "기타가족": "가족", "배우자": "가족", "부모님": "가족", "자녀": "가족",
    "친구": "친구·연인", "연인": "친구·연인",
    "학생": "단체", "회사동료": "단체",
}


def latest_window(rows: pd.DataFrame) -> pd.DataFrame:
    end = rows["query_end_month"].max()
    return rows[rows["query_end_month"] == end]


def parse_json_col(rows: pd.DataFrame) -> list[dict]:
    return [json.loads(j) for j in rows["row_json"]]


def build_gender_age(rows: pd.DataFrame) -> list[dict]:
    bucket = {}  # (gender, schema_band) -> ratio sum
    for r in parse_json_col(rows):
        band = AGE_REMAP.get(r["방문자 연령"])
        if band is None:
            continue
        for gender, key in (("남", "방문자 비율(남성)"), ("여", "방문자 비율(여성)")):
            bucket[(gender, band)] = bucket.get((gender, band), 0.0) + float(r[key])
    return [
        {"gender": g, "age_band": b, "ratio": round(v / 100, 4)}
        for (g, b), v in sorted(bucket.items())
    ]


def build_distance(rows: pd.DataFrame) -> list[dict]:
    bucket = {b: 0.0 for b in DISTANCE_BANDS}
    for r in parse_json_col(rows):
        weights = DISTANCE_REMAP.get(r["거리구분명"])
        if weights is None:
            continue
        ratio = float(r["방문자비율"])
        for band, w in weights:
            bucket[band] += ratio * w
    return [{"band": b, "ratio": round(v / 100, 4)} for b, v in bucket.items()]


def build_residence(rows: pd.DataFrame) -> list[dict]:
    items = []
    for r in parse_json_col(rows):
        name = r["거주지명"]
        sido, _, sigungu = name.partition(" ")
        items.append({"sido": sido, "sigungu": sigungu or None, "ratio": float(r["광역지자체 비율(%)"])})
    items.sort(key=lambda i: -i["ratio"])
    out = []
    for i in items[:TOP_RESIDENCE]:
        entry = {"sido": i["sido"], "ratio": round(i["ratio"] / 100, 4)}
        if i["sigungu"]:
            entry["sigungu"] = i["sigungu"]
        out.append(entry)
    return out


def build_spending(rows: pd.DataFrame) -> list[dict]:
    by_cat: dict[str, float] = {}
    for r in parse_json_col(rows):
        by_cat[r["업종대분류명"]] = by_cat.get(r["업종대분류명"], 0.0) + float(r["중분류 소비액(천원)"])
    total = sum(by_cat.values())
    return [
        {"category": cat, "amount_krw": round(amt * 1000), "ratio": round(amt / total, 4)}
        for cat, amt in sorted(by_cat.items(), key=lambda kv: -kv[1])
        if total > 0
    ]


def build_companion(rows: pd.DataFrame) -> list[dict]:
    bucket = {}
    for r in parse_json_col(rows):
        band = COMPANION_REMAP.get(r["동반유형명"])
        if band is None:
            continue
        bucket[band] = bucket.get(band, 0) + int(r["언급건수"])
    total = sum(bucket.values())
    return [
        {"type": t, "ratio": round(n / total, 4)}
        for t, n in sorted(bucket.items(), key=lambda kv: -kv[1])
        if total > 0
    ]


def profile_tags(gender_age: list[dict], distance: list[dict], companion: list[dict]) -> list[str]:
    tags = []
    age_totals: dict[str, float] = {}
    for g in gender_age:
        age_totals[g["age_band"]] = age_totals.get(g["age_band"], 0.0) + g["ratio"]
    for band, ratio in age_totals.items():
        if ratio >= 0.3:
            tags.append(f"{band}비중높음")
    near = next((d["ratio"] for d in distance if d["band"] == "50km 미만"), 0.0)
    if near >= 0.3:
        tags.append("근거리방문우세")
    far = next((d["ratio"] for d in distance if d["band"] == "200km 이상"), 0.0)
    if far >= 0.3:
        tags.append("장거리방문우세")
    alone = next((c["ratio"] for c in companion if c["type"] == "나홀로"), 0.0)
    if alone >= 0.3:
        tags.append("나홀로여행우세")
    group = next((c["ratio"] for c in companion if c["type"] == "단체"), 0.0)
    if group >= 0.3:
        tags.append("단체방문우세")
    return tags


def build(region: str, region_name: str, detail: pd.DataFrame, panel: pd.DataFrame, meta: dict) -> dict | None:
    sub = detail[detail["region_id"] == region]
    groups = {}
    for g in ("방문자 성연령별 분포", "거리별 방문자 분포", "방문자 거주지 분포", "관광소비_외국인", "동반유형 언급량"):
        rows = sub[sub["data_group"] == g]
        if rows.empty:
            return None
        groups[g] = latest_window(rows)

    panel_r = panel[panel["canonical_region_id"] == region].sort_values("period_start")
    if panel_r.empty:
        return None
    latest_panel = panel_r.iloc[-1]

    gender_age = build_gender_age(groups["방문자 성연령별 분포"])
    distance = build_distance(groups["거리별 방문자 분포"])
    residence = build_residence(groups["방문자 거주지 분포"])
    spending = build_spending(groups["관광소비_외국인"])
    companion = build_companion(groups["동반유형 언급량"])

    window_end = str(groups["방문자 성연령별 분포"]["query_end_month"].iloc[0])[:7]
    window_start = str(groups["방문자 성연령별 분포"]["query_start_month"].iloc[0])[:7]

    data = {
        "region": {"code": region, "name": region_name},
        "total_visitors": int(latest_panel["visitors"]),
        "gender_age": gender_age,
        "residence": residence,
        "distance": distance,
        "spending": spending,
        "companion": companion,
        "profile_tags": profile_tags(gender_age, distance, companion),
    }

    caveat = [
        f"성연령/거리/거주지/동반유형은 한국관광 데이터랩 원자료의 최신 수집 구간({window_start}~{window_end})만 썼다. "
        "같은 항목이 여러 시점에 재수집돼 있어 구간을 섞지 않았다.",
        "거리 구간은 데이터랩 6구간(30/70/140/190/240km 경계)을 스키마 4구간(50/100/200km 경계)으로 재매핑했다. "
        "경계가 걸치는 구간은 폭 비례로 나눴다(구간 내 균등분포 가정) — 근사치다.",
        "0~9세 방문자는 스키마 연령대에 대응 밴드가 없어 gender_age에서 제외했다(비율 합이 100%에 못 미칠 수 있다).",
        "spending은 관광소비_내국인 데이터에 금액(원) 필드가 없어 관광소비_외국인(업종중분류 소비액) 기준으로 만들었다 — "
        "외국인 방문객의 소비 구조이며 전체 방문객(내국인 다수)의 소비 구조와 다를 수 있다.",
        "동반유형은 데이터랩 원 분류(기타가족/배우자/부모님/자녀/싱글/친구/연인/학생/회사동료)를 스키마 4분류로 합쳐 "
        "집계했다(예: 학생·회사동료 → 단체).",
        "local_external_mix(현지인/외지인)는 이 DB의 소비 비중 필드가 스키마 정의와 정확히 일치하는지 확인되지 않아 비웠다.",
        f"total_visitors는 datalab_monthly_panel 최신월({str(latest_panel['period_start'])[:7]}) 방문자수다(judge_signal_status.py와 동일 소스).",
    ]

    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "한국관광 데이터랩 방문자 프로파일 원자료 (성연령/거리/거주지/소비/동반유형)",
                "provider": "한국관광공사 — 팀 DB datalab_detail_row",
                "retrieved_at": meta["exported_at"][:10],
                "url": "https://datalab.visitkorea.or.kr/",
            },
            {
                "name": "한국관광 데이터랩 월별 패널 (총 방문자수)",
                "provider": "한국관광공사 — 팀 DB datalab_monthly_panel",
                "retrieved_at": meta["exported_at"][:10],
            },
        ],
        "period": {"start": f"{window_start}-01", "end": f"{window_end}-01", "granularity": "월"},
        "caveat": caveat,
        "data": data,
    }


def main() -> None:
    manifest = json.loads((DB_DIR / "manifest.json").read_text(encoding="utf-8"))
    regions = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str}).set_index("region_id")["region_name"]
    detail = pd.read_csv(DB_DIR / "datalab_detail_row.csv", dtype={"region_id": str})
    panel = pd.read_csv(DB_DIR / "datalab_monthly_panel.csv", dtype={"canonical_region_id": str},
                         parse_dates=["period_start"])
    meta = {"exported_at": manifest["exported_at"]}

    PROD.mkdir(parents=True, exist_ok=True)
    for region in CASE_REGIONS:
        payload = build(region, regions[region], detail, panel, meta)
        if payload is None:
            print(f"{regions[region]:<5} 데이터 없음 — 건너뜀")
            continue
        errors = validate_payload("visitor_profile", payload)
        if errors:
            sys.exit(f"[스키마 실패] {region}: {errors[:3]}")
        name = "visitor_profile.json" if region == DEFAULT_REGION else f"visitor_profile_{region}.json"
        (PROD / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        d = payload["data"]
        print(f"{regions[region]:<5} 방문자 {d['total_visitors']:>9,}명  태그 {d['profile_tags']} → data/prod/{name}")


if __name__ == "__main__":
    main()
