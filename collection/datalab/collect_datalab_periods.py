#!/usr/bin/env python3
"""18개월 제한에 맞춰 여러 기간을 순차 수집하는 실행 관리자."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_PERIODS = "202401:202506,202507:202608"


def parse_periods(raw: str) -> list[tuple[str, str]]:
    periods = []
    for item in raw.split(","):
        match = re.fullmatch(r"\s*(\d{6})\s*:\s*(\d{6})\s*", item)
        if not match:
            raise SystemExit(f"기간 형식 오류: {item!r} (예: 202401:202506)")
        start, end = match.groups()
        sy, sm, ey, em = int(start[:4]), int(start[4:]), int(end[:4]), int(end[4:])
        months = (ey - sy) * 12 + em - sm + 1
        if not (1 <= sm <= 12 and 1 <= em <= 12 and 1 <= months <= 18):
            raise SystemExit(f"기간은 구간별 1~18개월이어야 합니다: {start}~{end}")
        periods.append((start, end))
    if not periods:
        raise SystemExit("수집 기간이 없습니다.")
    return periods


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="데이터랩 여러 기간 연속 수집",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--periods", default=DEFAULT_PERIODS,
                   help="쉼표로 구분한 START:END 목록. 각 구간 최대 18개월")
    p.add_argument("--tabs", default="2,3,4,5")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--start-at", default="")
    p.add_argument("--output-dir", default="datalab_downloads")
    p.add_argument("--browser", choices=["chrome", "msedge", "chromium"], default="chrome")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--max-consecutive-failures", type=int, default=5)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    periods = parse_periods(args.periods)
    base = Path(__file__).resolve().parent
    collector = base / "collect_datalab_downloads.py"
    print(f"[전체 계획] {len(periods)}개 구간: " + ", ".join(f"{s}~{e}" for s, e in periods))
    print("중단되더라도 같은 명령을 다시 실행하면 완료 파일을 건너뛰고 이어서 진행합니다.\n")

    for index, (start, end) in enumerate(periods, start=1):
        print(f"\n{'=' * 72}\n[구간 {index}/{len(periods)}] {start}~{end}\n{'=' * 72}")
        command = [
            sys.executable, str(collector),
            "--start", start, "--end", end,
            "--tabs", args.tabs,
            "--output-dir", args.output_dir,
            "--browser", args.browser,
            "--timeout", str(args.timeout),
            "--delay", str(args.delay),
            "--retries", str(args.retries),
            "--max-consecutive-failures", str(args.max_consecutive_failures),
        ]
        if args.limit > 0:
            command.extend(["--limit", str(args.limit)])
        if args.start_at:
            command.extend(["--start-at", args.start_at])
        result = subprocess.run(command, cwd=base, check=False)
        if result.returncode != 0:
            print(f"\n[중단] {start}~{end} 구간이 코드 {result.returncode}로 끝났습니다.")
            print("사이트·로그인 상태를 확인한 뒤 같은 명령을 다시 실행하세요.")
            return result.returncode

    print("\n모든 기간 수집이 완료됐습니다. 다음: 04_merge_downloads.cmd")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다. 같은 명령을 실행하면 이어받습니다.")
        raise SystemExit(130)
