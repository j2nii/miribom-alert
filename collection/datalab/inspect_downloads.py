#!/usr/bin/env python3
"""다운로드된 데이터랩 파일의 구조와 누락 여부를 빠르게 점검한다."""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("folder", nargs="?", default="datalab_downloads")
    p.add_argument("--show-columns", action="store_true")
    args = p.parse_args()
    root = Path(args.folder)
    files = sorted(x for x in root.rglob("*") if x.is_file() and x.name not in {"progress.jsonl", "progress_summary.csv"})
    print(f"파일 {len(files):,}개")
    by_ext: dict[str, int] = {}
    for path in files:
        by_ext[path.suffix.lower()] = by_ext.get(path.suffix.lower(), 0) + 1
    print("확장자:", json.dumps(by_ext, ensure_ascii=False))

    for path in files[:10]:
        print(f"\n{path} ({path.stat().st_size:,} bytes)")
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                print(" ZIP:", zf.namelist()[:20])
        elif path.suffix.lower() == ".csv" and args.show_columns:
            for enc in ("utf-8-sig", "cp949", "utf-8"):
                try:
                    with path.open("r", encoding=enc, newline="") as f:
                        r = csv.reader(f)
                        rows = [next(r) for _ in range(3)]
                    print(f" encoding={enc}")
                    for row in rows:
                        print(" ", row[:20])
                    break
                except Exception:
                    continue
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
