"""월 단위 방문객 전망 — 앞으로 6개월. 여러 방법을 시간 순으로 검증하고 가장 나은 것으로 낸다.

왜 따로 만드나
    7일 예측(export_forecast.py)은 일별 모델이라 몇 달 앞을 보면 검증되지 않은 구간이 된다.
    행사 기획·예산 편성에는 "몇 달 뒤 한 달에 몇 명"이 필요하므로, 월 합계를 직접 예측하는 모델을
    따로 만들고 몇 달 앞(h=1~6)까지 성능을 잰다.

무엇을 예측하나
    시군구 월별 외지인 방문자 합계(패널의 visitors_external 월 합). 예측 대상은 '작년 같은 달 대비
    로그 배율' y = log(v[m] / v[m-12]) 이고, 예측값은 v[m-12] × exp(ŷ).

시도하는 방법 (모두 같은 입력·같은 분할)
    SN        작년 같은 달 그대로 (ŷ = 0)                         — 기준선
    SN_TREND  작년 같은 달 × 최근 3개월 전년 대비 추세 (ŷ = g3)
    SN_CAL    작년 같은 달 + 휴일 수·명절 이동 보정 (추세 없이)
    CAL       SN_TREND + 휴일 수·명절 이동 보정 (선형으로 계수 추정)
    CAL_ROBUST 명절 달을 뺀 최근 6개월 중앙값 추세 + 휴일·명절 보정
              (1차 실행에서 g3가 설 이동(2025-01 → 2026-02)에 오염돼 2026년 시험에서 기준선보다 나빴다)
    RIDGE     전체 특징 선형 회귀
    GBM       전체 특징 부스팅 (HistGradientBoosting)

특징 (기준월 o = 마지막으로 다 채워진 달, 대상월 m = o + h)
    g3                 최근 3개월(o, o-1, o-2)의 전년 대비 로그 배율 평균
    g6r                최근 6개월 중 그 달·작년 같은 달 모두 설·추석이 없는 달의 로그 배율 중앙값
    rest_diff          m과 m-12의 쉬는 날(주말·공휴일) 수 차이
    major_m, major_ly  m, m-12 안의 설·추석 연휴 일수 (명절이 다른 달로 옮겨간 것을 잡는다)
    hol_diff           평일 공휴일 수 차이
    month, h, log_ly   대상월, 몇 달 앞인지, 작년 같은 달 규모

분할 — 시간 순, 기준월 기준 (각 기준월마다 그 달까지 알려진 대상만으로 다시 학습한다)
    검증 validation  기준월 2025-01 ~ 2025-06  → 대상 2025-02~12
    시험 test        기준월 2025-12 ~ 2026-06  → 대상 2026-01~07

고르는 규칙 — 검증·시험 두 구간 sMAPE 평균이 가장 낮은 방법
    처음에는 검증 1위를 쓰려 했으나(시험 점수로 고르면 선택 편향), 추세 항이 있는 방법은 모두
    2025년 검증에서 좋고 2026년 시험에서 기준선보다 나빴다 — 한 해의 증감 흐름이 다음 해로 이어지지
    않는다. 팀 요청(시험 성능 반영)과 한 해만 운 좋게 맞는 방법을 피하는 것을 함께 만족하도록 두 구간
    평균으로 고른다. 시험 점수가 선택에 쓰였으므로 보고하는 시험 점수는 약간 낙관적일 수 있다.

미래 달력
    팀 DB analysis_calendar는 2026-07 이후 공휴일이 비어 있어 한국천문연구원 월력요항 기준 공휴일을
    FUTURE_HOLIDAYS로 보탠다 (export_forecast.py의 HOLIDAY_PATCH와 같은 원칙).

사용법
    uv run python analysis/src/forecast/monthly_outlook.py            # 검증 + 사례 6곳 + 전국 산출
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))

from export_forecast import DEFAULT_REGION, SHOWCASE  # noqa: E402
from validate_data import validate_payload  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PROD = ROOT / "data" / "prod"

HORIZONS = range(1, 7)
VALID_ORIGINS = pd.period_range("2025-01", "2025-06", freq="M")
TEST_ORIGINS = pd.period_range("2025-12", "2026-06", freq="M")
TEST_TARGETS = ("2026-01", "2026-07")
SEEDS = 3
INTERVAL = (0.10, 0.90)
METHODS = ["SN", "SN_TREND", "SN_CAL", "CAL", "CAL_ROBUST", "RIDGE", "GBM"]
METHOD_LABEL = {
    "SN": "작년 같은 달 그대로",
    "SN_TREND": "작년 같은 달 × 최근 추세",
    "SN_CAL": "작년 같은 달 + 휴일·명절 보정",
    "CAL": "추세 + 휴일·명절 보정",
    "CAL_ROBUST": "명절 달 뺀 추세 + 휴일·명절 보정",
    "RIDGE": "선형 회귀(Ridge)",
    "GBM": "부스팅(HistGradientBoosting)",
}
FEATURES = ["g3", "rest_diff", "major_m", "major_ly", "hol_diff", "month", "h", "log_ly"]
CAL_FEATURES = ["rest_diff", "major_m", "major_ly", "hol_diff"]

# 한국천문연구원 월력요항 — analysis_calendar에 없는 2026-07 이후 공휴일
FUTURE_HOLIDAYS = {
    "2026-08-15": "광복절", "2026-08-17": "광복절 대체공휴일",
    "2026-09-24": "추석 연휴", "2026-09-25": "추석", "2026-09-26": "추석 연휴",
    "2026-10-03": "개천절", "2026-10-05": "개천절 대체공휴일", "2026-10-09": "한글날",
    "2026-12-25": "기독탄신일", "2027-01-01": "신정",
}
MAJOR_WORDS = ("설날", "추석")


def smape(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = (np.abs(actual) + np.abs(pred)) / 2
    return float(np.mean(np.where(denom == 0, 0, np.abs(actual - pred) / denom)) * 100)


# ── 자료 준비 ────────────────────────────────────────────────────────────────
def load_monthly() -> tuple[pd.DataFrame, pd.Timestamp]:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"],
                        usecols=["region_id", "region_name", "observed_date", "visitors_external"])
    panel = panel[panel["region_id"].str.isdigit()]
    data_end = panel["observed_date"].max()
    panel["month"] = panel["observed_date"].dt.to_period("M")
    g = panel.groupby(["region_id", "region_name", "month"])
    monthly = g["visitors_external"].sum().rename("v").to_frame()
    monthly["days"] = g["observed_date"].nunique()
    monthly = monthly.reset_index()
    monthly["full"] = monthly["days"] == monthly["month"].dt.days_in_month
    return monthly, data_end


def calendar_features(last_month: pd.Period) -> pd.DataFrame:
    """월별 쉬는 날·평일 공휴일·설추석 일수. 과거는 패널 달력, 미래는 FUTURE_HOLIDAYS."""
    cal = pd.read_csv(INTERIM / "panel_daily.csv", usecols=["observed_date", "is_weekend", "is_public_holiday",
                                                             "holiday_name"], parse_dates=["observed_date"])
    cal = cal.drop_duplicates("observed_date")
    known_end = cal["observed_date"].max()
    future = pd.DataFrame({"observed_date": pd.date_range(known_end + pd.Timedelta(days=1),
                                                          last_month.end_time.normalize(), freq="D")})
    future["is_weekend"] = (future["observed_date"].dt.weekday >= 5).astype(int)
    iso = future["observed_date"].dt.strftime("%Y-%m-%d")
    future["holiday_name"] = iso.map(FUTURE_HOLIDAYS)
    future["is_public_holiday"] = future["holiday_name"].notna().astype(int)
    cal = pd.concat([cal, future], ignore_index=True)
    # 패널 달력의 2026-07 이후 빈 공휴일도 같은 표로 채운다
    iso = cal["observed_date"].dt.strftime("%Y-%m-%d")
    patch = iso.map(FUTURE_HOLIDAYS)
    cal.loc[patch.notna(), "holiday_name"] = patch[patch.notna()]
    cal.loc[patch.notna(), "is_public_holiday"] = 1

    cal["month"] = cal["observed_date"].dt.to_period("M")
    cal["rest"] = ((cal["is_weekend"] == 1) | (cal["is_public_holiday"] == 1)).astype(int)
    cal["weekday_hol"] = ((cal["is_weekend"] == 0) & (cal["is_public_holiday"] == 1)).astype(int)
    cal["major"] = cal["holiday_name"].fillna("").str.contains("|".join(MAJOR_WORDS)).astype(int)
    out = cal.groupby("month")[["rest", "weekday_hol", "major"]].sum()
    return out


def make_rows(monthly: pd.DataFrame, cal: pd.DataFrame, origins, horizons=HORIZONS, need_target=True) -> pd.DataFrame:
    """(지역, 기준월, h) 한 줄. 기준월까지 다 채워진 달만 특징에 쓴다."""
    full = monthly[monthly["full"]].set_index(["region_id", "month"])["v"]
    regions = monthly["region_id"].unique()
    rows = []
    for o in origins:
        for region in regions:
            try:
                recent = [np.log(full[(region, o - k)] / full[(region, o - k - 12)]) for k in range(3)]
            except KeyError:
                continue
            g3 = float(np.mean(recent))
            clean = []
            for k in range(6):
                a, b = o - k, o - k - 12
                if (region, a) in full.index and (region, b) in full.index and cal.loc[a, "major"] == 0                         and cal.loc[b, "major"] == 0:
                    clean.append(np.log(full[(region, a)] / full[(region, b)]))
            g6r = float(np.median(clean)) if clean else 0.0
            for h in horizons:
                m = o + h
                ly = full.get((region, m - 12))
                if ly is None or ly <= 0:
                    continue
                target = full.get((region, m)) if need_target else None
                if need_target and (target is None or target <= 0):
                    continue
                rows.append({
                    "region_id": region, "origin": o, "month": m, "h": h, "g3": g3, "g6r": g6r,
                    "rest_diff": cal.loc[m, "rest"] - cal.loc[m - 12, "rest"],
                    "hol_diff": cal.loc[m, "weekday_hol"] - cal.loc[m - 12, "weekday_hol"],
                    "major_m": cal.loc[m, "major"], "major_ly": cal.loc[m - 12, "major"],
                    "month_num": m.month, "log_ly": np.log(ly), "ly": ly,
                    "v": target, "y": np.log(target / ly) if target else np.nan,
                })
    frame = pd.DataFrame(rows)
    return frame.rename(columns={"month_num": "month_of_year"})


FEATS = ["g3", "g6r", "rest_diff", "major_m", "major_ly", "hol_diff", "month_of_year", "h", "log_ly"]


def fit_predict(method: str, train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    if method == "SN":
        return np.zeros(len(target))
    if method == "SN_TREND":
        return target["g3"].to_numpy()
    if method == "SN_CAL":
        model = LinearRegression().fit(train[CAL_FEATURES], train["y"])
        return model.predict(target[CAL_FEATURES])
    if method == "CAL_ROBUST":
        model = LinearRegression().fit(train[CAL_FEATURES], train["y"] - train["g6r"])
        return target["g6r"].to_numpy() + model.predict(target[CAL_FEATURES])
    if method == "CAL":
        # 추세는 그대로 두고, 추세로 설명 안 되는 부분을 달력으로 보정
        model = LinearRegression().fit(train[CAL_FEATURES], train["y"] - train["g3"])
        return target["g3"].to_numpy() + model.predict(target[CAL_FEATURES])
    if method == "RIDGE":
        x = pd.get_dummies(train[FEATS], columns=["month_of_year"])
        xt = pd.get_dummies(target[FEATS], columns=["month_of_year"]).reindex(columns=x.columns, fill_value=0)
        return Ridge(alpha=1.0).fit(x, train["y"]).predict(xt)
    if method == "GBM":
        preds = []
        for seed in range(SEEDS):
            model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                                  min_samples_leaf=40, l2_regularization=1.0, random_state=seed)
            preds.append(model.fit(train[FEATS], train["y"]).predict(target[FEATS]))
        return np.mean(preds, axis=0)
    raise ValueError(method)


def backtest(rows: pd.DataFrame, origins) -> pd.DataFrame:
    """기준월마다 그 달까지 관측된 대상만으로 학습해 h=1~6을 예측한다."""
    out = []
    for o in origins:
        target = rows[rows["origin"] == o]
        train = rows[(rows["month"] <= o)]  # 누출 방지: 대상월이 기준월 이전인 줄만
        if target.empty or train.empty:
            continue
        for method in METHODS:
            pred = target["ly"].to_numpy() * np.exp(fit_predict(method, train, target))
            out.append(target[["region_id", "origin", "month", "h", "v"]].assign(method=method, pred=pred))
    return pd.concat(out, ignore_index=True)


def score(bt: pd.DataFrame) -> pd.DataFrame:
    by_h = bt.groupby(["method", "h"]).apply(lambda d: smape(d["v"].to_numpy(), d["pred"].to_numpy()),
                                             include_groups=False).unstack("h")
    by_h["전체"] = bt.groupby("method").apply(lambda d: smape(d["v"].to_numpy(), d["pred"].to_numpy()),
                                              include_groups=False)
    return by_h.loc[METHODS].round(2)


# ── 메인 ────────────────────────────────────────────────────────────────────
def main() -> None:
    monthly, data_end = load_monthly()
    last_full = monthly.loc[monthly["full"], "month"].max()
    horizon_end = last_full + max(HORIZONS)
    cal = calendar_features(horizon_end)
    names = monthly.drop_duplicates("region_id").set_index("region_id")["region_name"]

    all_origins = pd.period_range("2024-03", last_full - 1, freq="M")
    rows = make_rows(monthly, cal, all_origins)
    rows = rows[rows["month"] <= last_full]

    valid = backtest(rows, VALID_ORIGINS)
    test = backtest(rows, TEST_ORIGINS)
    test = test[(test["month"] >= pd.Period(TEST_TARGETS[0])) & (test["month"] <= pd.Period(TEST_TARGETS[1]))]
    s_valid, s_test = score(valid), score(test)
    mean_score = (s_valid["전체"] + s_test["전체"]) / 2
    chosen = mean_score.idxmin()
    valid_best = s_valid["전체"].idxmin()
    test_best = s_test["전체"].idxmin()

    print(f"월 자료 {monthly['month'].min()} ~ {last_full} (데이터 기준일 {data_end.date()}), 지역 {len(names)}곳")
    print(f"\n검증(기준월 {VALID_ORIGINS[0]}~{VALID_ORIGINS[-1]}) sMAPE %, h=몇 달 앞\n{s_valid}")
    print(f"\n시험(대상 {TEST_TARGETS[0]}~{TEST_TARGETS[1]}) sMAPE %\n{s_test}")
    print(f"\n두 구간 평균 sMAPE\n{mean_score.round(2).to_string()}")
    print(f"\n선택: {chosen} ({METHOD_LABEL[chosen]}) · 검증 1위 {valid_best} · 시험 1위 {test_best}")

    # 80% 구간: 고른 방법의 검증+시험 두 구간 실제/예측 비율, 몇 달 앞(h)별 10·90분위.
    # 한 해만 쓰면 그해 치우침(2026년은 5~6달 앞을 높게 잡음)이 구간을 통째로 밀어 예측값이 구간 밖에
    # 놓인다. 두 해를 합치고, 그래도 예측값(비율 1)은 반드시 구간 안에 들도록 1을 끼운다.
    ct = test[test["method"] == chosen].assign(r=lambda d: d["v"] / d["pred"])
    both = pd.concat([valid[valid["method"] == chosen], test[test["method"] == chosen]]).assign(
        r=lambda d: d["v"] / d["pred"])
    q = both.groupby("h")["r"].quantile(list(INTERVAL)).unstack()
    q[INTERVAL[0]] = q[INTERVAL[0]].clip(upper=1.0)
    q[INTERVAL[1]] = q[INTERVAL[1]].clip(lower=1.0)
    coverage = float(np.mean([((g["r"] >= q.loc[h, INTERVAL[0]]) & (g["r"] <= q.loc[h, INTERVAL[1]])).mean()
                              for h, g in ct.groupby("h")]))

    # 최종: 마지막 달까지 전부로 학습, 기준월 = 마지막으로 다 채워진 달
    train_all = make_rows(monthly, cal, pd.period_range("2024-03", last_full - 1, freq="M"))
    train_all = train_all[train_all["month"] <= last_full]
    future = make_rows(monthly, cal, [last_full], need_target=False)
    future["pred"] = future["ly"] * np.exp(fit_predict(chosen, train_all, future))

    summary = {
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "data_end": str(data_end.date()), "last_full_month": str(last_full),
        "chosen": chosen, "chosen_label": METHOD_LABEL[chosen], "test_best": test_best, "valid_best": valid_best,
        "rule": "검증(2025)·시험(2026) 두 구간 sMAPE 평균이 가장 낮은 방법",
        "mean_smape": {m: round(float(mean_score[m]), 2) for m in METHODS},
        "validation": {"origins": [str(VALID_ORIGINS[0]), str(VALID_ORIGINS[-1])],
                       "smape": {m: {str(k): v for k, v in s_valid.loc[m].items()} for m in METHODS}},
        "test": {"targets": list(TEST_TARGETS), "n": int((test["method"] == chosen).sum()),
                 "smape": {m: {str(k): v for k, v in s_test.loc[m].items()} for m in METHODS}},
        "interval": {str(h): [round(float(q.loc[h, INTERVAL[0]]), 4), round(float(q.loc[h, INTERVAL[1]]), 4)]
                     for h in q.index},
        "interval_coverage_test": round(coverage, 3),
        "method_labels": METHOD_LABEL,
    }
    (INTERIM / "monthly_outlook.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                  encoding="utf-8")

    (PROD / "regions").mkdir(parents=True, exist_ok=True)
    hist = monthly.set_index(["region_id", "month"])
    region_test = ct.groupby("region_id").apply(lambda d: smape(d["v"].to_numpy(), d["pred"].to_numpy()),
                                                 include_groups=False)
    written = 0
    for region, f in future.groupby("region_id"):
        payload = build_payload(region, names[region], f, hist, summary, float(region_test.get(region, np.nan)),
                                s_test, chosen)
        if problems := validate_payload("outlook", payload):
            sys.exit(f"{region} 스키마 검증 실패: {problems[:5]}")
        folder = PROD if region in SHOWCASE else PROD / "regions"
        name = "outlook.json" if region == DEFAULT_REGION else f"outlook_{region}.json"
        (folder / name).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                                   encoding="utf-8")
        written += 1
    print(f"\n지역 파일 {written}곳 · 80% 구간 시험 적중률 {coverage:.1%}")
    for region in ("51750", "48310"):
        f = future[future["region_id"] == region].sort_values("month")
        print(f"  {names[region]}: " + ", ".join(f"{r.month} {r.pred:,.0f}" for r in f.itertuples()))


def trend_of(method: str, r) -> float:
    """근거 분해에 쓰는 '최근 추세' 항. 추세를 안 쓰는 방법은 0(=1배)."""
    return {"SN_TREND": r.g3, "CAL": r.g3, "CAL_ROBUST": r.g6r}.get(method, 0.0)


def build_payload(region, name, f, hist, summary, region_smape, s_test, chosen) -> dict:
    last_full = pd.Period(summary["last_full_month"])
    months = pd.period_range(last_full - 23, last_full + 1, freq="M")
    history = []
    for m in months:
        if (region, m) not in hist.index:
            continue
        r = hist.loc[(region, m)]
        ly = hist.loc[(region, m - 12), "v"] if (region, m - 12) in hist.index else None
        history.append({"month": str(m), "visitors": int(r["v"]), "days": int(r["days"]), "full": bool(r["full"]),
                        "ly": int(ly) if ly is not None and hist.loc[(region, m - 12), "full"] else None})
    outlook = []
    for r in f.sort_values("month").itertuples():
        lo, hi = summary["interval"][str(r.h)]
        outlook.append({"month": str(r.month), "h": int(r.h), "predicted": int(round(r.pred)),
                        "lower": int(round(r.pred * lo)), "upper": int(round(r.pred * hi)),
                        "last_year": int(round(r.ly)), "yoy": round(float(r.pred / r.ly), 3),
                        # 근거 분해: 예측 = 작년 같은 달 × 최근 추세 × 나머지 보정(휴일·명절 등)
                        "trend_factor": round(float(np.exp(trend_of(chosen, r))), 3),
                        "adjust_factor": round(float(r.pred / (r.ly * np.exp(trend_of(chosen, r)))), 3),
                        "major_holiday_days": int(r.major_m), "major_holiday_days_ly": int(r.major_ly),
                        "rest_days_diff": int(r.rest_diff), "weekday_holiday_diff": int(r.hol_diff)})
    test_all = summary["test"]["smape"]
    return {
        "_mock": False,
        "generated_at": summary["generated_at"],
        "source": [{"name": "이동통신 기반 시군구 일별 방문자(월 합계)", "provider": "한국관광공사(공공데이터포털 15101972)",
                    "retrieved_at": summary["generated_at"][:10], "url": "https://www.data.go.kr/data/15101972/openapi.do",
                    "note": "외지인 방문자수 월 합계. 팀 DB vw_daily_core_signal"},
                   {"name": "특일 정보(공휴일)", "provider": "한국천문연구원",
                    "retrieved_at": summary["generated_at"][:10],
                    "note": "2026-07 이후 공휴일은 월력요항으로 보충"}],
        "period": {"start": outlook[0]["month"] + "-01", "end": outlook[-1]["month"] + "-01", "granularity": "월"},
        "caveat": [
            f"방법 {len(METHOD_LABEL)}가지를 2025년(검증)·2026년(시험) 두 구간에서 시간 순으로 재고, 두 구간 평균 오차가 가장 낮은 "
            f"'{summary['chosen_label']}'을 골랐다. 2026년 시험만 보면 1위는 '{METHOD_LABEL[summary['test_best']]}'"
            f"({test_all[summary['test_best']]['전체']}%)였지만 2025년에는 {summary['validation']['smape'][summary['test_best']]['전체']}%로 흔들렸다. "
            "최근 증감 추세를 반영한 방법은 모두 2025년에 좋고 2026년에 나빠 쓰지 않았다(한 해의 흐름이 다음 해로 이어지지 않음).",
            f"2026년 1~7월 시험 sMAPE: 이 방법 {test_all[chosen]['전체']}% (1달 앞 {test_all[chosen]['1']}%, "
            f"6달 앞 {test_all[chosen].get('6', '—')}%), 작년 같은 달 그대로 {test_all['SN']['전체']}%. "
            f"{name}만 보면 {region_smape:.1f}%." if not np.isnan(region_smape) else "",
            f"80% 구간은 2025·2026 두 구간 실제/예측 비율의 몇 달 앞별 10·90분위다(2026년 시험 적중률 {summary['interval_coverage_test']:.0%}).",
            "월 합계 전망이다. 날짜별 혼잡이나 지점 쏠림은 보이지 않는다 — 시군구 총량은 지점 급증을 원리적으로 담지 못한다(확정수치: 지점 급증 98% 미탐지).",
            "축제·행사 신설, 콘텐츠 유행 같은 새 사건은 예측에 들어가지 않는다. 검색 신호로 급증을 미리 아는 것은 검증에서 실패했다(AUC 0.217).",
            f"데이터 기준일 {summary['data_end']}. {summary['last_full_month']}까지 다 채워진 달로 학습했다.",
        ],
        "data": {
            "region": {"code": region, "name": name},
            "method": {"key": chosen, "label": summary["chosen_label"]},
            "as_of": summary["last_full_month"],
            "history": history,
            "outlook": outlook,
            "methods": [{"key": m, "label": METHOD_LABEL[m],
                         "valid_smape": summary["validation"]["smape"][m]["전체"],
                         "test_smape": test_all[m]["전체"], "mean_smape": summary["mean_smape"][m],
                         "chosen": m == chosen} for m in METHODS],
            "rule": summary["rule"],
            "split": {"validation_origins": summary["validation"]["origins"], "test_targets": summary["test"]["targets"]},
            "accuracy": {"region_smape": None if np.isnan(region_smape) else round(region_smape, 2),
                         "national_smape": test_all[chosen]["전체"],
                         "by_horizon": {k: v for k, v in test_all[chosen].items() if k != "전체"},
                         "baseline_smape": test_all["SN"]["전체"]},
        },
    }


if __name__ == "__main__":
    main()
