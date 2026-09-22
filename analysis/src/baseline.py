"""기준선 예측과 평가 틀 — "모델이 이걸 이기는가"를 재는 자.

예측 문제 정의
    예측 시점 t에 서서 t+h일의 외지인 방문자수를 맞힌다 (기본 h=7).
    이때 쓸 수 있는 정보는 docs/분석_누출점검표.md 규칙을 따른다:
      - 방문자수: 4일 지연 공개 → d-h-4 이전 값만
      - 네이버 검색: 전일까지 → d-h-1 이전 값만
      - 달력·축제: 미리 공표되므로 예측 대상일(d)의 값을 그대로 써도 된다

사다리 — 변수를 한 층씩 올리며 개선폭을 잰다 (각 층이 체크리스트의 하루에 대응)
    B1 작년같은요일    : 364일 전 같은 요일 값 (계절성만)
    B2 최근4주같은요일 : 쓸 수 있는 같은 요일 4개 평균
    B3 달력           : 방문자 시차 + 요일·월·주말·공휴일·연휴길이 (부스팅)
    M1 달력+축제+날씨  : B3 + 축제 전후 플래그 + 기온·강수·풍속 (9/24)
    M2 +검색          : M1 + 네이버 검색 시차·이동평균 (9/25) ← 검색의 기여가 여기서 드러난다

    B3→M1, M1→M2 개선폭이 서식4에 들어갈 숫자다. 날씨가 없는 79개 지역은 결측으로 두고
    부스팅 모델이 결측을 그대로 처리하게 한다(버리지 않는다).

평가
    Train 2023-01-01~2024-12-31 / Valid 2025 / Test 2026-01-01~2026-08-14 (시간 순, 랜덤 분할 없음)
    MAE·sMAPE를 전체와 지역별로 낸다. 큰 지역이 평균을 지배하지 않도록 지역별 중앙값도 함께 본다.

사용법:
    uv run python analysis/src/baseline.py            # h=7
    uv run python analysis/src/baseline.py --horizon 1
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
ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"

TARGET = "visitors_external"
VISITOR_DELAY = 4   # 이동통신 일별 자료는 4일 지연 공개
NAVER_DELAY = 1     # 네이버 검색지수는 전일까지 조회 가능
SPLITS = {
    "train": ("2023-01-01", "2024-12-31"),
    "valid": ("2025-01-01", "2025-12-31"),
    "test": ("2026-01-01", "2026-08-14"),
}


def lagged(frame: pd.DataFrame, column: str, days: int) -> pd.Series:
    return frame.groupby("region_id")[column].shift(days)


def rolling_mean(frame: pd.DataFrame, column: str, days: int, window: int) -> pd.Series:
    shifted = frame.groupby("region_id")[column].shift(days)
    return shifted.groupby(frame["region_id"]).transform(lambda s: s.rolling(window, min_periods=window).mean())


def build_features(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """예측 대상일 d의 행에, 예측 시점(d-horizon)까지만 알 수 있는 값으로 특징을 만든다."""
    frame = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True).copy()
    visit_cut = horizon + VISITOR_DELAY   # d 기준으로 방문자를 알 수 있는 최소 시차
    naver_cut = horizon + NAVER_DELAY

    # 같은 요일 값 중 예측 시점에 이미 알려진 것들 (7의 배수 중 visit_cut 이상)
    weekday_lags = [lag for lag in (7, 14, 21, 28, 35) if lag >= visit_cut][:4]

    features = pd.DataFrame(index=frame.index)
    features["vis_last"] = lagged(frame, TARGET, visit_cut)
    features["vis_prev"] = lagged(frame, TARGET, visit_cut + 1)
    features["vis_mean7"] = rolling_mean(frame, TARGET, visit_cut, 7)
    features["vis_mean28"] = rolling_mean(frame, TARGET, visit_cut, 28)
    for lag in weekday_lags:
        features[f"vis_wd{lag}"] = lagged(frame, TARGET, lag)
    features["vis_wd_mean"] = features[[f"vis_wd{lag}" for lag in weekday_lags]].mean(axis=1)
    features["vis_year"] = lagged(frame, TARGET, 364)
    features["vis_year_prev_week"] = lagged(frame, TARGET, 371)
    features["naver_last"] = lagged(frame, "naver_interest", naver_cut)
    features["naver_mean7"] = rolling_mean(frame, "naver_interest", naver_cut, 7)
    features["naver_mean28"] = rolling_mean(frame, "naver_interest", naver_cut, 28)
    # 검색은 지역마다 수준이 달라 절대값보다 '평소 대비 몇 배인가'가 신호에 가깝다
    features["naver_ratio_7_28"] = features["naver_mean7"] / features["naver_mean28"]
    features["naver_jump"] = features["naver_last"] / features["naver_mean28"]
    features["naver_year_ratio"] = features["naver_mean7"] / rolling_mean(frame, "naver_interest", naver_cut + 364, 7)

    # 달력·축제는 미리 공표되므로 예측 대상일(d)의 값을 그대로 쓴다.
    # 날씨는 예측 시점에 알 수 없다 — 상한 모델에서만 쓰고 운영 모델에서는 뺀다 (누출 점검표)
    for column in ("day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                   "rest_run_length", "festival_active", "festival_pre", "festival_post",
                   "avg_temperature_c", "min_temperature_c", "max_temperature_c",
                   "precipitation_mm", "max_wind_speed_ms", "weather_available"):
        features[column] = frame[column].astype(float)

    keys = frame[["region_id", "region_name", "observed_date", TARGET]]
    return pd.concat([keys, features], axis=1)


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    denominator = (np.abs(actual) + np.abs(predicted)) / 2
    ratio = np.where(denominator == 0, 0.0, np.abs(actual - predicted) / np.where(denominator == 0, 1, denominator))
    return float(np.mean(ratio) * 100)


def score(frame: pd.DataFrame, prediction: str) -> dict:
    valid = frame[frame[prediction].notna()]
    per_region = valid.groupby("region_id").apply(
        lambda g: pd.Series({"mae": float(np.mean(np.abs(g[TARGET] - g[prediction]))),
                             "smape": smape(g[TARGET].to_numpy(), g[prediction].to_numpy())}),
        include_groups=False)
    return {
        "rows": int(len(valid)),
        "mae": round(float(np.mean(np.abs(valid[TARGET] - valid[prediction]))), 1),
        "smape": round(smape(valid[TARGET].to_numpy(), valid[prediction].to_numpy()), 2),
        "smape_region_median": round(float(per_region["smape"].median()), 2),
        "smape_region_p90": round(float(per_region["smape"].quantile(0.9)), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=7, help="며칠 뒤를 예측하는가 (기본 7)")
    args = parser.parse_args()
    horizon = args.horizon

    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    data = build_features(panel, horizon)

    def slice_split(name: str) -> pd.DataFrame:
        start, end = SPLITS[name]
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)]

    train, valid, test = (slice_split(name) for name in ("train", "valid", "test"))

    # B1·B2는 학습이 필요 없는 규칙 기반이다
    for part in (train, valid, test):
        part["B1_작년같은요일"] = part["vis_year"]
        part["B2_최근4주같은요일"] = part["vis_wd_mean"]

    lag_features = [c for c in data.columns if c.startswith("vis_")]
    calendar_features = ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday", "rest_run_length"]
    festival_features = ["festival_active", "festival_pre", "festival_post"]
    weather_features = ["avg_temperature_c", "min_temperature_c", "max_temperature_c",
                        "precipitation_mm", "max_wind_speed_ms", "weather_available"]
    naver_features = ["naver_last", "naver_mean7", "naver_mean28", "naver_ratio_7_28", "naver_jump", "naver_year_ratio"]

    # 운영 모델 3층(날씨 없음) + 상한 모델 1층(그날 실측 날씨 포함)
    ladder = {
        "B3_달력": lag_features + calendar_features,
        "M1_축제추가": lag_features + calendar_features + festival_features,
        "M2_검색추가": lag_features + calendar_features + festival_features + naver_features,
        "M3_날씨포함_상한": lag_features + calendar_features + festival_features + naver_features + weather_features,
    }

    test = test.copy()
    fit_pool = pd.concat([train, valid])
    # 시차 변수가 없는 초기 구간만 버린다. 날씨 결측은 부스팅이 그대로 처리한다
    fit_frame = fit_pool.dropna(subset=lag_features + [TARGET])
    ready = test[lag_features].notna().all(axis=1)
    for name, columns in ladder.items():
        model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.06,
                                              early_stopping=True, validation_fraction=0.15, random_state=0)
        model.fit(fit_frame[columns], np.log1p(fit_frame[TARGET]))
        test[name] = np.nan
        test.loc[ready, name] = np.expm1(model.predict(test.loc[ready, columns]))

    names = ["B1_작년같은요일", "B2_최근4주같은요일", *ladder]
    results = {name: score(test, name) for name in names}
    best = min(results, key=lambda k: results[k]["smape"])
    feature_columns = ladder["M2_검색추가"]

    # 층 사이 개선폭 — 이 숫자가 서식4에 들어간다
    steps = [("B1_작년같은요일", "B3_달력"), ("B3_달력", "M1_축제추가"),
             ("M1_축제추가", "M2_검색추가"), ("M2_검색추가", "M3_날씨포함_상한")]
    improvements = {
        f"{before} → {after}": round(100 * (results[before]["smape"] - results[after]["smape"]) / results[before]["smape"], 1)
        for before, after in steps
    }

    summary = {
        "horizon_days": horizon,
        "target": TARGET,
        "visitor_delay_days": VISITOR_DELAY,
        "naver_delay_days": NAVER_DELAY,
        "weekday_lags_used": [c for c in feature_columns if c.startswith("vis_wd") and c != "vis_wd_mean"],
        "splits": SPLITS,
        "train_rows": int(len(fit_frame)),
        "test_rows": int(len(test)),
        "test_regions": int(test["region_id"].nunique()),
        "results": results,
        "improvement_pct": improvements,
        "best": best,
    }
    (INTERIM / f"baseline_h{horizon}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    test[["region_id", "region_name", "observed_date", TARGET, *names]].to_csv(
        INTERIM / f"baseline_predictions_h{horizon}.csv", index=False, encoding="utf-8")

    print(f"예측 문제: {horizon}일 뒤 {TARGET} · 방문자 {VISITOR_DELAY}일 지연, 검색 {NAVER_DELAY}일 지연 반영")
    print(f"같은 요일 시차로 쓴 값: {summary['weekday_lags_used']}")
    print(f"학습 {len(fit_frame):,}행 / 검증기간 테스트 {len(test):,}행 ({test['region_id'].nunique()}지역, "
          f"{SPLITS['test'][0]}~{SPLITS['test'][1]})\n")
    header = f"{'모델':<18}{'MAE':>10}{'sMAPE':>9}{'지역중앙값':>11}{'지역90%':>9}"
    print(header)
    for name, value in results.items():
        print(f"{name:<18}{value['mae']:>10,.0f}{value['smape']:>9.2f}{value['smape_region_median']:>11.2f}{value['smape_region_p90']:>9.2f}")
    print("\n층 사이 개선폭 (sMAPE 기준)")
    for step, value in improvements.items():
        print(f"  {step:<34}{value:>6.1f}%")
    print(f"\n가장 좋은 모델: {best} (sMAPE {results[best]['smape']}%)")
    print(f"출력: data/interim/baseline_h{horizon}.json, baseline_predictions_h{horizon}.csv")


if __name__ == "__main__":
    main()
