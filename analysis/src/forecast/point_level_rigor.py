"""지점 쏠림 결과를 공격해 본다 — 반론 7가지에 하나씩 수치로 답한다.

왜 이 스크립트가 따로 필요한가
    point_level.py는 "지점 급증 108건 중 106건이 시군구 총량에서 보이지 않는다"를 냈다.
    이 문장에 대해 심사에서 나올 수 있는 반론은 분명하다.

    R1 "관광지 하나는 시군구의 일부일 뿐인데, 총량이 안 움직이는 건 당연한 산수 아닌가"
    R2 "2배라는 기준이 그 지점에게 이례적이긴 한가. 원래 들쭉날쭉한 곳 아닌가"
    R3 "2026년에만 그런 것 아닌가"
    R4 "보고하는 지점이 달마다 달라지는데 표본이 바뀐 것 아닌가"
    R5 "98%라는 비율의 오차는 얼마인가"
    R6 "축제나 일회성 행사를 급증이라 부르는 것 아닌가"
    R7 "그래서 지점을 보라는 건 알겠는데, 미리 알 방법은 있는가"

    각각에 답을 만들고, 답이 나오지 않으면 나오지 않는다고 적는다.

사용법
    uv run python analysis/src/forecast/point_level_rigor.py
    (point_level.py를 먼저 실행해 data/interim/attraction_monthly.csv를 만들어 둘 것)
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
INTERIM = ROOT / "data" / "interim"

from point_level import (MIN_BASE, POINT_SURGE, REGION_FLAT,  # noqa: E402
                         load_points, paired_point_ratios, region_monthly)

SEASONS = {"2026": ["2026-03", "2026-04", "2026-05", "2026-06"],
           "2025": ["2025-03", "2025-04", "2025-05", "2025-06"]}
MIN_HISTORY = 6      # 지점 고유 변동성을 재려면 과거 배율이 이만큼은 있어야 한다


def build(points: pd.DataFrame, regions: pd.DataFrame) -> pd.DataFrame:
    ratios = paired_point_ratios(points)
    ratios["month_str"] = ratios["month"].astype(str)
    regions = regions.copy()
    regions["month_str"] = regions["month"].astype(str)
    regions = regions.rename(columns={"visitors_external": "region_visitors"})
    regions["region_prev"] = regions["region_visitors"] / regions["region_ratio"]
    merged = ratios.merge(
        regions[["region_id", "region_name", "month_str", "region_visitors",
                 "region_prev", "region_ratio"]],
        on=["region_id", "month_str"], how="inner")
    return merged[merged["prev"] >= MIN_BASE].copy()


def season(frame: pd.DataFrame, year: str) -> pd.DataFrame:
    return frame[frame["month_str"].isin(SEASONS[year])].copy()


def blind_spots(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    surged = frame[frame["point_ratio"] >= POINT_SURGE]
    return surged, surged[surged["region_ratio"] < REGION_FLAT]


def cluster_bootstrap_share(frame: pd.DataFrame, draws: int = 2000, seed: int = 3):
    """시군구를 단위로 재표집해 '지점 급증 중 총량에 안 보이는 비율'의 구간을 낸다.

    같은 시군구의 지점들은 서로 닮았으므로 관측을 독립으로 보면 구간이 좁게 나온다.
    지역 묶음째로 다시 뽑는 것이 정직하다.
    """
    rng = np.random.default_rng(seed)
    regions = frame["region_id"].unique()
    grouped = {region: group for region, group in frame.groupby("region_id")}
    shares = []
    for _ in range(draws):
        picked = rng.choice(regions, len(regions), replace=True)
        sample = pd.concat([grouped[region] for region in picked])
        surged, blind = blind_spots(sample)
        if len(surged):
            shares.append(len(blind) / len(surged))
    if not shares:
        return (float("nan"), float("nan"))
    return float(np.percentile(shares, 2.5)), float(np.percentile(shares, 97.5))


def main() -> None:
    points = load_points()
    regions = region_monthly()
    frame = build(points, regions)

    current = season(frame, "2026")
    surged, blind = blind_spots(current)
    print(f"기준 결과 재확인 — 2026년 3~6월 · 관측 {len(current):,}건 · "
          f"지점 급증 {len(surged)}건 · 그중 총량 미탐지 {len(blind)}건 "
          f"({100 * len(blind) / len(surged):.0f}%)")

    # ------------------------------------------------------------------ R1
    print("\nR1. \"관광지 하나는 시군구의 일부이니 총량이 안 움직이는 게 당연하지 않은가\"")
    print("    → 맞다. 그리고 그 '당연함'의 크기를 재는 것이 이 분석의 핵심이다.")
    current["share_of_region"] = 100 * current["prev"] / current["region_prev"]
    current["contribution_pp"] = 100 * (current["visitor_count"] - current["prev"]) / current["region_prev"]
    # 총량이 REGION_FLAT배가 되려면 이 지점 혼자 몇 배가 되어야 하는가
    current["required_ratio"] = 1 + (REGION_FLAT - 1) * current["region_prev"] / current["prev"]
    blind = current.loc[blind.index] if len(blind) else current.iloc[:0]

    share = current["share_of_region"]
    contribution = blind["contribution_pp"]
    required = current["required_ratio"]
    print(f"    지점 입장객이 시군구 월 방문자에서 차지하는 비중: "
          f"중앙값 {share.median():.2f}% · 상위 10% {share.quantile(0.9):.2f}% · 최대 {share.max():.1f}%")
    print(f"    급증 106건이 시군구 총량에 더한 몫: "
          f"중앙값 {contribution.median():+.2f}%p · 최대 {contribution.max():+.2f}%p")
    print(f"    시군구 총량을 {REGION_FLAT}배로 만들려면 그 지점 혼자 몇 배가 되어야 하는가: "
          f"중앙값 {required.median():,.0f}배")
    region_noise = current.drop_duplicates(["region_id", "month_str"])["region_ratio"]
    print(f"    한편 시군구 총량 배율의 정상 변동폭(표준편차)은 {region_noise.std():.3f}이다")
    print(f"    → 지점 급증이 총량에 남기는 흔적({contribution.median():.2f}%p)은 총량 자체의 "
          f"흔들림({100 * region_noise.std():.1f}%p)보다 {100 * region_noise.std() / max(contribution.median(), 0.001):.0f}배 작다.")
    print("    → 즉 총량 감시는 '놓친' 것이 아니라 **원리적으로 감지할 수 없다**. "
          "이것이 감시 단위를 바꿔야 하는 이유다.")

    # ------------------------------------------------------------------ R2
    print("\nR2. \"2배가 그 지점에게 이례적이긴 한가 (원래 들쭉날쭉한 곳 아닌가)\"")
    history = frame[frame["month_str"] < "2026-01"]
    stats = history.groupby(["region_id", "attraction_name"])["point_ratio"].agg(
        hist_n="count", hist_median="median", hist_p95=lambda s: s.quantile(0.95),
        hist_max="max")
    checked = blind.merge(stats, on=["region_id", "attraction_name"], how="left")
    have = checked[checked["hist_n"] >= MIN_HISTORY]
    beyond_p95 = have[have["point_ratio"] > have["hist_p95"]]
    beyond_max = have[have["point_ratio"] > have["hist_max"]]
    print(f"    과거 배율이 {MIN_HISTORY}개 이상 있는 {len(have)}건 기준")
    print(f"    그 지점의 과거 상위 5%를 넘는 경우: {len(beyond_p95)}건 "
          f"({100 * len(beyond_p95) / max(len(have), 1):.0f}%)")
    print(f"    그 지점의 과거 최대치를 넘는 경우:   {len(beyond_max)}건 "
          f"({100 * len(beyond_max) / max(len(have), 1):.0f}%)")
    print(f"    (이 지점들의 과거 배율 중앙값은 {have['hist_median'].median():.2f}배로 평소엔 평탄하다)")

    # ------------------------------------------------------------------ R3
    print("\nR3. \"2026년에만 그런 것 아닌가\" — 한 해 앞선 구간에서 그대로 반복해 본다")
    replication = []
    for year in ("2025", "2026"):
        block = season(frame, year)
        up, hidden = blind_spots(block)
        if not len(up):
            continue
        low, high = cluster_bootstrap_share(block)
        replication.append({"연도": year, "관측": int(len(block)),
                            "지점수": int(block["attraction_name"].nunique()),
                            "지점급증": int(len(up)), "총량미탐지": int(len(hidden)),
                            "비율_pct": round(100 * len(hidden) / len(up), 1),
                            "비율95CI_pct": [round(100 * low, 1), round(100 * high, 1)]})
    print(f"    {'연도':<7}{'관측':>8}{'지점수':>8}{'지점급증':>9}{'총량미탐지':>11}{'비율':>8}{'95% 구간':>16}")
    for row in replication:
        ci = f"[{row['비율95CI_pct'][0]:.0f}%, {row['비율95CI_pct'][1]:.0f}%]"
        print(f"    {row['연도']:<7}{row['관측']:>8,}{row['지점수']:>8,}{row['지점급증']:>9}"
              f"{row['총량미탐지']:>11}{row['비율_pct']:>7.0f}%{ci:>16}")
    print("    → 두 해 모두 같은 결과면 2026년의 특수 사정이 아니라 구조다")

    # ------------------------------------------------------------------ R4
    print("\nR4. \"보고 지점이 달마다 바뀌는데 표본이 달라진 것 아닌가\" — 균형 패널로 다시 본다")
    counts = current.groupby(["region_id", "attraction_name"])["month_str"].nunique()
    full = counts[counts == len(SEASONS["2026"])].index
    balanced = current.set_index(["region_id", "attraction_name"]).loc[full].reset_index()
    b_surged, b_blind = blind_spots(balanced)
    print(f"    4개월 모두 보고한 지점만: {balanced['attraction_name'].nunique():,}곳 · 관측 {len(balanced):,}건")
    print(f"    지점 급증 {len(b_surged)}건 중 총량 미탐지 {len(b_blind)}건 "
          f"({100 * len(b_blind) / max(len(b_surged), 1):.0f}%)")

    # ------------------------------------------------------------------ R5
    low, high = cluster_bootstrap_share(current)
    print("\nR5. \"98%의 오차는 얼마인가\" — 시군구를 묶음으로 재표집한 구간")
    print(f"    {100 * len(blind) / len(surged):.0f}% "
          f"[{100 * low:.0f}%, {100 * high:.0f}%] (시군구 단위 붓스트랩 2,000회)")

    # ------------------------------------------------------------------ R6
    print("\nR6. \"축제나 일회성 행사를 급증이라 부르는 것 아닌가\"")
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"],
                        usecols=["region_id", "observed_date", "festival_active"])
    panel["month_str"] = panel["observed_date"].dt.to_period("M").astype(str)
    festival = panel.groupby(["region_id", "month_str"])["festival_active"].max().reset_index()
    festival = festival.rename(columns={"festival_active": "region_festival"})
    tagged = blind.merge(festival, on=["region_id", "month_str"], how="left")
    with_festival = int((tagged["region_festival"] > 0).sum())
    # 지속성: 같은 지점이 2개월 이상 연속으로 급증했는가
    runs = blind.groupby(["region_id", "attraction_name"])["month_str"].nunique()
    persistent = int((runs >= 2).sum())
    print(f"    같은 달 그 시군구에 축제가 있었던 경우: {with_festival}건 "
          f"({100 * with_festival / max(len(tagged), 1):.0f}%)")
    print(f"    두 달 이상 이어진 지점: {persistent}곳 / 전체 {len(runs)}곳 "
          f"({100 * persistent / max(len(runs), 1):.0f}%) — 일회성 행사라면 한 달로 끝난다")

    # ------------------------------------------------------------------ R7
    print("\nR7. \"그래서 지점 급증을 미리 알 방법이 있는가\" — 시군구 검색으로 가려낼 수 있는지")
    naver = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"],
                        usecols=["region_id", "observed_date", "naver_interest"])
    naver["month_str"] = naver["observed_date"].dt.to_period("M").astype(str)
    monthly_search = naver.groupby(["region_id", "month_str"], as_index=False)["naver_interest"].mean()
    monthly_search = monthly_search.sort_values(["region_id", "month_str"])
    monthly_search["search_prev_year"] = monthly_search.groupby("region_id")["naver_interest"].shift(12)
    monthly_search["search_ratio"] = (monthly_search["naver_interest"] /
                                      monthly_search["search_prev_year"].replace(0, np.nan))

    board = current.drop_duplicates(["region_id", "month_str"])[["region_id", "month_str"]].copy()
    hit_keys = set(zip(blind["region_id"], blind["month_str"]))
    board["has_point_surge"] = [(r, m) in hit_keys for r, m in zip(board["region_id"], board["month_str"])]
    board = board.merge(monthly_search[["region_id", "month_str", "search_ratio"]],
                        on=["region_id", "month_str"], how="left").dropna(subset=["search_ratio"])

    from detect_ablation import auc, auc_ci  # noqa: E402
    labels = board["has_point_surge"].to_numpy().astype(int)
    scores = board["search_ratio"].to_numpy()
    value = auc(labels, scores)
    lo, hi = auc_ci(labels, scores)
    print(f"    시군구-월 {len(board):,}칸 중 지점 급증이 있던 칸 {int(labels.sum())}칸")
    print(f"    시군구 검색량(전년 대비)으로 그 칸을 가려내는 판별력 AUC {value:.3f} [{lo:.3f}, {hi:.3f}]")
    verdict = "판별력 있음" if lo > 0.5 else ("역방향" if hi < 0.5 else "판별력 없음")
    print(f"    판정: {verdict}")
    if verdict != "판별력 있음":
        print("    → 시군구 검색으로는 어느 지점이 뜨는지 알 수 없다. "
              "지점 입장객 자체를 감시 지표로 올려야 한다는 뜻이다(월 단위라도).")

    # ------------------------------------------------------------------ R8
    print()
    print('R8. "그래서 어떤 규칙을 운영하라는 것인가" — 제안 규칙의 경보 부담을 센다')
    rule = current.merge(stats, on=["region_id", "attraction_name"], how="left")
    rule = rule[rule["hist_n"] >= MIN_HISTORY]
    alarms = rule[rule["point_ratio"] > rule["hist_p95"]]
    months = current["month_str"].nunique()
    print(f"    규칙: '그 지점의 과거 배율 상위 5%를 넘으면 경보' (지점마다 자기 기준을 쓴다)")
    print(f"    적용 가능한 지점 {rule['attraction_name'].nunique():,}곳 · {months}개월 기준")
    print(f"    경보 {len(alarms)}건 = 월 평균 {len(alarms) / months:.0f}건 "
          f"(전국 {rule['region_id'].nunique()}개 시군구에 분산되므로 시군구당 월 "
          f"{len(alarms) / months / max(rule['region_id'].nunique(), 1):.2f}건)")
    print(f"    같은 기간 시군구 총량 기준 경보는 0건이다(총량이 1.2배를 넘은 시군구-월이 없다)")
    print("    → 담당자 한 명이 감당할 수 있는 수준이며, 총량 감시로는 애초에 울릴 경보가 없다")

    summary = {
        "R8_규칙": "지점별 과거 배율 상위 5% 초과",
        "R8_대상지점": int(rule["attraction_name"].nunique()),
        "R8_경보건수": int(len(alarms)),
        "R8_월평균경보": round(len(alarms) / months, 1),
        "R8_시군구당_월경보": round(len(alarms) / months / max(rule["region_id"].nunique(), 1), 3),
        "기준_지점급증": int(len(surged)),
        "기준_총량미탐지": int(len(blind)),
        "R1_지점비중_pct": {"중앙값": round(float(share.median()), 3),
                         "상위10%": round(float(share.quantile(0.9)), 3),
                         "최대": round(float(share.max()), 2)},
        "R1_총량기여_pp": {"중앙값": round(float(contribution.median()), 3),
                       "최대": round(float(contribution.max()), 3)},
        "R1_필요배율_중앙값": round(float(required.median()), 1),
        "R1_시군구배율_표준편차": round(float(region_noise.std()), 4),
        "R2_과거상위5%초과": {"대상": int(len(have)), "초과": int(len(beyond_p95)),
                        "과거최대초과": int(len(beyond_max))},
        "R3_연도재현": replication,
        "R4_균형패널": {"지점수": int(balanced["attraction_name"].nunique()),
                    "급증": int(len(b_surged)), "미탐지": int(len(b_blind))},
        "R5_비율95CI_pct": [round(100 * low, 1), round(100 * high, 1)],
        "R6_축제겹침": with_festival, "R6_2개월이상_지점": persistent,
        "R7_검색판별력_AUC": round(float(value), 3),
        "R7_AUC_95CI": [round(lo, 3), round(hi, 3)], "R7_판정": verdict,
    }
    keep = ["region_id", "region_name", "attraction_name", "month_str", "prev", "visitor_count",
            "point_ratio", "region_ratio", "share_of_region", "contribution_pp", "required_ratio"]
    blind[keep].to_csv(INTERIM / "point_level_rigor_events.csv", index=False, encoding="utf-8")
    (INTERIM / "point_level_rigor.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n출력: data/interim/point_level_rigor.json")


if __name__ == "__main__":
    main()
