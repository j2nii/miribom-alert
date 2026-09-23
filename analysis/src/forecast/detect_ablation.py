"""추가 데이터가 '조기경보'를 개선하는가 — 월 단위 경보 실험.

배경
    9/22 실험에서 일별 네이버 검색은 시군구 방문 급증을 예고하지 못했다
    (지역 맞춤 기저율 대비 상승도 1.0~1.25, 임계를 바꾸면 방향이 뒤집힘).
    그렇다면 **추가로 수집한 데이터로는 되는가**가 다음 질문이다.
    한국관광 데이터랩 월간 지표(SNS 언급량·내비 목적지 검색·숙박 검색)는
    매월 17일에 전월분이 공개되므로, m월 초에 서 있으면 (m-2)월분까지 손에 있다.
    즉 "한 달 앞 경보"를 낼 수 있는지 시험할 수 있다.

설계 (9/22에 세운 규율을 그대로 적용)
    단위      지역 × 월 (테스트 2026-01~2026-08, 228지역 × 8개월)
    정답      그 달에 일별 전년대비 급증(7일 중앙값 기준, 2일 연속)이 시작된 달
    신호      각 지표를 '그 지역의 평소 대비 배율'로 바꾼 뒤 상위 k%에 경보
    임계      2025년(검증 구간)에서만 정한다
    비교      적중률을 **지역 맞춤 기저율**과 비교한다 (전국 평균과 비교하면 착시가 생긴다)
    민감도    경보율 2%·5%·10% 세 가지에서 결론이 유지되는지 본다

사용법
    uv run python analysis/src/forecast/detect_ablation.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"

from baseline import SPLITS  # noqa: E402
from baseline import TARGET, build_features  # noqa: E402
from detect import HORIZON, MIN_RUN, collect_events, expected_visitors, year_over_year_ratio  # noqa: E402

ALARM_RATES = [0.02, 0.05, 0.10]
DATALAB_SIGNALS = {
    "데이터랩 SNS 언급량": "sns_mentions",
    "데이터랩 내비 목적지검색": "navigation_searches",
    "데이터랩 숙박 검색": "lodging_searches",
    "데이터랩 외지인 소비": "tourism_spend_outsider_krw_thousand",
}


def surge_months(panel: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """일별 전년대비 급증이 시작된 달을 '급증 달'로 표시한다."""
    yoy = year_over_year_ratio(panel).merge(
        panel[["region_id", "region_name", "observed_date"]], on=["region_id", "observed_date"])
    valid = yoy[(yoy["observed_date"] >= SPLITS["valid"][0]) & (yoy["observed_date"] <= SPLITS["valid"][1])]
    threshold = float(valid["visit_yoy"].dropna().quantile(0.99))   # 검증 구간 상위 1%
    later = yoy[yoy["observed_date"] >= SPLITS["valid"][0]]
    events = collect_events(later, "visit_yoy", threshold, MIN_RUN)
    events["month"] = events["start"].dt.to_period("M")
    return events, threshold


def residual_surge_months(panel: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """달력·축제를 통제한 기대치 대비 급증이 시작된 달.

    전년대비(364일 전) 정의는 설·추석이 해마다 옮겨다니면 오염된다. 2026년 설은 2월,
    2025년 설은 1월이어서 '작년 2월 대비 올해 2월'은 명절 이동분을 급증으로 잘못 읽는다.
    잔차 정의는 요일·공휴일·연휴길이·축제를 넣은 모델의 기대치와 비교하므로 이 오염이 없다.
    두 정의에서 결론이 같아야 신호가 진짜다.
    """
    data = build_features(panel, HORIZON)
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    operating = lag_features + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                                "rest_run_length", "festival_active", "festival_pre", "festival_post"]
    frame = expected_visitors(data, operating)
    valid = frame[(frame["observed_date"] >= SPLITS["valid"][0]) & (frame["observed_date"] <= SPLITS["valid"][1])]
    threshold = float(valid["visit_ratio"].quantile(0.99))
    events = collect_events(frame, "visit_ratio", threshold, MIN_RUN)
    events["month"] = events["start"].dt.to_period("M")
    return events, threshold


def monthly_signals() -> pd.DataFrame:
    """월간 지표를 '그 지역 평소(직전 12개월 중앙값) 대비 배율'로 바꾼다."""
    monthly = pd.read_csv(INTERIM / "datalab_monthly.csv", dtype={"region_id": str},
                          parse_dates=["period_start"]).sort_values(["region_id", "period_start"])
    monthly["month"] = monthly["period_start"].dt.to_period("M")
    grouped = monthly.groupby("region_id")
    for column in DATALAB_SIGNALS.values():
        trailing = grouped[column].transform(lambda s: s.shift(1).rolling(12, min_periods=6).median())
        monthly[f"sig_{column}"] = monthly[column] / trailing.replace(0, np.nan)
    keep = ["region_id", "month"] + [f"sig_{c}" for c in DATALAB_SIGNALS.values()]
    return monthly[keep]


def naver_monthly_signal(panel: pd.DataFrame) -> pd.DataFrame:
    """경보 시점(달 시작) 직전 14일 검색의 '평소 대비 최대 배율'. 전일까지 공개되므로 그대로 쓸 수 있다."""
    frame = panel.sort_values(["region_id", "observed_date"]).copy()
    shifted = frame.groupby("region_id")["naver_interest"].shift(1)
    baseline = shifted.groupby(frame["region_id"]).transform(lambda s: s.rolling(28, min_periods=28).mean())
    frame["ratio"] = frame["naver_interest"] / baseline.clip(lower=0.1)
    frame["month"] = frame["observed_date"].dt.to_period("M")
    # 그 달의 경보는 달 시작 전에 내야 하므로, 직전 달 마지막 14일만 쓴다
    last14 = frame.groupby(["region_id", "month"]).tail(14)
    aggregated = last14.groupby(["region_id", "month"])["ratio"].max().reset_index()
    aggregated["month"] = aggregated["month"] + 1        # 다음 달에 대한 신호
    return aggregated.rename(columns={"ratio": "sig_naver_prev14d_max"})


def evaluate(board: pd.DataFrame, column: str, alarm_rate: float) -> dict:
    """검증 구간에서 임계를 정하고 테스트 구간에서 적중률을 지역 맞춤 기저율과 비교한다."""
    valid = board[board["split"] == "valid"]
    test = board[board["split"] == "test"]
    usable = valid[column].dropna()
    if len(usable) < 50 or test[column].notna().sum() < 20:
        return {}
    threshold = float(usable.quantile(1 - alarm_rate))
    alarmed = test[test[column] >= threshold]
    if alarmed.empty:
        return {"경보수": 0}
    hit_rate = float(alarmed["surge"].mean())
    # 지역 맞춤 기저율: 경보가 난 지역들이 원래 급증이 잦은 지역이면 적중률도 저절로 높다
    region_rate = test.groupby("region_id")["surge"].mean()
    matched_base = float(region_rate.reindex(alarmed["region_id"]).mean())
    national_base = float(test["surge"].mean())
    return {
        "경보수": int(len(alarmed)),
        "경보율_실제_pct": round(100 * len(alarmed) / len(test), 2),
        "적중률": round(hit_rate, 3),
        "기저율_지역맞춤": round(matched_base, 3),
        "기저율_전국": round(national_base, 3),
        "상승도_지역맞춤": round(hit_rate / matched_base, 2) if matched_base else None,
        "상승도_전국": round(hit_rate / national_base, 2) if national_base else None,
    }


def auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """순위 기반 판별력. 0.5 = 동전 던지기, 1.0 = 완벽. 임계를 고를 필요가 없다."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # 동점 처리 (같은 점수는 평균 순위)
    frame = pd.DataFrame({"s": scores, "r": ranks})
    ranks = frame.groupby("s")["r"].transform("mean").to_numpy()
    positives, negatives = labels.sum(), (~labels.astype(bool)).sum()
    if positives == 0 or negatives == 0:
        return float("nan")
    return float((ranks[labels.astype(bool)].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def auc_ci(labels: np.ndarray, scores: np.ndarray, draws: int = 2000, seed: int = 5):
    rng = np.random.default_rng(seed)
    n = len(labels)
    values = []
    for _ in range(draws):
        idx = rng.integers(0, n, n)
        value = auc(labels[idx], scores[idx])
        if not np.isnan(value):
            values.append(value)
    if not values:
        return (float("nan"), float("nan"))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def within_month(board: pd.DataFrame, signal_columns: dict, min_positives: int = 5) -> list[dict]:
    """같은 달 안에서 '어느 지역이 급증할지'를 가릴 수 있는가.

    급증 달의 대부분이 설·추석이 낀 한 달에 몰려 있어, 달끼리 비교하면 사실상
    '공휴일 달 맞히기'가 된다. 그래서 달을 고정하고 지역 순위만 본다.
    이렇게 하면 달력 효과가 통제되고 신호의 순수한 판별력만 남는다.
    """
    rows = []
    for month, group in board.groupby("month"):
        positives = int(group["surge"].sum())
        if positives < min_positives:
            continue
        for label, column in signal_columns.items():
            usable = group.dropna(subset=[column])
            if len(usable) < 30 or usable["surge"].sum() < min_positives:
                continue
            labels = usable["surge"].to_numpy().astype(int)
            scores = usable[column].to_numpy()
            low, high = auc_ci(labels, scores)
            rows.append({"월": str(month), "구간": usable["split"].iloc[0], "신호": label,
                         "지역수": int(len(usable)), "급증지역수": int(labels.sum()),
                         "AUC": round(auc(labels, scores), 3),
                         "AUC_95CI": [round(low, 3), round(high, 3)],
                         "판정": "판별력 있음" if low > 0.5 else ("역방향" if high < 0.5 else "판별력 없음")})
    return rows


def main() -> None:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    label_sets = {"전년대비": surge_months(panel), "잔차(달력·축제 통제)": residual_surge_months(panel)}
    events, threshold = label_sets["전년대비"]

    months = panel[["region_id", "region_name", "observed_date"]].copy()
    months["month"] = months["observed_date"].dt.to_period("M")
    board = months.groupby(["region_id", "region_name", "month"], as_index=False).size()
    board = board[board["month"] >= pd.Period("2025-01")]
    surge_keys = set(zip(events["region_id"], events["month"]))
    board["surge"] = [(r, m) in surge_keys for r, m in zip(board["region_id"], board["month"])]
    board["split"] = np.where(board["month"] <= pd.Period("2025-12"), "valid", "test")

    signals = monthly_signals()
    # 공개 규칙: m월 초에 서면 (m-2)월분까지 공개되어 있다 (m-1월분은 m월 17일 공개)
    signals["month"] = signals["month"] + 2
    board = board.merge(signals, on=["region_id", "month"], how="left")
    board = board.merge(naver_monthly_signal(panel), on=["region_id", "month"], how="left")

    signal_columns = {"네이버 일별검색(직전 14일)": "sig_naver_prev14d_max"}
    signal_columns.update({k: f"sig_{v}" for k, v in DATALAB_SIGNALS.items()})

    # 결합 신호: 2025년으로만 배우고 2026년에 적용한다
    feature_columns = list(signal_columns.values())
    train = board[board["split"] == "valid"].dropna(subset=feature_columns)
    if train["surge"].nunique() > 1:
        model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06,
                                               max_depth=3, random_state=0)
        model.fit(train[feature_columns], train["surge"].astype(int))
        ready = board[feature_columns].notna().all(axis=1)
        board["sig_combined"] = np.nan
        board.loc[ready, "sig_combined"] = model.predict_proba(board.loc[ready, feature_columns])[:, 1]
        signal_columns["결합(검색+데이터랩)"] = "sig_combined"

    test = board[board["split"] == "test"]
    print(f"급증 정의: 전년대비 7일 중앙값 {threshold:.2f}배 이상 {MIN_RUN}일 연속 "
          f"(임계는 2025년 상위 1%에서 결정)")
    print(f"테스트 지역-월 {len(test):,}칸 중 급증 달 {int(test['surge'].sum())}칸 "
          f"({100 * test['surge'].mean():.1f}%) · 2026-01~2026-08")
    print(f"검증(2025) 지역-월 {int((board['split'] == 'valid').sum()):,}칸 "
          f"중 급증 달 {int(board[board['split'] == 'valid']['surge'].sum())}칸\n")

    rows = []
    for alarm_rate in ALARM_RATES:
        for label, column in signal_columns.items():
            result = evaluate(board, column, alarm_rate)
            if not result:
                continue
            rows.append({"경보율_목표_pct": alarm_rate * 100, "신호": label, **result})

    table = pd.DataFrame(rows)
    print("신호별 성능 (상승도 1.0 = 아무 달이나 고른 것과 같음 · 지역맞춤 기저율 기준)")
    header = f"{'경보율':>6}{'신호':<24}{'경보수':>6}{'적중률':>8}{'기저율':>8}{'상승도':>8}"
    print(header)
    for row in rows:
        print(f"{row['경보율_목표_pct']:>5.0f}%{row['신호']:<24}{row['경보수']:>6}"
              f"{row['적중률']:>8.3f}{row['기저율_지역맞춤']:>8.3f}"
              f"{(row['상승도_지역맞춤'] if row['상승도_지역맞춤'] else float('nan')):>8.2f}")

    # 결론이 임계에 따라 뒤집히는지 — 9/22에 철회했던 그 함정을 다시 밟지 않기 위한 확인
    print("\n임계 민감도: 신호별 상승도가 경보율 2%/5%/10%에서 유지되는가")
    for label in signal_columns:
        values = [r["상승도_지역맞춤"] for r in rows if r["신호"] == label]
        stable = all(v is not None and v >= 1.2 for v in values)
        print(f"  {label:<24}{str(values):<24}{'일관되게 1.2배 이상' if stable else '유지되지 않음'}")

    month_rows = within_month(board, signal_columns)
    month_rows = [dict(r, 라벨="전년대비") for r in month_rows]
    for label_name, (label_events, label_threshold) in label_sets.items():
        if label_name == "전년대비":
            continue
        keys = set(zip(label_events["region_id"], label_events["month"]))
        other = board.copy()
        other["surge"] = [(r, m) in keys for r, m in zip(other["region_id"], other["month"])]
        print()
        print(f"[라벨 교차확인] {label_name} · 임계 {label_threshold:.2f} · "
              f"테스트 급증 달 {int(other[other['split'] == 'test']['surge'].sum())}칸")
        month_rows += [dict(r, 라벨=label_name) for r in within_month(other, signal_columns)]
    print()
    print("같은 달 안에서 지역을 가려내는가 (AUC 0.5 = 동전 던지기 · 95% 구간이 0.5를 걸치면 판별력 없음)")
    print(f"{'라벨':<14}{'월':<9}{'구간':<7}{'신호':<24}{'급증/지역':>10}{'AUC':>7}{'95%구간':>18}  판정")
    for row in month_rows:
        ci = f"[{row['AUC_95CI'][0]:.3f}, {row['AUC_95CI'][1]:.3f}]"
        print(f"{row['라벨']:<14}{row['월']:<9}{row['구간']:<7}{row['신호']:<24}"
              f"{str(row['급증지역수']) + '/' + str(row['지역수']):>10}{row['AUC']:>7.3f}{ci:>18}  {row['판정']}")

    out = {"surge_threshold_yoy": round(threshold, 3),
           "test_region_months": int(len(test)),
           "test_surge_months": int(test["surge"].sum()),
           "rows": rows, "within_month": month_rows}
    (INTERIM / "detect_ablation.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    table.to_csv(INTERIM / "detect_ablation.csv", index=False, encoding="utf-8")
    print("\n출력: data/interim/detect_ablation.json · detect_ablation.csv")


if __name__ == "__main__":
    main()
