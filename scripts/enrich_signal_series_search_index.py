"""Add daily Naver search index to existing signal_series exports.

Usage: python scripts/enrich_signal_series_search_index.py --source PATH_TO_NAVER_CSV
The source must be the same scaled series used for search_stat. Every region is
checked against its exported 7-day median YoY statistic before files are changed.
"""

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "data" / "prod").rglob("signal_series*.json"))


def read_source(path):
    values = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            values.setdefault(row["region"], {})[row["date"]] = float(row["value"])
    return values


def verify(data, raw):
    code = data["region"]["code"]
    end = min(data["as_of"]["search"], data["as_of"]["visitors"])
    exported = next((row["search_stat"] for row in data["daily"] if row["date"] == end), None)
    if exported is None:
        raise ValueError(f"{code}: missing search_stat at {end}")
    last = date.fromisoformat(end)
    ratios = []
    for offset in range(6, -1, -1):
        current = last - timedelta(days=offset)
        previous = current - timedelta(days=364)
        ratios.append(raw[current.isoformat()] / raw[previous.isoformat()])
    if abs(median(ratios) - exported) > 0.011:
        raise ValueError(f"{code}: Naver scale differs from exported search_stat")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = read_source(args.source)
    documents = []
    for path in FILES:
        document = json.loads(path.read_text(encoding="utf-8"))
        code = document["data"]["region"]["code"]
        if code not in source:
            raise ValueError(f"{code}: no Naver source series")
        verify(document["data"], source[code])
        documents.append((path, document, source[code]))
    for path, document, raw in documents:
        for row in document["data"]["daily"]:
            row["search_index"] = raw.get(row["date"])
        path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Updated {len(documents)} signal_series files from {args.source}")


if __name__ == "__main__":
    main()
