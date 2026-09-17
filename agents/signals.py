"""일별 신호 판정 (설계결정 D-12, 임시 규칙 — 역할2 백테스트로 교체될 수 있다).

규칙
- 배율: 그날 값 ÷ 364일 전(같은 요일) 값. 전년 같은 시기와 비교해 계절성을 뺀다
- 통계량: 배율의 최근 7일 중앙값. 평균이 아니라 중앙값이라 1~2일짜리 사건(산불 보도 등)에 끌려가지 않는다
- 임계: 2024년 전국(합성 지역 제외) 모든 지역·일자의 통계량 99백분위. 사례 지역을 보고 정하지 않는다
- 확정: 임계 초과가 7일 연속되면 7번째 날에 신호를 낸다. 첫날에 내면 미래를 본 셈이 된다.
  1~3일짜리 사건 급증과 짧은 명절 이동은 걸러지지만, 2025년 설·추석처럼 긴 연휴는 일부 지역에서 7일을 넘는다
  (전국 외지인 방문자 신호 23건 중 20건이 2025-01·2025-10 시작 — signal_episodes.csv)

입력은 collection/db_export.py가 만든 data/raw/db/daily_all.csv다.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data" / "raw" / "db"

LAG_DAYS = 364
WINDOW = 7
MIN_DURATION = 7
PERCENTILE = 0.99
BASELINE = ("2024-01-01", "2024-12-31")

METRICS = {
    "interest_naver": "네이버 검색지수",
    "realization_visitors": "외지인 방문자수",
}


@dataclass
class Episode:
    start: pd.Timestamp       # 임계를 처음 넘은 날
    end: pd.Timestamp         # 마지막으로 넘은 날
    confirm: pd.Timestamp     # 신호를 내는 날 (start + 6일)
    peak: float
    peak_date: pd.Timestamp


class SignalFrames:
    def __init__(self) -> None:
        daily = pd.read_csv(DB_DIR / "daily_all.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
        regions = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str})
        real_regions = set(regions.loc[regions["is_synthetic"] == 0, "region_id"])

        self.raw: dict[str, pd.DataFrame] = {}
        self.ratio: dict[str, pd.DataFrame] = {}
        self.stat: dict[str, pd.DataFrame] = {}
        self.threshold: dict[str, float] = {}
        self.data_end: dict[str, pd.Timestamp] = {}
        for metric, group in daily.groupby("metric"):
            wide = group.pivot(index="observed_date", columns="region_id", values="value").asfreq("D")
            ratio = wide / wide.shift(LAG_DAYS)
            stat = ratio.rolling(WINDOW, min_periods=WINDOW).median()
            base = stat.loc[BASELINE[0]:BASELINE[1], [c for c in stat.columns if c in real_regions]].stack()
            self.raw[metric] = wide
            self.ratio[metric] = ratio
            self.stat[metric] = stat
            self.threshold[metric] = round(float(base.quantile(PERCENTILE)), 2)
            self.data_end[metric] = wide.dropna(how="all").index.max()

    def episodes(self, metric: str, region: str, start: str, end: str) -> list[Episode]:
        """start~end 사이에 시작한, MIN_DURATION일 이상 이어진 임계 초과 구간."""
        stat = self.stat[metric][region]
        above = stat >= self.threshold[metric]
        run_id = (above != above.shift()).cumsum()
        found = []
        for _, run in stat[above].groupby(run_id[above]):
            first, last = run.index[0], run.index[-1]
            if not (pd.Timestamp(start) <= first <= pd.Timestamp(end)):
                continue
            if len(run) < MIN_DURATION:
                continue
            found.append(Episode(first, last, first + pd.Timedelta(days=MIN_DURATION - 1),
                                 float(run.max()), run.idxmax()))
        return found

    def window_max(self, metric: str, region: str, start: str, end: str) -> tuple[float, pd.Timestamp] | None:
        s = self.stat[metric][region].loc[start:end].dropna()
        if s.empty:
            return None
        return float(s.max()), s.idxmax()

    def daily_peak(self, metric: str, region: str, start: str, end: str) -> tuple[float, pd.Timestamp] | None:
        s = self.ratio[metric][region].loc[start:end].dropna()
        if s.empty:
            return None
        return float(s.max()), s.idxmax()

    def days_above(self, metric: str, region: str, start: str, end: str) -> int:
        """구간 안에서 통계량이 임계를 넘은 가장 긴 연속 일수."""
        s = self.stat[metric][region].loc[start:end]
        above = s >= self.threshold[metric]
        if not above.any():
            return 0
        run_id = (above != above.shift()).cumsum()
        return int(above.groupby(run_id).sum().max())


def export_episodes(start: str = "2025-01-01") -> Path:
    """전국 신호 구간 목록 — 역할2 백테스트의 사례 후보. data/handoff/signal_episodes.csv"""
    frames = SignalFrames()
    names = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str}).set_index("region_id")
    rows = []
    for metric, label in METRICS.items():
        end = frames.data_end[metric].strftime("%Y-%m-%d")
        for region in frames.stat[metric].columns:
            if region not in names.index or names.at[region, "is_synthetic"]:
                continue
            for ep in frames.episodes(metric, region, start, end):
                rows.append({
                    "region_id": region, "region_name": names.at[region, "region_name"], "metric": label,
                    "start": ep.start.date(), "confirm": ep.confirm.date(), "end": ep.end.date(),
                    "days": (ep.end - ep.start).days + 1, "peak": round(ep.peak, 2), "peak_date": ep.peak_date.date(),
                    "threshold": frames.threshold[metric],
                })
    out = ROOT / "data" / "handoff" / "signal_episodes.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows).sort_values(["metric", "start", "region_id"])
    table.to_csv(out, index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    path = export_episodes()
    table = pd.read_csv(path)
    print(f"{path.relative_to(ROOT)}: {len(table)}개 구간")
    print(table.groupby("metric").agg(구간=("region_id", "size"), 지역=("region_id", "nunique")).to_string())
