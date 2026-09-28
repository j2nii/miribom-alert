"""Load the six official DataLab daily visitor series into the live MySQL DB.

Only dates after the legacy API coverage (2026-08-14) are loaded. The original
API rows and the frozen 2026-09-22 analysis snapshot are left intact.

Example:
    python collection/datalab/load_daily_visitors_mysql.py --env C:/path/to/loader/.env
    python collection/datalab/load_daily_visitors_mysql.py --env C:/path/to/loader/.env --commit
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data" / "raw" / "datalab_daily" / "daily_visitors_case.csv"
REGIONS = {"12130", "47940", "48310", "51210", "51750", "51810"}
SOURCE = "kto_datalab_daily"
START = date(2026, 8, 15)
END = date(2026, 9, 23)


def env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def get_env(values: dict[str, str], name: str) -> str:
    for prefix in ("MYSQL_", "DB_"):
        if values.get(prefix + name):
            return values[prefix + name]
    raise ValueError(f"Missing {name} in the DB environment file")


def read_rows(path: Path) -> list[tuple[str, str, str, int]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["region", "date", "tou_div", "value"]:
            raise ValueError(f"Unexpected columns: {reader.fieldnames}")
        data = list(reader)
    if len(data) != 648:
        raise ValueError(f"Expected 648 source rows, found {len(data)}")
    keys = {(r["region"], r["date"], r["tou_div"]) for r in data}
    if len(keys) != len(data):
        raise ValueError("Duplicate region/date/tou_div key in CSV")
    expected_dates = {(START - timedelta(days=14) + timedelta(days=i)).isoformat()
                      for i in range((END - START).days + 15)}
    expected_keys = {(region, day, segment)
                     for region in REGIONS for day in expected_dates for segment in ("1", "2")}
    if keys != expected_keys:
        raise ValueError("CSV does not contain the complete expected six-region date series")
    result = []
    for r in data:
        value = int(r["value"])
        if value < 0:
            raise ValueError("Negative visitor count")
        if r["date"] >= START.isoformat():
            segment = "local" if r["tou_div"] == "1" else "external"
            result.append((r["region"], r["date"], segment, value))
    if len(result) != 480:
        raise ValueError(f"Expected 480 new rows, found {len(result)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--commit", action="store_true", help="Write to live DB; otherwise dry-run")
    args = parser.parse_args()
    rows = read_rows(args.csv)
    digest = hashlib.sha256(args.csv.read_bytes()).hexdigest()
    print("CSV SHA256:", digest)
    print("New rows:", len(rows), dict(Counter(r[2] for r in rows)))

    values = env_file(args.env)
    conn = pymysql.connect(
        host=get_env(values, "HOST"),
        port=int(values.get("MYSQL_PORT") or values.get("DB_PORT") or 3306),
        user=get_env(values, "USER"),
        password=get_env(values, "PASSWORD"),
        database=values.get("MYSQL_DATABASE") or values.get("DB_NAME") or "tour_earlywarning",
        charset="utf8mb4",
        connect_timeout=15,
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE(), CURRENT_USER()")
            database, user = cur.fetchone()
            print("DB:", database, "as", user)
            if database != "tour_earlywarning":
                raise ValueError(f"Unexpected database: {database}")
            cur.execute(
                """SELECT region_id, observed_date, segment, value FROM fact_signal
                   WHERE source_system=%s AND metric='realization_visitors'
                     AND observed_date BETWEEN %s AND %s
                     AND region_id IN ('12130','47940','48310','51210','51750','51810')""",
                (SOURCE, START, END),
            )
            old = {(region, day.isoformat(), segment): int(value)
                   for region, day, segment, value in cur.fetchall()}
            expected = {(region, day, segment): value for region, day, segment, value in rows}
            conflict = [key for key, value in old.items() if expected.get(key) != value]
            if conflict:
                raise ValueError(f"Existing DataLab rows differ from CSV: {conflict[:5]}")
            print("Existing matching rows:", len(old))
            if not args.commit:
                print("Dry-run complete; no DB changes")
                return

            cur.execute(
                """INSERT INTO source_file(file_name,sha256,byte_size,row_count,note)
                   VALUES (%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE source_file_id=LAST_INSERT_ID(source_file_id)""",
                (args.csv.name, digest, args.csv.stat().st_size, 648,
                 "한국관광 데이터랩 공식 일별 ZIP 병합; 6지역 2026-08-01~09-23"),
            )
            file_id = cur.lastrowid
            cur.executemany(
                """INSERT INTO fact_signal
                   (region_id,source_region_id,observed_date,metric,segment,value,
                    source_system,granularity,source_file_id)
                   VALUES (%s,%s,%s,'realization_visitors',%s,%s,%s,'day',%s)
                   ON DUPLICATE KEY UPDATE source_file_id=VALUES(source_file_id)""",
                [(region, region, day, segment, value, SOURCE, file_id)
                 for region, day, segment, value in rows],
            )
            cur.execute(
                """INSERT INTO analysis_calendar
                   (calendar_date,calendar_year,calendar_month,day_of_month,
                    day_of_week,iso_year_week,is_weekend)
                   SELECT DISTINCT observed_date,YEAR(observed_date),MONTH(observed_date),
                          DAY(observed_date),WEEKDAY(observed_date)+1,
                          YEARWEEK(observed_date,3),WEEKDAY(observed_date) IN (5,6)
                   FROM fact_signal
                   WHERE source_system=%s AND metric='realization_visitors'
                     AND observed_date BETWEEN %s AND %s
                   ON DUPLICATE KEY UPDATE
                     calendar_year=VALUES(calendar_year),calendar_month=VALUES(calendar_month),
                     day_of_month=VALUES(day_of_month),day_of_week=VALUES(day_of_week),
                     iso_year_week=VALUES(iso_year_week),is_weekend=VALUES(is_weekend)""",
                (SOURCE, START, END),
            )
            cur.execute(
                """SELECT COUNT(*) FROM fact_signal WHERE source_system=%s
                   AND metric='realization_visitors' AND observed_date BETWEEN %s AND %s
                   AND region_id IN ('12130','47940','48310','51210','51750','51810')""",
                (SOURCE, START, END),
            )
            if cur.fetchone()[0] != 480:
                raise ValueError("DB row count after load is not 480")
        conn.commit()
        print("Committed 480 visitor rows and calendar dates through", END)
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
