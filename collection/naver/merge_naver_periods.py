#!/usr/bin/env python3
"""겹치는 두 네이버 검색지수 구간을 하나의 일별 정본으로 연결한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="네이버 기간별 CSV 스케일 연결")
    p.add_argument("--older", type=Path, default=base / "naver_period_202301_202412.csv")
    p.add_argument("--newer", type=Path, default=base / "naver_period_202407_202608.csv")
    p.add_argument("--output", type=Path, default=base / "naver_all_daily_202301_202608.csv")
    p.add_argument("--report", type=Path, default=base / "naver_merge_report.json")
    p.add_argument("--expected-start", default="2023-01-01")
    p.add_argument("--expected-end", default="2026-08-31")
    p.add_argument("--expected-regions", type=int, default=228)
    p.add_argument("--min-overlap-days", type=int, default=90)
    return p.parse_args()


def read_period(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise SystemExit(f"{label} CSV를 찾을 수 없습니다: {path}")
    df = pd.read_csv(path, dtype={"region": str})
    missing = {"region", "date", "value"} - set(df.columns)
    if missing:
        raise SystemExit(f"{path.name} 필수 열 누락: {', '.join(sorted(missing))}")
    df = df[["region", "date", "value"]].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if df[["region", "date", "value"]].isna().any().any():
        raise SystemExit(f"{path.name}에 날짜·수치 변환 실패 행이 있습니다.")
    dup = int(df.duplicated(["region", "date"]).sum())
    if dup:
        raise SystemExit(f"{path.name}에 지역·일자 중복 {dup:,}건이 있습니다.")
    return df.sort_values(["region", "date"]).reset_index(drop=True)


def main() -> int:
    args = parse_args()
    older = read_period(args.older.resolve(), "앞 구간")
    newer = read_period(args.newer.resolve(), "뒤 구간")

    old_regions = set(older["region"])
    new_regions = set(newer["region"])
    if old_regions != new_regions:
        only_old = sorted(old_regions - new_regions)[:10]
        only_new = sorted(new_regions - old_regions)[:10]
        raise SystemExit(f"두 CSV의 지역 집합이 다릅니다. 앞에만={only_old}, 뒤에만={only_new}")

    overlap_start = max(older["date"].min(), newer["date"].min())
    overlap_end = min(older["date"].max(), newer["date"].max())
    overlap_days = (overlap_end - overlap_start).days + 1
    if overlap_days < args.min_overlap_days:
        raise SystemExit(f"겹침 기간이 {overlap_days}일로 너무 짧습니다. 최소 {args.min_overlap_days}일이 필요합니다.")

    ov_old = older[older["date"].between(overlap_start, overlap_end)]
    ov_new = newer[newer["date"].between(overlap_start, overlap_end)]
    joined = ov_old.merge(ov_new, on=["region", "date"], suffixes=("_old", "_new"), validate="one_to_one")
    expected_overlap_rows = len(old_regions) * overlap_days
    if len(joined) != expected_overlap_rows:
        raise SystemExit(
            f"겹침 행이 {len(joined):,}건이지만 {expected_overlap_rows:,}건이어야 합니다. "
            "빠진 날짜가 있습니다."
        )

    per_region = []
    for region, group in joined.groupby("region"):
        old_mean = float(group["value_old"].mean())
        new_mean = float(group["value_new"].mean())
        if old_mean <= 0 or new_mean <= 0:
            continue
        corr = group["value_old"].corr(group["value_new"])
        per_region.append((region, new_mean / old_mean, float(corr) if pd.notna(corr) else np.nan))
    stats = pd.DataFrame(per_region, columns=["region", "scale", "corr"])
    usable_scale = stats["scale"].replace([np.inf, -np.inf], np.nan).dropna()
    usable_corr = stats["corr"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(usable_scale) < max(10, int(len(old_regions) * 0.8)):
        raise SystemExit(f"스케일을 계산할 수 있는 지역이 {len(usable_scale)}개로 부족합니다.")
    scale = float(usable_scale.median())
    corr_median = float(usable_corr.median()) if len(usable_corr) else float("nan")
    corr_p10 = float(usable_corr.quantile(0.10)) if len(usable_corr) else float("nan")
    if not np.isfinite(corr_median) or corr_median < 0.99 or corr_p10 < 0.95:
        raise SystemExit(
            f"겹침 시계열 모양이 일치하지 않습니다: "
            f"상관계수 중앙값={corr_median:.4f}, 10백분위={corr_p10:.4f}"
        )

    old_head = older[older["date"] < newer["date"].min()].copy()
    old_head["value"] = old_head["value"] * scale
    merged = pd.concat([old_head, newer], ignore_index=True).sort_values(["region", "date"])
    if merged.duplicated(["region", "date"]).any():
        raise SystemExit("병합 결과에 지역·일자 중복이 생겼습니다.")

    expected_start = pd.Timestamp(args.expected_start)
    expected_end = pd.Timestamp(args.expected_end)
    expected_days = (expected_end - expected_start).days + 1
    counts = merged.groupby("region")["date"].nunique()
    problems = []
    if merged["date"].min() != expected_start:
        problems.append(f"시작일 {merged['date'].min().date()} != {expected_start.date()}")
    if merged["date"].max() != expected_end:
        problems.append(f"종료일 {merged['date'].max().date()} != {expected_end.date()}")
    if merged["region"].nunique() != args.expected_regions:
        problems.append(f"지역 {merged['region'].nunique()}개 != {args.expected_regions}개")
    bad_counts = counts[counts != expected_days]
    if len(bad_counts):
        problems.append(f"일수 불일치 지역 {len(bad_counts)}개")
    if problems:
        raise SystemExit("최종 검증 실패: " + "; ".join(problems))

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    merged.to_csv(output, index=False, encoding="utf-8-sig")
    report = {
        "older_file": str(args.older.resolve()),
        "newer_file": str(args.newer.resolve()),
        "output_file": str(output),
        "overlap": {"start": str(overlap_start.date()), "end": str(overlap_end.date()), "days": overlap_days},
        "older_to_newer_scale": scale,
        "overlap_correlation_median": corr_median,
        "overlap_correlation_p10": corr_p10,
        "rows": int(len(merged)),
        "regions": int(merged["region"].nunique()),
        "date_min": str(expected_start.date()),
        "date_max": str(expected_end.date()),
        "days_per_region": expected_days,
    }
    args.report.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[병합 완료] {output}")
    print(f"  {len(merged):,}행 · {report['regions']}개 지역 · {report['date_min']}~{report['date_max']}")
    print(f"  앞 구간 보정배율 {scale:.8f} · 겹침 상관계수 중앙값 {corr_median:.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
