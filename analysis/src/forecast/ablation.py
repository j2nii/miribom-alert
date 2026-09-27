"""추가 데이터가 예측을 실제로 개선하는가 — 블록 단위 기여도 실험.

왜 이 실험이 따로 필요한가
    baseline.py의 사다리는 변수를 한 층씩 "올리기만" 한다. 그런데 층을 올려서
    0.03%p 좋아졌다는 말은, 모델을 같은 조건에서 다시 돌렸을 때 생기는 흔들림
    (난수 씨앗만 바꿔도 생기는 차이)보다 작으면 아무 의미가 없다. 그래서 여기서는
      1) 같은 설정을 씨앗만 바꿔 여러 번 돌려 **잡음 바닥**을 먼저 잰다
      2) 전진(하나씩 추가)과 후진(전체에서 하나씩 제거) 두 방향으로 본다
      3) 차이에 **지역 단위 붓스트랩 신뢰구간**과 **지역 승률**을 붙인다
    셋을 다 통과해야 "추가 데이터가 도움이 된다"고 쓸 수 있다.

블록
    LAG 방문자 시차(항상 포함)   CAL 달력   FES 축제
    NAV 네이버 일별 검색지수                        (전일까지 공개)
    DLB 한국관광 데이터랩 월간 지표                 (매월 17일 전월분 → 공개시점 엄격 적용)
    WXP 과거 관측 날씨(예측 시점까지)               (운영 가능)
    WX0 예측 대상일의 실측 날씨                     (운영 불가 — 상한 확인용)

사용법
    uv run python analysis/src/forecast/ablation.py --horizon 7 --seeds 3
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"

from baseline import SPLITS, TARGET, build_features, lagged, rolling_mean, smape  # noqa: E402

DATALAB_LEVELS = ["sns_mentions", "navigation_searches", "lodging_searches",
                  "tourism_spend_outsider_krw_thousand", "visitors", "unique_visitors"]
DATALAB_RATES = ["visitors_yoy_pct", "lodging_searches_yoy_pct", "avg_nights",
                 "overnight_visit_pct", "stay_minutes"]


def datalab_features(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """월간 데이터랩을 '예측 시점에 이미 공개된 달'만 쓰도록 붙인다.

    공개 규칙: m월분은 (m+1)월 17일 공개. 예측 시점 o = 대상일 d - horizon 이므로
    쓸 수 있는 최신 달은 period(o - 16일) - 1개월이다.
    (예: o=3/17 -> 2월분 사용 가능, o=3/16 -> 1월분까지만)
    """
    monthly = pd.read_csv(INTERIM / "datalab_monthly.csv", dtype={"region_id": str},
                          parse_dates=["period_start"]).sort_values(["region_id", "period_start"])
    monthly = monthly.reset_index(drop=True)
    monthly["month"] = monthly["period_start"].dt.to_period("M")

    out = pd.DataFrame(index=monthly.index)
    grouped = monthly.groupby("region_id")
    for column in DATALAB_LEVELS:
        # 지역마다 규모가 달라 절대값 대신 '그 지역의 평소(직전 12개월) 대비 몇 배'로 본다
        trailing = grouped[column].transform(lambda s: s.shift(1).rolling(12, min_periods=6).median())
        out[f"dlb_{column}_ratio"] = monthly[column] / trailing.replace(0, np.nan)
        out[f"dlb_{column}_yoy"] = monthly[column] / grouped[column].shift(12).replace(0, np.nan)
    for column in DATALAB_RATES:
        out[f"dlb_{column}"] = monthly[column]
    out["region_id"] = monthly["region_id"].to_numpy()
    out["month"] = monthly["month"].to_numpy()

    # 대상일 -> 쓸 수 있는 달 매핑
    dates = panel[["region_id", "observed_date"]].copy()
    origin = dates["observed_date"] - pd.Timedelta(days=horizon)
    dates["month"] = (origin - pd.Timedelta(days=16)).dt.to_period("M") - 1
    merged = dates.merge(out, on=["region_id", "month"], how="left")
    merged["dlb_staleness_days"] = (
        dates["observed_date"].to_numpy() - merged["month"].dt.to_timestamp().to_numpy()
    ) / np.timedelta64(1, "D")
    return merged.drop(columns=["region_id", "observed_date", "month"])


def placebo_datalab_features(panel: pd.DataFrame, horizon: int, seed: int = 11) -> pd.DataFrame:
    """지역을 뒤섞은 가짜 데이터랩 — 변수를 18개 더 넣은 것 자체의 효과를 재는 대조군.

    진짜 데이터랩이 개선을 만든 것이 신호 때문인지, 아니면 그냥 변수 수가 늘어
    모델 용량이 커졌기 때문인지 구분하려면 이 대조군이 필요하다. 날짜 구조는 그대로
    두고 지역 이름표만 섞으므로, 개선이 남는다면 그것은 신호가 아니다.
    """
    rng = np.random.default_rng(seed)
    shuffled = panel[["region_id", "observed_date"]].copy()
    regions = np.sort(shuffled["region_id"].unique())
    mapping = dict(zip(regions, rng.permutation(regions)))
    shuffled["region_id"] = shuffled["region_id"].map(mapping)
    fake = datalab_features(shuffled, horizon)
    return fake.rename(columns={c: c.replace("dlb_", "plb_") for c in fake.columns})


def lagged_weather_features(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """예측 시점까지 관측된 날씨만 쓴다 (대상일의 날씨는 모른다)."""
    frame = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True)
    cut = horizon + 1  # 관측 다음 날 공개
    out = pd.DataFrame(index=frame.index)
    out["wxp_temp_last"] = lagged(frame, "avg_temperature_c", cut)
    out["wxp_temp_mean7"] = rolling_mean(frame, "avg_temperature_c", cut, 7)
    out["wxp_precip_last"] = lagged(frame, "precipitation_mm", cut)
    out["wxp_precip_mean7"] = rolling_mean(frame, "precipitation_mm", cut, 7)
    out["wxp_wind_mean7"] = rolling_mean(frame, "max_wind_speed_ms", cut, 7)
    return out


def assemble(horizon: int):
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    panel = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True)
    data = build_features(panel, horizon)
    data = pd.concat([data, datalab_features(panel, horizon),
                      placebo_datalab_features(panel, horizon),
                      lagged_weather_features(panel, horizon)], axis=1)

    blocks = {
        "LAG": [c for c in data.columns if c.startswith("vis_")],
        "CAL": ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday", "rest_run_length"],
        "FES": ["festival_active", "festival_pre", "festival_post"],
        "NAV": ["naver_last", "naver_mean7", "naver_mean28", "naver_ratio_7_28",
                "naver_jump", "naver_year_ratio"],
        "DLB": [c for c in data.columns if c.startswith("dlb_")],
        # 데이터랩 '방문자' 계열은 예측 대상과 같은 원천(이동통신)의 월 집계다.
        # 공개시점은 지켰지만 "대상을 다시 넣은 것 아니냐"는 반론이 가능하므로,
        # 방문자 계열을 뺀 구성(DLX)으로 같은 이득이 나는지 따로 확인한다.
        "DLX": [c for c in data.columns if c.startswith("dlb_")
                and "visitors" not in c],
        "PLB": [c for c in data.columns if c.startswith("plb_")],
        "WXP": [c for c in data.columns if c.startswith("wxp_")],
        "WX0": ["avg_temperature_c", "min_temperature_c", "max_temperature_c",
                "precipitation_mm", "max_wind_speed_ms", "weather_available"],
    }
    return data, blocks


def fit_predict(fit_frame, test_frame, columns, seed):
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.06, early_stopping=True,
                                          validation_fraction=0.15, random_state=seed)
    model.fit(fit_frame[columns], np.log1p(fit_frame[TARGET]))
    return np.expm1(model.predict(test_frame[columns]))


def region_smape(frame, column):
    return frame.groupby("region_id").apply(
        lambda g: smape(g[TARGET].to_numpy(), g[column].to_numpy()), include_groups=False)


def paired_bootstrap(base, other, draws=2000, seed=7):
    """지역을 단위로 재표집해 sMAPE 차이(대상-기준)의 신뢰구간을 낸다."""
    rng = np.random.default_rng(seed)
    diff = (other - base).to_numpy()
    n = len(diff)
    samples = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(draws)])
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()
    horizon, n_seeds = args.horizon, args.seeds

    data, blocks = assemble(horizon)

    def slice_split(name):
        start, end = SPLITS[name]
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)]

    fit_pool = pd.concat([slice_split("train"), slice_split("valid")])
    test = slice_split("test").copy()
    fit_frame = fit_pool.dropna(subset=blocks["LAG"] + [TARGET])
    test = test[test[blocks["LAG"]].notna().all(axis=1)].copy()

    configs = {}
    forward = ["LAG", "CAL", "FES", "NAV", "DLB", "WXP"]
    running = []
    for name in forward:
        running = running + [name]
        configs["+".join(running)] = list(running)
    full = list(running)
    full_label = "+".join(full)
    configs[full_label + "+WX0"] = full + ["WX0"]                # 상한(운영 불가)
    for name in ["CAL", "FES", "NAV", "DLB", "WXP"]:             # 후진 제거
        configs[f"FULL-{name}"] = [b for b in full if b != name]
    configs["LAG+CAL+FES+NAV+DLX"] = ["LAG", "CAL", "FES", "NAV", "DLX"]   # 방문자계열 제외
    configs["LAG+CAL+FES+NAV+PLB"] = ["LAG", "CAL", "FES", "NAV", "PLB"]   # 지역 섞은 위약

    dlb_cols = [c for c in blocks["DLB"] if c != "dlb_staleness_days"]
    coverage = float(test[dlb_cols].notna().any(axis=1).mean() * 100)
    stale = test["dlb_staleness_days"]
    print(f"데이터랩 결합 점검 · 테스트 행 중 값이 있는 비율 {coverage:.1f}% · "
          f"자료 나이(대상일 - 해당 월 1일) {stale.min():.0f}~{stale.max():.0f}일 "
          f"(중앙값 {stale.median():.0f}일)")
    print(f"h={horizon} · 학습 {len(fit_frame):,}행 · 테스트 {len(test):,}행 "
          f"({test['region_id'].nunique()}지역) · 씨앗 {n_seeds}개")
    print("블록 변수 수: " + ", ".join(f"{k} {len(v)}" for k, v in blocks.items()))

    results = {}
    seen = {}
    for label, names in configs.items():
        key = tuple(sorted(names))
        if key in seen:
            results[label] = dict(results[seen[key]], same_as=seen[key])
            test[label] = test[seen[key]]
            print(f"  {label:<28} = {seen[key]} (같은 구성)")
            continue
        seen[key] = label
        columns = [c for name in names for c in blocks[name]]
        preds = np.column_stack([fit_predict(fit_frame, test, columns, seed) for seed in range(n_seeds)])
        test[label] = preds.mean(axis=1)
        per_seed = [smape(test[TARGET].to_numpy(), preds[:, i]) for i in range(n_seeds)]
        results[label] = {
            "blocks": names,
            "n_features": len(columns),
            "smape": round(smape(test[TARGET].to_numpy(), test[label].to_numpy()), 3),
            "mae": round(float(np.mean(np.abs(test[TARGET] - test[label]))), 1),
            "smape_per_seed": [round(v, 3) for v in per_seed],
            "seed_spread": round(max(per_seed) - min(per_seed), 3),
        }
        print(f"  {label:<28} sMAPE {results[label]['smape']:>6.3f}  "
              f"(씨앗별 {min(per_seed):.3f}~{max(per_seed):.3f})")

    comparisons = []
    pairs = [("LAG", "LAG+CAL", "달력 추가"),
             ("LAG+CAL", "LAG+CAL+FES", "축제 추가"),
             ("LAG+CAL+FES", "LAG+CAL+FES+NAV", "네이버 검색 추가"),
             ("LAG+CAL+FES+NAV", "LAG+CAL+FES+NAV+DLB", "데이터랩 월간 추가"),
             ("LAG+CAL+FES+NAV+DLB", full_label, "과거 날씨 추가")]
    pairs += [(f"FULL-{n}", full_label, f"전체에서 {n} 뺀 것 대비 복원")
              for n in ["NAV", "DLB", "WXP", "FES", "CAL"]]
    pairs += [("LAG+CAL+FES+NAV", "LAG+CAL+FES+NAV+DLX", "데이터랩(방문자계열 제외) 추가"),
              ("LAG+CAL+FES+NAV", "LAG+CAL+FES+NAV+PLB", "위약: 지역 섞은 데이터랩"),
              ("LAG+CAL+FES+NAV+PLB", "LAG+CAL+FES+NAV+DLB", "진짜 데이터랩 - 위약 (순수 신호분)"),
              ("LAG+CAL+FES+NAV+PLB", "LAG+CAL+FES+NAV+DLX", "방문자계열 제외 - 위약"),
              (full_label, full_label + "+WX0", "당일 실측 날씨(상한·운영불가)")]
    for base_label, other_label, note in pairs:
        if base_label not in test.columns or other_label not in test.columns:
            continue
        base_r, other_r = region_smape(test, base_label), region_smape(test, other_label)
        low, high = paired_bootstrap(base_r, other_r)
        noise = max(results[base_label]["seed_spread"], results[other_label]["seed_spread"])
        gap = results[other_label]["smape"] - results[base_label]["smape"]
        verdict = "개선" if high < 0 else ("악화" if low > 0 else "차이 없음")
        if verdict == "개선" and abs(gap) < noise:
            verdict = "개선(잡음 수준)"
        comparisons.append({
            "비교": note, "기준": base_label, "대상": other_label,
            "sMAPE_차이": round(gap, 3),
            "지역평균차이_95CI": [round(low, 3), round(high, 3)],
            "지역승률_pct": round(float((other_r < base_r).mean() * 100), 1),
            "씨앗잡음": round(noise, 3),
            "판정": verdict,
        })

    print("\n블록별 기여 판정 (음수 = 오차 감소 = 개선 · 95% 구간이 0을 걸치면 '차이 없음')")
    print(f"{'비교':<30}{'sMAPE차':>9}{'95%구간':>20}{'지역승률':>10}{'씨앗잡음':>9}  판정")
    for c in comparisons:
        ci = f"[{c['지역평균차이_95CI'][0]:+.3f}, {c['지역평균차이_95CI'][1]:+.3f}]"
        print(f"{c['비교']:<30}{c['sMAPE_차이']:>+9.3f}{ci:>20}"
              f"{c['지역승률_pct']:>9.1f}%{c['씨앗잡음']:>9.3f}  {c['판정']}")

    summary = {"horizon": horizon, "seeds": n_seeds, "test_rows": int(len(test)),
               "test_regions": int(test["region_id"].nunique()),
               "block_sizes": {k: len(v) for k, v in blocks.items()},
               "results": results, "comparisons": comparisons}
    (INTERIM / f"ablation_h{horizon}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    keep = ["region_id", "region_name", "observed_date", TARGET] + list(configs)
    test[keep].to_csv(INTERIM / f"ablation_predictions_h{horizon}.csv", index=False, encoding="utf-8")
    print(f"\n출력: data/interim/ablation_h{horizon}.json · ablation_predictions_h{horizon}.csv")


if __name__ == "__main__":
    main()
