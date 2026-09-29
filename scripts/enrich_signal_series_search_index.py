"""Add daily Naver search index to existing signal_series exports.

Usage: python scripts/enrich_signal_series_search_index.py --source PATH_TO_NAVER_CSV --case-only
   or: python scripts/enrich_signal_series_search_index.py --db-env PATH_TO_ENV --case-only
The source must be the same scaled series used for search_stat. Every region is
checked against its exported 7-day median YoY statistic before files are changed.
"""

import argparse
import csv
import json
import ssl
from datetime import date, timedelta
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "data" / "prod"


def read_source(path):
    values = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            values.setdefault(row["region"], {})[row["date"]] = float(row["value"])
    return values


def read_db_source(env_path, documents):
    import pymysql
    from dotenv import dotenv_values

    settings = dotenv_values(env_path)
    prefix = "DB_" if settings.get("DB_HOST") else "MYSQL_"
    database_key = "DB_NAME" if prefix == "DB_" else "MYSQL_DATABASE"
    codes = [document["data"]["region"]["code"] for _, document in documents]
    first = min(row["date"] for _, document in documents for row in document["data"]["daily"])
    last = max(document["data"]["as_of"]["search"] for _, document in documents)
    placeholders = ",".join(["%s"] * len(codes))
    sql = ("SELECT region_id, observed_date, value FROM fact_signal "
           f"WHERE metric='interest_naver' AND region_id IN ({placeholders}) "
           "AND observed_date BETWEEN %s AND %s")
    connection = pymysql.connect(
        host=settings[prefix + "HOST"],
        port=int(settings.get(prefix + "PORT") or 3306),
        user=settings[prefix + "USER"],
        password=settings[prefix + "PASSWORD"],
        database=settings[database_key],
        ssl={"check_hostname": False, "verify_mode": ssl.CERT_NONE},
        connect_timeout=15,
        read_timeout=60,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, (*codes, first, last))
            records = cursor.fetchall()
    finally:
        connection.close()
    values = {code: {} for code in codes}
    for code, observed_date, value in records:
        day = observed_date.isoformat() if isinstance(observed_date, date) else str(observed_date)
        if day in values[str(code)]:
            raise ValueError(f"{code}: duplicate Naver index on {day}")
        values[str(code)][day] = float(value)
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
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--source", type=Path)
    input_group.add_argument("--db-env", type=Path)
    parser.add_argument("--case-only", action="store_true", help="Update only the six top-level showcase regions")
    args = parser.parse_args()
    files = sorted(PROD.glob("signal_series*.json") if args.case_only else PROD.rglob("signal_series*.json"))
    documents = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in files]
    source = read_source(args.source) if args.source else read_db_source(args.db_env, documents)
    updates = []
    for path, document in documents:
        code = document["data"]["region"]["code"]
        if code not in source:
            raise ValueError(f"{code}: no Naver source series")
        verify(document["data"], source[code])
        missing = [row["date"] for row in document["data"]["daily"] if row["date"] not in source[code]]
        if missing:
            raise ValueError(f"{code}: missing Naver source dates, first {missing[0]}")
        updates.append((path, document, source[code]))
    for path, document, raw in updates:
        for row in document["data"]["daily"]:
            row["search_index"] = raw[row["date"]]
        path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Updated {len(updates)} signal_series files")


if __name__ == "__main__":
    main()
