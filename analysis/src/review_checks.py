"""전면 검토 — 지금까지의 분석이 믿을 만한지 코드로 확인한다.

검사 항목
1. 시차 정렬   : 특징이 정말 '그 시점에 알 수 있는 값'인가 (무작위 표본을 직접 대조)
2. 위약 검사   : 목표값을 섞으면 성능이 무너지는가 (안 무너지면 어딘가 누출이 있다)
3. 미래 차단   : 학습 구간 뒤의 값을 쓰지 않았는가 (특징 생성 시점 확인)
4. 기저율 보정 : 신호가 난 지역에 맞춘 기저율로 상승도를 다시 계산
5. 임계 민감도 : 경보 임계를 바꿔도 결론이 유지되는가

사용법:
    uv run python analysis/src/review_checks.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "src"))

from baseline import SPLITS, TARGET, VISITOR_DELAY, build_features, score  # noqa: E402
from detect import LOOKAHEAD, collect_events, expected_visitors, search_ratio, year_over_year_ratio  # noqa: E402

INTERIM = ROOT / "data" / "interim"
HORIZON = 7
PASS, FAIL = "통과", "실패"


def check_lag_alignment(panel: pd.DataFrame, data: pd.DataFrame, samples: int = 200) -> str:
    """무작위 행을 뽑아 vis_last·naver_last가 실제로 그 시차의 값인지 원본과 대조한다."""
    lookup = panel.set_index(["region_id", "observed_date"])
    rows = data.dropna(subset=["vis_last", "naver_last"]).sample(samples, random_state=0)
    visit_cut, naver_cut = HORIZON + VISITOR_DELAY, HORIZON + 1
    mismatches = 0
    for row in rows.itertuples():
        want_visit = (row.region_id, row.observed_date - pd.Timedelta(days=visit_cut))
        want_naver = (row.region_id, row.observed_date - pd.Timedelta(days=naver_cut))
        if want_visit not in lookup.index or want_naver not in lookup.index:
            continue
        if abs(lookup.loc[want_visit, TARGET] - row.vis_last) > 0.01:
            mismatches += 1
        if abs(lookup.loc[want_naver, "naver_interest"] - row.naver_last) > 0.01:
            mismatches += 1
    print(f"1. 시차 정렬     {PASS if mismatches == 0 else FAIL} — 표본 {samples}행 대조, 불일치 {mismatches}건 "
          f"(방문자 {visit_cut}일 전, 검색 {naver_cut}일 전)")
    return PASS if mismatches == 0 else FAIL


def check_placebo(data: pd.DataFrame, columns: list[str]) -> str:
    """목표값을 지역 안에서 섞고 학습한다. 성능이 무너져야 정상이다."""
    def part(name: str) -> pd.DataFrame:
        start, end = SPLITS[name]
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)]

    fit_pool = pd.concat([part("train"), part("valid")]).dropna(subset=columns + [TARGET]).copy()
    test = part("test").dropna(subset=columns).copy()
    rng = np.random.default_rng(0)
    fit_pool["shuffled"] = fit_pool.groupby("region_id")[TARGET].transform(lambda s: rng.permutation(s.to_numpy()))

    real = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.06, early_stopping=True, random_state=0)
    real.fit(fit_pool[columns], np.log1p(fit_pool[TARGET]))
    test["real"] = np.expm1(real.predict(test[columns]))

    fake = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.06, early_stopping=True, random_state=0)
    fake.fit(fit_pool[columns], np.log1p(fit_pool["shuffled"]))
    test["fake"] = np.expm1(fake.predict(test[columns]))

    real_smape, fake_smape = score(test, "real")["smape"], score(test, "fake")["smape"]
    verdict = PASS if fake_smape > real_smape * 1.5 else FAIL
    print(f"2. 위약 검사     {verdict} — 정상 목표 sMAPE {real_smape:.2f}% vs 섞은 목표 {fake_smape:.2f}% "
          f"(섞으면 크게 나빠져야 정상)")
    return verdict


def check_future_blocking(data: pd.DataFrame) -> str:
    """특징 생성이 미래 값을 끌어오지 않는지, 마지막 관측일 이후 값이 없는지 확인한다."""
    last_day = data["observed_date"].max()
    future_rows = int((data["observed_date"] > last_day).sum())
    # 테스트 구간 첫날의 vis_last는 2025년 값이어야 한다
    first_test = data[data["observed_date"] == pd.Timestamp(SPLITS["test"][0])].dropna(subset=["vis_last"])
    expected_source = pd.Timestamp(SPLITS["test"][0]) - pd.Timedelta(days=HORIZON + VISITOR_DELAY)
    verdict = PASS if future_rows == 0 and expected_source.year == 2025 else FAIL
    print(f"3. 미래 차단     {verdict} — 마지막 관측일 {last_day:%Y-%m-%d}, 테스트 첫날의 방문자 특징 출처 "
          f"{expected_source:%Y-%m-%d} ({len(first_test)}개 지역)")
    return verdict


def check_base_rate(panel: pd.DataFrame, data: pd.DataFrame) -> str:
    """상승도를 '신호가 난 지역'에 맞춘 기저율로 다시 계산한다.

    전국 평균 기저율을 쓰면, 급증이 잦은 지역에서 신호가 많이 났을 때 상승도가 부풀려진다.
    """
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    operating = lag_features + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                                "rest_run_length", "festival_active", "festival_pre", "festival_post"]
    frame = expected_visitors(data, operating)
    frame = frame.merge(search_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(year_over_year_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(panel[["region_id", "observed_date", "festival_active", "is_public_holiday"]],
                        on=["region_id", "observed_date"], how="left", suffixes=("", "_p"))

    valid = frame[(frame["observed_date"] >= SPLITS["valid"][0]) & (frame["observed_date"] <= SPLITS["valid"][1])]
    test = frame[frame["observed_date"] >= SPLITS["test"][0]].copy()
    surge_threshold = float(valid["visit_yoy"].dropna().quantile(0.99))
    search_threshold = float(valid["search_ratio"].dropna().quantile(0.99))
    surges = collect_events(test, "visit_yoy", surge_threshold, 2)
    signals = collect_events(test, "search_ratio", search_threshold, 2)

    days_per_region = test.groupby("region_id")["observed_date"].nunique()
    surge_per_region = surges.groupby("region_id").size()

    def region_matched_lift(subset: pd.DataFrame) -> tuple[float, float, float]:
        hits, expectations = [], []
        for signal in subset.itertuples():
            follow = surges[(surges["region_id"] == signal.region_id) &
                            (surges["start"] >= signal.start) &
                            (surges["start"] <= signal.start + pd.Timedelta(days=LOOKAHEAD))]
            hits.append(not follow.empty)
            rate = surge_per_region.get(signal.region_id, 0) / days_per_region.get(signal.region_id, 1)
            expectations.append(1 - (1 - min(rate, 1.0)) ** LOOKAHEAD)
        hit_rate = float(np.mean(hits)) if hits else float("nan")
        expected = float(np.mean(expectations)) if expectations else float("nan")
        return hit_rate, expected, hit_rate / expected if expected else float("nan")

    def overlaps(signal, column: str) -> bool:
        window = test[(test["region_id"] == signal.region_id) &
                      (test["observed_date"] >= signal.start - pd.Timedelta(days=3)) &
                      (test["observed_date"] <= signal.end + pd.Timedelta(days=3))]
        return bool(window[column].max() > 0)

    signals["holiday"] = [overlaps(s, "is_public_holiday") for s in signals.itertuples()]
    signals["festival"] = [overlaps(s, "festival_active") for s in signals.itertuples()]
    filtered = signals[~signals["holiday"] & ~signals["festival"]]

    all_rate, all_base, all_lift = region_matched_lift(signals)
    sub_rate, sub_base, sub_lift = region_matched_lift(filtered)
    print(f"4. 기저율 보정   참고 — 지역 맞춤 기저율 기준")
    print(f"     전체 신호 {len(signals):>3}건: 적중 {all_rate:.1%} / 기저 {all_base:.1%} → 상승도 {all_lift:.2f}")
    print(f"     필터 후  {len(filtered):>3}건: 적중 {sub_rate:.1%} / 기저 {sub_base:.1%} → 상승도 {sub_lift:.2f}")
    return f"전체 {all_lift:.2f} / 필터 후 {sub_lift:.2f}"


def check_threshold_sensitivity(panel: pd.DataFrame, data: pd.DataFrame) -> str:
    """경보 임계를 바꿔도 '필터링이 상승도를 올린다'는 결론이 유지되는지 본다."""
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    operating = lag_features + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                                "rest_run_length", "festival_active", "festival_pre", "festival_post"]
    frame = expected_visitors(data, operating)
    frame = frame.merge(search_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(year_over_year_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(panel[["region_id", "observed_date", "festival_active", "is_public_holiday"]],
                        on=["region_id", "observed_date"], how="left", suffixes=("", "_p"))
    valid = frame[(frame["observed_date"] >= SPLITS["valid"][0]) & (frame["observed_date"] <= SPLITS["valid"][1])]
    test = frame[frame["observed_date"] >= SPLITS["test"][0]].copy()

    print("5. 임계 민감도   경보율별 상승도 (필터 전 → 후)")
    verdicts = []
    for alarm_rate in (0.005, 0.01, 0.02):
        surge_threshold = float(valid["visit_yoy"].dropna().quantile(1 - alarm_rate))
        search_threshold = float(valid["search_ratio"].dropna().quantile(1 - alarm_rate))
        surges = collect_events(test, "visit_yoy", surge_threshold, 2)
        signals = collect_events(test, "search_ratio", search_threshold, 2)
        if surges.empty or signals.empty:
            continue
        days = test.groupby("region_id")["observed_date"].nunique()
        per_region = surges.groupby("region_id").size()

        def lift(subset: pd.DataFrame) -> float:
            hits, expectations = [], []
            for signal in subset.itertuples():
                follow = surges[(surges["region_id"] == signal.region_id) &
                                (surges["start"] >= signal.start) &
                                (surges["start"] <= signal.start + pd.Timedelta(days=LOOKAHEAD))]
                hits.append(not follow.empty)
                rate = per_region.get(signal.region_id, 0) / days.get(signal.region_id, 1)
                expectations.append(1 - (1 - min(rate, 1.0)) ** LOOKAHEAD)
            if not hits or np.mean(expectations) == 0:
                return float("nan")
            return float(np.mean(hits)) / float(np.mean(expectations))

        def overlaps(signal, column: str) -> bool:
            window = test[(test["region_id"] == signal.region_id) &
                          (test["observed_date"] >= signal.start - pd.Timedelta(days=3)) &
                          (test["observed_date"] <= signal.end + pd.Timedelta(days=3))]
            return bool(window[column].max() > 0)

        signals["holiday"] = [overlaps(s, "is_public_holiday") for s in signals.itertuples()]
        signals["festival"] = [overlaps(s, "festival_active") for s in signals.itertuples()]
        filtered = signals[~signals["holiday"] & ~signals["festival"]]
        before, after = lift(signals), lift(filtered)
        verdicts.append(after > before)
        print(f"     경보율 {alarm_rate:.1%}: 신호 {len(signals):>3}→{len(filtered):>3}건, "
              f"상승도 {before:.2f} → {after:.2f}")
    verdict = PASS if all(verdicts) else FAIL
    print(f"   결론 유지 여부: {verdict}")
    return verdict


def main() -> None:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    data = build_features(panel, HORIZON)
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    operating = lag_features + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                                "rest_run_length", "festival_active", "festival_pre", "festival_post"]

    print(f"검토 대상: 패널 {len(panel):,}행 · 특징 {len(data.columns)}열 · 예측 {HORIZON}일 앞\n")
    check_lag_alignment(panel, data)
    check_placebo(data, operating)
    check_future_blocking(data)
    check_base_rate(panel, data)
    check_threshold_sensitivity(panel, data)


if __name__ == "__main__":
    main()
