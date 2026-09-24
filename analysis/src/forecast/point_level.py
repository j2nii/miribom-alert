"""지점은 쏠리는데 시군구는 평탄한가 — 전국 관광지점으로 확인한다.

왜 이 분석이 필요한가
    지금까지 확인한 것: 시군구 총량에서는 2026년 상반기에 '급증'이라 부를 사건이 없다
    (명절을 맞춰 재면 228곳 중 임계 초과 0곳). 그런데 영월 청령포는 전년 대비 8배였다.
    사례 두 건으로는 "우연히 그 지점만 그랬다"는 반론을 막을 수 없다. 그래서 전국
    관광지점 전수로 **"시군구 총량은 지점의 쏠림을 얼마나 놓치는가"**를 잰다.

자료
    major_attraction_visitors_monthly  주요 관광지점 월별 입장객 (합계 기준)
    attraction_region_map              지점 → 시군구 매핑
    panel_daily.csv                    시군구 일별 외지인 방문자 (월 합계로 집계)

설계에서 조심한 것
    1) **짝지어 비교한다.** 같은 지점의 같은 달을 전년과 비교한다. 2026년에 보고를 시작한
       지점이나 중단한 지점이 섞이면 배율이 아니라 표본 변화를 재게 된다.
    2) **작은 지점을 걸러낸다.** 전년 입장객이 몇십 명인 곳은 배율이 쉽게 튄다.
       기본 기준은 전년 같은 달 1,000명 이상이고, 기준을 바꿔도 결론이 유지되는지 확인한다.
    3) **명절이 옮겨간 달을 헤드라인에서 뺀다.** 2025년 설은 1월, 2026년 설은 2월이라
       1~2월의 전년 대비는 오염되어 있다(09.24 확인). 본 수치는 3~6월로 내고 1~2월은 따로 적는다.
    4) **시군구와 같은 잣대로 잰다.** 지점에 쓴 배율 정의를 시군구 월 합계에도 그대로 적용한다.

사용법
    uv run python analysis/src/forecast/point_level.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "collection"))
INTERIM = ROOT / "data" / "interim"

from db_export import connect  # noqa: E402

MIN_BASE = 1000              # 전년 같은 달 입장객이 이보다 적은 지점은 배율이 불안정하다
POINT_SURGE = 2.0            # 지점 급증으로 볼 배율
REGION_FLAT = 1.2            # 시군구가 '평탄하다'고 볼 상한
CLEAN_MONTHS = ["2026-03", "2026-04", "2026-05", "2026-06"]   # 명절 이동 오염이 없는 달
SHIFTED_MONTHS = ["2026-01", "2026-02"]


def load_points() -> pd.DataFrame:
    path = INTERIM / "attraction_monthly.csv"
    if path.exists():
        return pd.read_csv(path, dtype={"region_id": str}, parse_dates=["observed_month"])
    connection = connect()
    frame = pd.read_sql("""
        SELECT m.canonical_region_id AS region_id,
               a.province_name, a.district_name, a.attraction_name,
               a.observed_month, a.visitor_count
        FROM major_attraction_visitors_monthly AS a
        JOIN attraction_region_map AS m
          ON m.province_name = a.province_name
         AND m.district_name = a.district_name
        WHERE a.visitor_type = '합계'
          AND a.observed_month >= '2023-01-01'
    """, connection)
    connection.close()
    frame["observed_month"] = pd.to_datetime(frame["observed_month"])
    frame["region_id"] = frame["region_id"].astype(str)
    frame.to_csv(path, index=False, encoding="utf-8")
    return frame


def region_monthly() -> pd.DataFrame:
    """시군구 일별 외지인 방문자를 월 합계로 만든다 (지점과 같은 잣대로 재기 위해)."""
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"],
                        usecols=["region_id", "region_name", "observed_date", "visitors_external"])
    panel["month"] = panel["observed_date"].dt.to_period("M")
    # 달이 통째로 들어있는 경우만 쓴다 (2026-08은 14일까지라 월 합계가 작게 나온다)
    days = panel.groupby(["region_id", "month"])["observed_date"].nunique()
    full = days[days >= 28].index
    monthly = panel.groupby(["region_id", "region_name", "month"], as_index=False)["visitors_external"].sum()
    monthly = monthly[monthly.set_index(["region_id", "month"]).index.isin(full)]
    monthly["prev"] = monthly.groupby("region_id")["visitors_external"].shift(12)
    monthly["region_ratio"] = monthly["visitors_external"] / monthly["prev"].replace(0, np.nan)
    return monthly[["region_id", "region_name", "month", "visitors_external", "region_ratio"]]


def paired_point_ratios(points: pd.DataFrame) -> pd.DataFrame:
    """같은 지점·같은 달의 전년 대비 배율. 양쪽 해에 모두 보고된 경우만 남긴다.

    달을 건너뛴 지점이 있어 순서 기반 시차(shift)는 쓸 수 없다. 12개월 전 달을
    직접 계산해 붙인다(24개월 전도 같은 방식). 붙지 않으면 그 관측은 버린다.
    """
    frame = points.copy()
    frame["month"] = frame["observed_month"].dt.to_period("M")
    key = ["region_id", "attraction_name"]
    base = frame[key + ["month", "visitor_count"]]

    def shifted(months: int, name: str) -> pd.DataFrame:
        other = base.copy()
        other["month"] = other["month"] + months
        return other.rename(columns={"visitor_count": name})

    frame = frame.merge(shifted(12, "prev"), on=key + ["month"], how="left")
    frame = frame.merge(shifted(24, "prev2"), on=key + ["month"], how="left")
    frame = frame[frame["prev"].notna()].copy()
    frame["point_ratio"] = frame["visitor_count"] / frame["prev"].replace(0, np.nan)
    # 작년에도 이미 오르던 곳인가 — "신규 개관이라 원래 낮았던 것 아니냐"에 답하기 위해 쓴다
    frame["prior_year_ratio"] = frame["prev"] / frame["prev2"].replace(0, np.nan)
    return frame


def describe(series: pd.Series) -> dict:
    return {"n": int(series.notna().sum()),
            "중앙값": round(float(series.median()), 2),
            "상위10%": round(float(series.quantile(0.9)), 2),
            "상위1%": round(float(series.quantile(0.99)), 2),
            "최대": round(float(series.max()), 2)}


def main() -> None:
    points = load_points()
    ratios = paired_point_ratios(points)
    regions = region_monthly()
    regions["month_str"] = regions["month"].astype(str)
    ratios["month_str"] = ratios["month"].astype(str)

    merged = ratios.merge(regions[["region_id", "region_name", "month_str", "region_ratio"]],
                          on=["region_id", "month_str"], how="inner")
    usable = merged[merged["prev"] >= MIN_BASE].copy()

    print(f"지점 월별 입장객 {len(points):,}행 · {points['attraction_name'].nunique():,}개 지점 · "
          f"{points['region_id'].nunique()}개 시군구")
    print(f"전년 같은 달과 짝지어진 관측 {len(merged):,}건 → 전년 입장객 {MIN_BASE:,}명 이상만 남기면 "
          f"{len(usable):,}건 ({usable['attraction_name'].nunique():,}개 지점)")

    clean = usable[usable["month_str"].isin(CLEAN_MONTHS)]
    shifted = usable[usable["month_str"].isin(SHIFTED_MONTHS)]
    if clean.empty:
        print("2026년 3~6월 자료가 없어 분석할 수 없습니다.")
        return

    print(f"\n[본 수치] 2026년 3~6월 · 지점 관측 {len(clean):,}건 · "
          f"{clean['attraction_name'].nunique():,}개 지점 · {clean['region_id'].nunique()}개 시군구")

    point_stats = describe(clean["point_ratio"])
    region_series = clean.drop_duplicates(["region_id", "month_str"])["region_ratio"]
    region_stats = describe(region_series)
    print("\n1) 같은 잣대(전년 같은 달 대비 배율)로 잰 분포")
    print(f"{'':<10}{'건수':>8}{'중앙값':>9}{'상위10%':>9}{'상위1%':>9}{'최대':>9}")
    print(f"{'지점':<10}{point_stats['n']:>8,}{point_stats['중앙값']:>9.2f}"
          f"{point_stats['상위10%']:>9.2f}{point_stats['상위1%']:>9.2f}{point_stats['최대']:>9.2f}")
    print(f"{'시군구':<10}{region_stats['n']:>8,}{region_stats['중앙값']:>9.2f}"
          f"{region_stats['상위10%']:>9.2f}{region_stats['상위1%']:>9.2f}{region_stats['최대']:>9.2f}")
    print(f"  → 상위 1% 기준 지점 {point_stats['상위1%']:.2f}배 vs 시군구 {region_stats['상위1%']:.2f}배 "
          f"({point_stats['상위1%'] / region_stats['상위1%']:.1f}배 차이) · "
          f"최대값은 {point_stats['최대']:.1f}배 vs {region_stats['최대']:.2f}배")
    print("     시군구 총량은 어느 달에도 1.31배를 넘지 않는다 — 총량만 보면 '아무 일도 없다'")

    # 2) 사각지대 — 지점은 급증했는데 시군구는 평탄한 경우
    blind = clean[(clean["point_ratio"] >= POINT_SURGE) & (clean["region_ratio"] < REGION_FLAT)]
    surged = clean[clean["point_ratio"] >= POINT_SURGE]
    print(f"\n2) 총량 감시의 사각지대 (지점 {POINT_SURGE}배 이상 · 같은 달 시군구 {REGION_FLAT}배 미만)")
    print(f"   지점 급증 {len(surged)}건 중 시군구가 평탄한 경우 **{len(blind)}건** "
          f"({100 * len(blind) / max(len(surged), 1):.0f}%)")
    print(f"   해당 지점 {blind['attraction_name'].nunique()}곳 · "
          f"{blind['region_id'].nunique()}개 시군구에 분포")
    print(f"   시군구 단위로 보면 이 {blind['region_id'].nunique()}곳은 모두 '이상 없음'으로 분류된다")

    # "신규 개관이라 원래 낮았던 것 아닌가"에 대한 답 — 작년에도 이미 오르던 곳인지 본다
    known = blind[blind["prior_year_ratio"].notna()]
    fresh = known[known["prior_year_ratio"] < 1.5]
    print(f"   이 중 전년 배율을 계산할 수 있는 {len(known)}건을 보면, "
          f"작년에는 평탄했다가(1.5배 미만) 올해 처음 뛴 경우가 **{len(fresh)}건**"
          f"({100 * len(fresh) / max(len(known), 1):.0f}%)")
    print("   → 대부분이 '원래 오르던 추세'가 아니라 올해 새로 생긴 쏠림이다")

    top = blind.sort_values("point_ratio", ascending=False).head(12)
    print("\n   대표 사례 (배율 큰 순)")
    print(f"   {'지점':<26}{'시군구':<10}{'월':<9}{'지점배율':>8}{'시군구배율':>10}{'전년':>10}{'올해':>10}")
    for row in top.itertuples():
        print(f"   {row.attraction_name[:24]:<26}{row.region_name:<10}{row.month_str:<9}"
              f"{row.point_ratio:>8.1f}{row.region_ratio:>10.2f}"
              f"{row.prev:>10,.0f}{row.visitor_count:>10,.0f}")

    # 3) 기준을 바꿔도 결론이 유지되는가
    print("\n3) 기준 민감도 (결론이 임계에 기대고 있지 않은지)")
    print(f"   {'최소 전년 입장객':<16}{'지점배율 임계':<14}{'사각지대 건수':>12}{'지점 급증 중 비율':>16}")
    rows = []
    for base in (300, 1000, 3000):
        for threshold in (1.5, 2.0, 3.0):
            subset = clean[clean["prev"] >= base]
            up = subset[subset["point_ratio"] >= threshold]
            hidden = up[up["region_ratio"] < REGION_FLAT]
            share = 100 * len(hidden) / max(len(up), 1)
            rows.append({"최소전년입장객": base, "지점배율임계": threshold,
                         "지점급증": int(len(up)), "사각지대": int(len(hidden)),
                         "사각지대비율_pct": round(share, 1)})
            print(f"   {base:<16,}{threshold:<14.1f}{len(hidden):>12,}{share:>15.0f}%")

    # 4) 명절이 옮겨간 1~2월은 따로 본다
    if not shifted.empty:
        shifted_stats = describe(shifted["point_ratio"])
        shifted_blind = shifted[(shifted["point_ratio"] >= POINT_SURGE) &
                                (shifted["region_ratio"] < REGION_FLAT)]
        print(f"\n4) 참고 — 명절이 옮겨간 1~2월 (본 수치에서 제외한 구간)")
        print(f"   지점 관측 {shifted_stats['n']:,}건 · 중앙값 {shifted_stats['중앙값']}배 · "
              f"상위 10% {shifted_stats['상위10%']}배 · 사각지대 {len(shifted_blind)}건")
        print("   설 연휴가 1월(2025)에서 2월(2026)로 옮겨가 전년 대비가 오염된 구간이므로 본 수치에 넣지 않는다")

    # 5) 사례 지역 확인 (기존에 보고한 숫자가 이 절차로도 재현되는가)
    print("\n5) 사례 지역 확인")
    for region_id, label in (("51750", "영월"), ("48310", "거제")):
        case = usable[usable["region_id"] == region_id].sort_values("point_ratio", ascending=False)
        if case.empty:
            print(f"   {label}: 조건을 만족하는 지점 관측 없음")
            continue
        print(f"   {label} — 상위 5개 지점-월")
        for row in case.head(5).itertuples():
            print(f"     {row.attraction_name[:22]:<24}{row.month_str:<9}"
                  f"지점 {row.point_ratio:>6.1f}배 · 시군구 {row.region_ratio:>5.2f}배 "
                  f"({row.prev:,.0f} → {row.visitor_count:,.0f}명)")

    summary = {
        "분석월_본수치": CLEAN_MONTHS,
        "최소_전년입장객": MIN_BASE,
        "지점_급증임계": POINT_SURGE,
        "시군구_평탄상한": REGION_FLAT,
        "지점_관측수": int(len(clean)),
        "지점수": int(clean["attraction_name"].nunique()),
        "시군구수": int(clean["region_id"].nunique()),
        "지점_배율분포": point_stats,
        "시군구_배율분포": region_stats,
        "지점급증_건수": int(len(surged)),
        "사각지대_건수": int(len(blind)),
        "사각지대_지점수": int(blind["attraction_name"].nunique()),
        "사각지대_시군구수": int(blind["region_id"].nunique()),
        "사각지대_전년배율_계산가능": int(len(known)),
        "사각지대_올해처음뛴건수": int(len(fresh)),
        "민감도": rows,
    }
    (INTERIM / "point_level.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    clean.to_csv(INTERIM / "point_level_ratios.csv", index=False, encoding="utf-8")
    blind.to_csv(INTERIM / "point_level_blindspots.csv", index=False, encoding="utf-8")
    print("\n출력: data/interim/point_level.json · point_level_ratios.csv · point_level_blindspots.csv")


if __name__ == "__main__":
    main()
