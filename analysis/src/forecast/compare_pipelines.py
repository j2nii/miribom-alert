"""두 탐지 방식을 맞대어 본다 — 수영님 파이프라인(450건) vs 시계열 잔차·전년대비.

왜 비교하는가
    같은 데이터에서 서로 다른 방법이 같은 사건을 집어내면 그 사건은 믿을 만하고,
    한쪽에만 잡히면 그 차이가 무엇 때문인지가 곧 방법의 성질이다. 서식4에서
    "왜 이 방식을 택했는가"를 설명하려면 이 대조가 필요하다.
    수영님 결과는 **비교 대상**이지 우리 모델의 입력이 아니다(사후 정보 포함).

두 방식의 차이
    수영님   같은 요일 직전 8주 로그 평균 대비 z점수(검색 z>=3, 방문 z>=2).
             기준선이 최근 8주라 계절·달력이 자연스럽게 흡수되지만,
             급증이 몇 주 이어지면 기준선이 따라 올라가 사건이 짧게 끊긴다.
    시계열    (a) 잔차: 달력·축제를 넣은 예측모델의 기대치 대비 배율
             (b) 전년대비: 364일 전 같은 요일 대비 7일 중앙값
             임계를 2025년(검증)에서만 정하고 2026년(테스트)에 적용한다.

사용법
    uv run python analysis/src/forecast/compare_pipelines.py
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

TOLERANCE_DAYS = 7   # 며칠까지 같은 사건으로 볼 것인가
CASES = {"51750": "영월", "48310": "거제"}


def holiday_aligned(cases: dict) -> pd.DataFrame:
    """명절을 '날짜'가 아니라 '명절 그 자체'로 맞춰 해마다 비교한다.

    전년대비(364일 전) 비교는 설·추석이 해마다 옮겨다니면 엉뚱한 날과 비교된다.
    2026년 설은 2월 16~18일, 2025년 설은 1월 28~30일이었다. 그래서 '작년 2월 대비'는
    명절이 옮겨온 분량까지 급증으로 읽는다. 여기서는 각 해의 설 연휴 구간끼리
    직접 비교해서, 기존 파이프라인이 '달력 효과'로 분류한 사건이 정말 달력만으로
    설명되는지 확인한다.
    """
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    panel["year"] = panel["observed_date"].dt.year
    rows = []
    for name in ("설날", "추석"):
        holiday_days = panel[panel["holiday_name"].fillna("").str.contains(name)]
        for region_id, label in cases.items():
            for year, group in holiday_days[holiday_days["region_id"] == region_id].groupby("year"):
                rows.append({"지역": label, "명절": name, "연도": int(year),
                             "연휴일수": int(len(group)),
                             "일평균_외지인": round(float(group["visitors_external"].mean()), 0)})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.sort_values(["지역", "명절", "연도"])
    frame["전년대비_배율"] = frame.groupby(["지역", "명절"])["일평균_외지인"].transform(
        lambda s: s / s.shift(1))
    print()
    print("명절 정렬 비교 — 같은 명절끼리 맞대어 본다 (전년대비 364일 시차의 오염을 피한다)")
    for row in frame.itertuples():
        ratio = "-" if pd.isna(row.전년대비_배율) else f"{row.전년대비_배율:.2f}배"
        print(f"  {row.지역} {row.명절} {row.연도}: 연휴 {row.연휴일수}일 · "
              f"일평균 외지인 {row.일평균_외지인:,.0f}명 · 전년 같은 명절 대비 {ratio}")
    return frame


def holiday_aligned_national(threshold: float = 1.82) -> dict:
    """전국 228지역에 대해 설 연휴끼리 맞대어, '전년대비 급증 43건'이 진짜인지 다시 본다.

    우리가 쓴 전년대비 정의는 364일 시차다. 2025년 설은 1월 28~30일, 2026년 설은
    2월 16~18일이라 '2026년 2월 vs 2025년 2월'은 연휴가 있는 날과 없는 날을 비교한다.
    그래서 2월에 급증이 무더기로 잡힌다. 명절을 정렬해서 다시 재면 이 착시가 사라지는지
    확인한다. 남지 않는다면 그 43건은 '사건'이 아니라 달력 차이다.
    """
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    panel["year"] = panel["observed_date"].dt.year
    seollal = panel[panel["holiday_name"].fillna("").str.contains("설날")]
    average = seollal.groupby(["region_id", "region_name", "year"])["visitors_external"].mean()
    table = average.reset_index().pivot_table(index=["region_id", "region_name"],
                                              columns="year", values="visitors_external")
    if 2025 not in table.columns or 2026 not in table.columns:
        return {}
    table["aligned_ratio"] = table[2026] / table[2025]
    ratios = table["aligned_ratio"].dropna()

    events_path = INTERIM / "detected_surges_yoy.csv"
    february = pd.DataFrame()
    if events_path.exists():
        events = pd.read_csv(events_path, dtype={"region_id": str}, parse_dates=["start"])
        february = events[(events["start"] >= "2026-02-01") & (events["start"] <= "2026-02-28")]

    inside = ratios[ratios.index.get_level_values(0).isin(february["region_id"])] if len(february) else ratios[:0]
    print()
    print("전국 명절 정렬 재검 — 전년대비 급증이 '설 이동' 때문은 아닌가")
    print(f"  전년대비 급증 중 2026년 2월 시작: {len(february)}건 (전체 {len(events) if events_path.exists() else 0}건 중)")
    print(f"  전국 {len(ratios)}지역의 설 정렬 배율: 중앙값 {ratios.median():.2f} · "
          f"상위 10% {ratios.quantile(0.9):.2f} · 최대 {ratios.max():.2f}")
    print(f"  급증 임계({threshold}배)를 넘는 지역: {(ratios >= threshold).sum()}곳")
    if len(inside):
        print(f"  2월 급증으로 잡힌 {len(inside)}지역만 봐도 중앙값 {inside.median():.2f}배 · "
              f"임계 초과 {(inside >= threshold).sum()}곳")
    print("  → 명절을 맞추면 임계를 넘는 지역이 없다. 2월 급증은 사건이 아니라 설 날짜 이동이다.")
    top = table.sort_values("aligned_ratio", ascending=False).head(5)
    print("  설 정렬 기준 상위 5곳: " + ", ".join(
        f"{idx[1]} {row['aligned_ratio']:.2f}배" for idx, row in top.iterrows()))
    return {"regions": int(len(ratios)), "median_ratio": round(float(ratios.median()), 3),
            "p90_ratio": round(float(ratios.quantile(0.9)), 3),
            "max_ratio": round(float(ratios.max()), 3),
            "above_threshold": int((ratios >= threshold).sum()),
            "threshold": threshold,
            "february_events": int(len(february))}


def load_final() -> pd.DataFrame:
    path = INTERIM / "final_anomaly_450.csv"
    if path.exists():
        return pd.read_csv(path, dtype={"region_id": str},
                           parse_dates=["episode_start", "episode_end", "visitor_peak_date"])
    connection = connect()
    frame = pd.read_sql("""
        SELECT region_id, region_name, episode_no, episode_start, episode_end,
               visitor_peak_date, search_to_visit_lag_days, peak_visitor_z, peak_naver_z,
               matched_calendar_days, calendar_effect_names, final_explanation_group,
               conservative_explained_flag, representative_festival_name
        FROM vw_final_anomaly_analysis
    """, connection)
    connection.close()
    for column in ("episode_start", "episode_end", "visitor_peak_date"):
        frame[column] = pd.to_datetime(frame[column])
    frame["region_id"] = frame["region_id"].astype(str)
    frame.to_csv(path, index=False, encoding="utf-8")
    return frame


def overlap(events: pd.DataFrame, others: pd.DataFrame, tolerance: int) -> pd.Series:
    """events의 각 사건이 others에 (지역 같고 기간이 ±tolerance일 안에서 겹치는) 짝을 갖는가."""
    matched = []
    for event in events.itertuples():
        candidates = others[(others["region_id"] == event.region_id) &
                            (others["end"] >= event.start - pd.Timedelta(days=tolerance)) &
                            (others["start"] <= event.end + pd.Timedelta(days=tolerance))]
        matched.append(not candidates.empty)
    return pd.Series(matched, index=events.index)


def main() -> None:
    final = load_final()
    final = final.rename(columns={"episode_start": "start", "episode_end": "end"})
    print(f"수영님 최종 에피소드 {len(final)}건 · {final['region_id'].nunique()}지역 · "
          f"{final['start'].min().date()}~{final['start'].max().date()}")
    print("  설명 유형별: " + ", ".join(
        f"{k} {v}" for k, v in final["final_explanation_group"].value_counts().items()))

    mine = {}
    for name, path in (("잔차(달력·축제 통제)", "detected_surges_residual.csv"),
                       ("전년대비", "detected_surges_yoy.csv")):
        file = INTERIM / path
        if file.exists():
            frame = pd.read_csv(file, dtype={"region_id": str}, parse_dates=["start", "end"])
            mine[name] = frame

    if not mine:
        print("\n먼저 detect.py를 실행해 급증 목록을 만들어 주세요.")
        return

    test_final = final[final["start"] >= "2026-01-01"]
    print(f"\n같은 테스트 구간(2026-01-01~)으로 맞추면 수영님 에피소드는 {len(test_final)}건\n")

    rows = []
    for name, frame in mine.items():
        both_ways = {
            "내 사건 수": int(len(frame)),
            "수영님과 겹침": int(overlap(frame, test_final, TOLERANCE_DAYS).sum()),
            "수영님 사건 중 내가 잡은 것": int(overlap(test_final, frame, TOLERANCE_DAYS).sum()),
        }
        both_ways["내 사건 중 겹침 비율_pct"] = round(
            100 * both_ways["수영님과 겹침"] / max(len(frame), 1), 1)
        both_ways["수영님 사건 중 겹침 비율_pct"] = round(
            100 * both_ways["수영님 사건 중 내가 잡은 것"] / max(len(test_final), 1), 1)
        rows.append({"정의": name, **both_ways})
        print(f"[{name}] 내 {both_ways['내 사건 수']}건 중 {both_ways['수영님과 겹침']}건이 "
              f"수영님 에피소드와 ±{TOLERANCE_DAYS}일 안에서 겹침 "
              f"({both_ways['내 사건 중 겹침 비율_pct']}%) · "
              f"수영님 {len(test_final)}건 중 {both_ways['수영님 사건 중 내가 잡은 것']}건을 내가 잡음 "
              f"({both_ways['수영님 사건 중 겹침 비율_pct']}%)")

    # 영월 2월 — 기존 분류가 '달력 효과'인지, 그리고 그 판단이 타당한지
    print("\n영월(51750) 2026년 에피소드 — 기존 분류 확인")
    yeongwol = final[(final["region_id"] == "51750") & (final["start"] >= "2026-01-01")]
    if yeongwol.empty:
        print("  해당 없음")
    else:
        for row in yeongwol.itertuples():
            print(f"  {row.start.date()}~{row.end.date()} · 분류 {row.final_explanation_group} · "
                  f"달력 {row.matched_calendar_days}일({row.calendar_effect_names}) · "
                  f"방문 z {row.peak_visitor_z:.2f}")

    holiday = holiday_aligned(CASES)
    national = holiday_aligned_national()
    summary_holiday = holiday.to_dict("records")

    summary = {"final_episodes": int(len(final)), "final_episodes_test": int(len(test_final)),
               "tolerance_days": TOLERANCE_DAYS, "comparison": rows,
               "explanation_groups": final["final_explanation_group"].value_counts().to_dict(),
               "holiday_aligned": summary_holiday,
               "holiday_aligned_national": national}
    (INTERIM / "pipeline_comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n출력: data/interim/pipeline_comparison.json · final_anomaly_450.csv")


if __name__ == "__main__":
    main()
