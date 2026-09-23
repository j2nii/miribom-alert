"""모델 계열 비교 — 어떤 방식이 이 데이터에 맞는가.

`baseline.py`가 만든 특징(누출 규칙 반영)을 그대로 쓰고, 학습 방식만 바꿔 가며 비교한다.
비교 대상은 세 갈래다.

전역 모델 (228개 지역을 한 모델로)
    Ridge          선형 회귀. 해석이 쉽고 과적합이 적다 — 부스팅이 정말 필요한지 보는 잣대
    GBM(제곱오차)   기본 부스팅 (baseline.py의 M1과 같다)
    GBM(포아송)     방문자수는 0 이상 정수라 포아송 손실이 이론상 더 맞다
    GBM(절대오차)   큰 급증일에 덜 끌려간다 — 평상시 성능이 좋아질 수 있다

지역별 모델 (지역마다 따로 학습)
    사례 6개 지역에 대해 전역 모델과 맞대결한다. 지역별로 따로 배우는 게 나은지 확인한다

고전 시계열 (사례 지역만)
    ETS(지수평활)   추세·주간 계절성을 직접 모형화
    SARIMAX        주간 계절성 ARIMA. 달력 변수를 외생변수로 넣는다

사용법:
    uv run python analysis/src/forecast/models.py
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baseline import SPLITS, TARGET, build_features, score, smape  # noqa: E402

INTERIM = ROOT / "data" / "interim"
HORIZON = 7
CASE_REGIONS = {"51750": "영월", "48310": "거제", "12130": "여수", "47940": "울릉", "51210": "속초", "51810": "인제"}


def gbm(loss: str = "squared_error", **kwargs) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(loss=loss, max_iter=400, learning_rate=0.06,
                                         early_stopping=True, validation_fraction=0.15,
                                         random_state=0, **kwargs)


def fit_predict(model, fit_frame: pd.DataFrame, test: pd.DataFrame, columns: list[str],
                log_target: bool, log_features: bool = False) -> np.ndarray:
    """log_features: 선형 모델에는 규모 차이가 큰 변수(방문자·검색)를 로그로 넣어야 공정하다."""
    def matrix(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame[columns].copy()
        if log_features:
            scale_columns = [c for c in columns if c.startswith(("vis_", "naver_"))]
            out[scale_columns] = np.log1p(out[scale_columns].clip(lower=0))
        return out

    target = np.log1p(fit_frame[TARGET]) if log_target else fit_frame[TARGET]
    model.fit(matrix(fit_frame), target)
    prediction = model.predict(matrix(test))
    return np.expm1(prediction) if log_target else prediction


def classical_rolling(series: pd.Series, test_dates: pd.DatetimeIndex, kind: str,
                      horizon: int = HORIZON, delay: int = 4) -> pd.Series:
    """고전 시계열도 GBM과 같은 조건에서 잰다.

    7일마다 시점을 옮겨 가며 그때까지의 자료(방문자 4일 지연 반영)로 다시 적합하고,
    horizon일 뒤 하루를 예측한다. 테스트 구간을 한 번에 예측하면 불리해서 비교가 성립하지 않는다.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    daily = series.asfreq("D").interpolate()
    predictions = {}
    origins = pd.date_range(test_dates.min() - pd.Timedelta(days=horizon), test_dates.max(), freq="7D")
    for origin in origins:
        target_date = origin + pd.Timedelta(days=horizon)
        if target_date not in set(test_dates):
            continue
        history = np.log1p(daily.loc[:origin - pd.Timedelta(days=delay)])
        if len(history) < 400:
            continue
        steps = horizon + delay
        if kind == "ETS":
            fitted = ExponentialSmoothing(history, trend="add", seasonal="add", seasonal_periods=7).fit(optimized=True)
        else:
            fitted = SARIMAX(history, order=(1, 1, 1), seasonal_order=(1, 0, 1, 7),
                             enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        predictions[target_date] = float(np.expm1(fitted.forecast(steps).iloc[-1]))
    return pd.Series(predictions)


def main() -> None:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    data = build_features(panel, HORIZON)

    def part(name: str) -> pd.DataFrame:
        start, end = SPLITS[name]
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)].copy()

    train, valid, test = part("train"), part("valid"), part("test")
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    calendar_features = ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday", "rest_run_length"]
    festival_features = ["festival_active", "festival_pre", "festival_post"]
    columns = lag_features + calendar_features + festival_features   # 운영 모델 변수(날씨·검색 제외)

    fit_frame = pd.concat([train, valid]).dropna(subset=lag_features + [TARGET])
    ready = test[lag_features].notna().all(axis=1)
    test = test[ready].copy()

    print(f"학습 {len(fit_frame):,}행 · 테스트 {len(test):,}행 ({test['region_id'].nunique()}지역, {HORIZON}일 앞)\n")

    global_models = {
        "Ridge_선형": (make_pipeline(StandardScaler(), Ridge(alpha=1.0)), True, True),
        "GBM_제곱오차": (gbm(), True, False),
        "GBM_포아송": (gbm(loss="poisson"), False, False),
        "GBM_절대오차": (gbm(loss="absolute_error"), True, False),
    }
    results = {}
    for name, (model, log_target, log_features) in global_models.items():
        test[name] = fit_predict(model, fit_frame, test, columns, log_target, log_features)
        results[name] = score(test, name)
        print(f"  {name:<14} sMAPE {results[name]['smape']:6.2f}  MAE {results[name]['mae']:>9,.0f}")

    # 지역별 모델 — 사례 6곳에서 전역 모델과 맞대결
    print("\n지역별 모델 vs 전역 모델 (사례 지역, sMAPE)")
    per_region_rows = []
    for region, label in CASE_REGIONS.items():
        region_fit = fit_frame[fit_frame["region_id"] == region]
        region_test = test[test["region_id"] == region]
        if len(region_fit) < 400 or region_test.empty:
            continue
        local = gbm()
        local.fit(region_fit[columns], np.log1p(region_fit[TARGET]))
        local_prediction = np.expm1(local.predict(region_test[columns]))
        actual = region_test[TARGET].to_numpy()
        per_region_rows.append({
            "region": label,
            "전역_GBM": round(smape(actual, region_test["GBM_제곱오차"].to_numpy()), 2),
            "지역별_GBM": round(smape(actual, local_prediction), 2),
        })
    per_region = pd.DataFrame(per_region_rows)
    print(per_region.to_string(index=False))

    # 고전 시계열 — 사례 지역만. GBM과 같은 조건(7일마다 재적합, 7일 앞 하루)으로 잰다
    print("\n고전 시계열 (사례 지역, sMAPE · 7일마다 재적합한 7일 앞 예측)")
    classical_rows = []
    for region, label in CASE_REGIONS.items():
        series = panel[panel["region_id"] == region].set_index("observed_date")[TARGET].astype(float)
        region_test = test[test["region_id"] == region].set_index("observed_date")
        if region_test.empty:
            continue
        row = {"region": label}
        for kind in ("ETS", "SARIMAX"):
            try:
                forecast = classical_rolling(series, pd.DatetimeIndex(region_test.index), kind)
                shared = region_test.index.intersection(forecast.index)
                row[kind] = round(smape(region_test.loc[shared, TARGET].to_numpy(), forecast.loc[shared].to_numpy()), 2)
                row["비교일수"] = len(shared)
                row["전역_GBM"] = round(smape(region_test.loc[shared, TARGET].to_numpy(),
                                            region_test.loc[shared, "GBM_제곱오차"].to_numpy()), 2)
            except Exception as error:  # 수렴 실패도 결과다
                row[kind] = f"실패({type(error).__name__})"
        classical_rows.append(row)
    classical = pd.DataFrame(classical_rows)
    print(classical.to_string(index=False))

    summary = {
        "horizon_days": HORIZON,
        "features": {"lag": len(lag_features), "calendar": len(calendar_features), "festival": len(festival_features)},
        "global_models": results,
        "per_region_vs_global": per_region_rows,
        "classical": classical.to_dict("records"),
    }
    (INTERIM / "model_comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                                   encoding="utf-8")
    best = min(results, key=lambda k: results[k]["smape"])
    print(f"\n전역 모델 중 최고: {best} (sMAPE {results[best]['smape']}%)")
    print("출력: data/interim/model_comparison.json")


if __name__ == "__main__":
    main()
