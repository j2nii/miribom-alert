"""이상 탐지와 조기경보 — 검색의 진짜 가치를 여기서 잰다.

예측 정확도로는 검색이 기여하지 않았다(docs/분석_결과_예측사다리.md). 남은 질문은 이것이다.
**달력·축제로 설명되는 변동을 걷어낸 뒤, 검색이 방문 급증을 먼저 알려주는가.**

방법
1. 기대 수준 모델: 운영 모델(방문자 시차 + 달력 + 축제, 검색·날씨 제외)로 그날의 기대 방문자수를 만든다
2. 잔차 비율: 실제 ÷ 기대. 이 값이 크면 '달력으로 설명되지 않는 급증'이다
3. 방문 급증 사건(정답): 잔차 비율이 임계 이상인 날이 MIN_RUN일 이상 이어진 구간
4. 검색 이상 신호: 같은 방식으로 검색지수의 기대 수준(요일·계절)을 만들고 잔차 비율이 임계를 넘는 날
5. 선행성: 검색 신호가 방문 급증 시작보다 며칠 앞섰는가 / 방문 급증 없이 울린 검색 신호는 몇 건인가

임계는 **2025년(검증 구간)에서만** 정하고 2026년 테스트 구간에 적용한다. 테스트를 보고 고르면 성과가 부풀려진다.

사용법:
    uv run python analysis/src/detect.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "src"))

from baseline import SPLITS, TARGET, build_features  # noqa: E402

INTERIM = ROOT / "data" / "interim"
HORIZON = 7
MIN_RUN = 2            # 며칠 이어져야 '사건'으로 볼 것인가
LOOKAHEAD = 21         # 검색 신호 뒤 며칠 안에 방문 급증이 오면 적중으로 볼 것인가
ALARM_RATE = 0.01      # 검증 구간에서 이 비율(지역-일 기준)이 되도록 임계를 정한다
CASES = {"51750": "영월", "48310": "거제"}


def expected_visitors(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """2023~2024로 배워 2025·2026의 기대 방문자수를 만든다 (테스트 정보 미사용)."""
    train = data[(data["observed_date"] >= SPLITS["train"][0]) & (data["observed_date"] <= SPLITS["train"][1])]
    fit_frame = train.dropna(subset=columns + [TARGET])
    model = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.06, early_stopping=True,
                                          validation_fraction=0.15, random_state=0)
    model.fit(fit_frame[columns], np.log1p(fit_frame[TARGET]))

    later = data[data["observed_date"] > SPLITS["train"][1]].copy()
    ready = later[columns].notna().all(axis=1)
    later = later[ready].copy()
    later["expected"] = np.expm1(model.predict(later[columns]))
    later["visit_ratio"] = later[TARGET] / later["expected"].clip(lower=1)
    return later


def year_over_year_ratio(panel: pd.DataFrame) -> pd.DataFrame:
    """전년 동요일(364일 전) 대비 배율의 7일 중앙값.

    잔차 정의만 쓰면 급증이 며칠 이어질 때 기대 모델이 따라 올라가 급증이 사라진다
    (영월 2월이 실제로 그랬다). 전년 대비는 그 영향을 받지 않아 '작년보다 얼마나 많은가'를 그대로 본다.
    """
    frame = panel.sort_values(["region_id", "observed_date"]).copy()
    for column, name in ((TARGET, "visit_yoy"), ("naver_interest", "search_yoy")):
        ratio = frame[column] / frame.groupby("region_id")[column].shift(364).clip(lower=0.1)
        frame[name] = ratio.groupby(frame["region_id"]).transform(lambda s: s.rolling(7, min_periods=7).median())
    return frame[["region_id", "observed_date", "visit_yoy", "search_yoy"]]


def base_rate(events: pd.DataFrame, frame: pd.DataFrame, lookahead: int) -> float:
    """아무 날이나 골랐을 때 lookahead일 안에 급증이 시작될 확률.

    적중률은 이 값과 비교해야 의미가 있다. 기저율과 같으면 신호에 정보가 없다는 뜻이다.
    """
    region_days = frame.groupby("region_id")["observed_date"].nunique()
    per_region = []
    for region, days in region_days.items():
        count = int((events["region_id"] == region).sum())
        if days <= 0:
            continue
        daily = count / days
        per_region.append(1 - (1 - min(daily, 1.0)) ** lookahead)
    return float(np.mean(per_region)) if per_region else float("nan")


def search_ratio(panel: pd.DataFrame) -> pd.DataFrame:
    """검색지수의 '평소 대비 배율'. 같은 요일 28일 평균을 평소로 본다 (예측 시점에 알 수 있는 값만)."""
    frame = panel.sort_values(["region_id", "observed_date"]).copy()
    shifted = frame.groupby("region_id")["naver_interest"].shift(1)
    baseline = shifted.groupby(frame["region_id"]).transform(lambda s: s.rolling(28, min_periods=28).mean())
    frame["search_ratio"] = frame["naver_interest"] / baseline.clip(lower=0.1)
    return frame[["region_id", "observed_date", "search_ratio"]]


def runs(flags: pd.Series, dates: pd.Series, min_run: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """연속으로 True인 구간 중 min_run일 이상인 것의 (시작, 끝)."""
    found, start, count = [], None, 0
    for flag, date in zip(flags, dates):
        if flag:
            start = date if count == 0 else start
            count += 1
        else:
            if count >= min_run:
                found.append((start, previous))
            count = 0
        previous = date
    if count >= min_run:
        found.append((start, previous))
    return found


def collect_events(frame: pd.DataFrame, column: str, threshold: float, min_run: int) -> pd.DataFrame:
    rows = []
    for region, group in frame.groupby("region_id"):
        group = group.sort_values("observed_date")
        for start, end in runs(group[column] >= threshold, group["observed_date"], min_run):
            window = group[(group["observed_date"] >= start) & (group["observed_date"] <= end)]
            rows.append({"region_id": region, "region_name": group["region_name"].iloc[0],
                         "start": start, "end": end, "days": len(window),
                         "peak": float(window[column].max()),
                         "peak_date": window.loc[window[column].idxmax(), "observed_date"]})
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    data = build_features(panel, HORIZON)
    lag_features = [c for c in data.columns if c.startswith("vis_")]
    operating = lag_features + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday",
                                "rest_run_length", "festival_active", "festival_pre", "festival_post"]

    frame = expected_visitors(data, operating)
    frame = frame.merge(search_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(year_over_year_ratio(panel), on=["region_id", "observed_date"], how="left")
    frame = frame.merge(panel[["region_id", "observed_date", "festival_active", "is_public_holiday", "rest_run_length"]],
                        on=["region_id", "observed_date"], how="left", suffixes=("", "_panel"))

    valid = frame[(frame["observed_date"] >= SPLITS["valid"][0]) & (frame["observed_date"] <= SPLITS["valid"][1])]
    test = frame[frame["observed_date"] >= SPLITS["test"][0]].copy()

    # 임계는 검증 구간에서만 고른다 (지역-일의 상위 ALARM_RATE)
    visit_threshold = float(valid["visit_ratio"].quantile(1 - ALARM_RATE))
    search_threshold = float(valid["search_ratio"].dropna().quantile(1 - ALARM_RATE))
    visit_yoy_threshold = float(valid["visit_yoy"].dropna().quantile(1 - ALARM_RATE))

    # 급증의 정의를 두 가지로 두고 각각에 대해 검색 신호를 평가한다
    surge_sets = {
        "잔차(달력·축제 통제 후)": collect_events(test, "visit_ratio", visit_threshold, MIN_RUN),
        "전년대비": collect_events(test, "visit_yoy", visit_yoy_threshold, MIN_RUN),
    }
    surges = surge_sets["잔차(달력·축제 통제 후)"]
    signals = collect_events(test, "search_ratio", search_threshold, MIN_RUN)


    def evaluate(surge_events: pd.DataFrame, label: str) -> dict:
        """검색 신호가 이 정의의 급증을 예고하는가. 적중률은 기저율과 비교해야 뜻이 있다."""
        hits, leads = [], []
        for signal in signals.itertuples():
            follow = surge_events[(surge_events["region_id"] == signal.region_id) &
                                  (surge_events["start"] >= signal.start) &
                                  (surge_events["start"] <= signal.start + pd.Timedelta(days=LOOKAHEAD))]
            hits.append(not follow.empty)
            if not follow.empty:
                leads.append(int((follow["start"].min() - signal.start).days))

        caught = []
        for surge in surge_events.itertuples():
            before = signals[(signals["region_id"] == surge.region_id) &
                             (signals["start"] <= surge.start) &
                             (signals["start"] >= surge.start - pd.Timedelta(days=LOOKAHEAD))]
            window = test[(test["region_id"] == surge.region_id) &
                          (test["observed_date"] >= surge.start) & (test["observed_date"] <= surge.end)]
            caught.append({"region_id": surge.region_id, "region_name": surge.region_name,
                           "surge_start": surge.start, "caught": not before.empty,
                           "festival": bool(window["festival_active"].max() > 0),
                           "holiday": bool(window["is_public_holiday"].max() > 0)})
        caught = pd.DataFrame(caught)
        hit_rate = float(np.mean(hits)) if hits else float("nan")
        expected = base_rate(surge_events, test, LOOKAHEAD)
        return {
            "정의": label,
            "급증_사건수": int(len(surge_events)),
            "검색신호수": int(len(signals)),
            "적중률": round(hit_rate, 3),
            "기저율": round(expected, 3),
            "상승도(적중률/기저율)": round(hit_rate / expected, 2) if expected else None,
            "사전포착률": round(float(caught["caught"].mean()), 3) if len(caught) else None,
            "선행일수_중앙값": float(np.median(leads)) if leads else None,
            "급증_축제겹침": int(caught["festival"].sum()) if len(caught) else 0,
            "급증_공휴일겹침": int(caught["holiday"].sum()) if len(caught) else 0,
            "급증_둘다아님": int((~caught["festival"] & ~caught["holiday"]).sum()) if len(caught) else 0,
        }

    evaluations = [evaluate(events, label) for label, events in surge_sets.items()]

    # 검색 신호를 걸러내면 상승도가 올라가는가 — 지표 C(오경보 통제)의 본체
    def overlaps(signal, column: str) -> bool:
        window = test[(test["region_id"] == signal.region_id) &
                      (test["observed_date"] >= signal.start - pd.Timedelta(days=3)) &
                      (test["observed_date"] <= signal.end + pd.Timedelta(days=3))]
        return bool(window[column].max() > 0)

    signals["holiday_overlap"] = [overlaps(s, "is_public_holiday") for s in signals.itertuples()]
    signals["festival_overlap"] = [overlaps(s, "festival_active") for s in signals.itertuples()]

    filters = {
        "전체 검색 신호": signals,
        "공휴일 구간 제외": signals[~signals["holiday_overlap"]],
        "공휴일·축제 구간 제외": signals[~signals["holiday_overlap"] & ~signals["festival_overlap"]],
    }
    filter_rows = []
    for label, subset in filters.items():
        hits, leads = [], []
        target_events = surge_sets["전년대비"]
        for signal in subset.itertuples():
            follow = target_events[(target_events["region_id"] == signal.region_id) &
                                   (target_events["start"] >= signal.start) &
                                   (target_events["start"] <= signal.start + pd.Timedelta(days=LOOKAHEAD))]
            hits.append(not follow.empty)
            if not follow.empty:
                leads.append(int((follow["start"].min() - signal.start).days))
        expected = base_rate(target_events, test, LOOKAHEAD)
        rate = float(np.mean(hits)) if hits else float("nan")
        filter_rows.append({"필터": label, "신호수": int(len(subset)),
                            "적중률": round(rate, 3), "기저율": round(expected, 3),
                            "상승도": round(rate / expected, 2) if expected else None,
                            "선행일수_중앙값": float(np.median(leads)) if leads else None})

    summary = {
        "설정": {"horizon": HORIZON, "min_run_days": MIN_RUN, "lookahead_days": LOOKAHEAD,
               "alarm_rate_target": ALARM_RATE, "threshold_source": "2025 검증 구간 분위수",
               "visit_threshold_ratio": round(visit_threshold, 3),
               "visit_yoy_threshold": round(visit_yoy_threshold, 3),
               "search_threshold_ratio": round(search_threshold, 3)},
        "테스트구간": {"start": SPLITS["test"][0], "end": SPLITS["test"][1],
                  "지역수": int(test["region_id"].nunique()), "행": int(len(test))},
        "평가": evaluations,
        "신호_필터링(전년대비 급증 기준)": filter_rows,
    }
    (INTERIM / "detection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                                    encoding="utf-8")
    for label, events in surge_sets.items():
        name = "detected_surges_yoy.csv" if "전년" in label else "detected_surges_residual.csv"
        events.to_csv(INTERIM / name, index=False, encoding="utf-8-sig")
    signals.to_csv(INTERIM / "search_signals.csv", index=False, encoding="utf-8-sig")

    print(f"임계 (2025에서 결정): 잔차 {visit_threshold:.2f}배 · 전년대비 {visit_yoy_threshold:.2f}배 · 검색 {search_threshold:.2f}배")
    print(f"테스트 2026-01-01~08-14 · {test['region_id'].nunique()}지역 {len(test):,}행 · 검색 신호 {len(signals)}건")
    print()
    header = f"{'급증 정의':<22}{'사건':>6}{'적중률':>8}{'기저율':>8}{'상승도':>7}{'포착률':>8}{'선행중앙값':>10}"
    print(header)
    for row in evaluations:
        lead = f"{row['선행일수_중앙값']:.0f}일" if row["선행일수_중앙값"] is not None else "-"
        print(f"{row['정의']:<22}{row['급증_사건수']:>6}{row['적중률']:>8.1%}{row['기저율']:>8.1%}"
              f"{row['상승도(적중률/기저율)'] or 0:>7.2f}{row['사전포착률'] or 0:>8.1%}{lead:>10}")
    print()
    print("검색 신호를 걸러내면 (전년대비 급증 기준)")
    print(f"  {'필터':<22}{'신호수':>7}{'적중률':>8}{'상승도':>7}{'선행중앙값':>10}")
    for row in filter_rows:
        lead = f"{row['선행일수_중앙값']:.0f}일" if row["선행일수_중앙값"] is not None else "-"
        print(f"  {row['필터']:<22}{row['신호수']:>7}{row['적중률']:>8.1%}{row['상승도'] or 0:>7.2f}{lead:>10}")

    print()
    print("급증 사건의 성격")
    for row in evaluations:
        print(f"  {row['정의']:<22} 축제 {row['급증_축제겹침']}건 · 공휴일 {row['급증_공휴일겹침']}건 · 둘 다 아님 {row['급증_둘다아님']}건")

    for region, label in CASES.items():
        print()
        print(f"[{label}]")
        for definition, events in surge_sets.items():
            rows = events[events["region_id"] == region]
            if len(rows):
                spans = ", ".join(f"{r.start:%m/%d}~{r.end:%m/%d}({r.peak:.1f}배)" for r in rows.itertuples())
                print(f"   급증·{definition}: {spans}")
            else:
                print(f"   급증·{definition}: 없음")
        rows = signals[signals["region_id"] == region]
        spans = ", ".join(f"{r.start:%m/%d}~{r.end:%m/%d}({r.peak:.1f}배)" for r in rows.itertuples()) or "없음"
        print(f"   검색 신호: {spans}")

    print()
    print("출력: data/interim/detection_summary.json, detected_surges_*.csv, search_signals.csv")


if __name__ == "__main__":
    main()
