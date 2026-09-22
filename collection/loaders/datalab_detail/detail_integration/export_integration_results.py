from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "team_integration_export"


def load_environment():
    local_env = BASE_DIR / ".env"
    sibling_env = BASE_DIR.parent / "all_received_loader" / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    elif sibling_env.exists():
        load_dotenv(sibling_env)


def connect():
    password = os.environ.get("MYSQL_PASSWORD", "")
    if not password or password.startswith("CHANGE_"):
        raise RuntimeError(".env의 MYSQL_PASSWORD를 실제 비밀번호로 바꾸세요.")
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "yaho_loader"),
        password=password,
        database=os.environ.get("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


EXPORTS = {
    "anomaly_analysis_enriched.csv": """
        SELECT * FROM vw_anomaly_analysis_enriched
        ORDER BY peak_anomaly_score DESC, visitor_peak_date
    """,
    "additional_collection_priority.csv": """
        SELECT * FROM vw_additional_collection_priority
        ORDER BY FIELD(collection_priority,'P1','P2','P3'),
                 collection_priority_score DESC, visitor_peak_date DESC
    """,
    "datalab_detail_monthly_summary.csv": """
        SELECT * FROM vw_datalab_detail_monthly_summary
        ORDER BY canonical_region_id, period_start
    """,
    "datalab_detail_unmapped.csv": """
        SELECT * FROM vw_datalab_detail_unmapped
        ORDER BY rows_actual DESC, source_region_code
    """,
    "attraction_region_unmapped.csv": """
        SELECT * FROM vw_attraction_region_unmapped
        ORDER BY rows_actual DESC, province_name, district_name
    """,
    "integration_status_summary.csv": """
        SELECT 'enriched_episodes' AS metric, COUNT(*) AS value
          FROM vw_anomaly_analysis_enriched
        UNION ALL
        SELECT 'collection_queue', COUNT(*) FROM vw_additional_collection_priority
        UNION ALL
        SELECT 'datalab_unmapped_pairs', COUNT(*) FROM vw_datalab_detail_unmapped
        UNION ALL
        SELECT 'attraction_unmapped_districts', COUNT(*) FROM vw_attraction_region_unmapped
        UNION ALL
        SELECT 'detail_monthly_rows', COUNT(*) FROM vw_datalab_detail_monthly_summary
        UNION ALL
        SELECT 'attraction_monthly_rows', COUNT(*) FROM attraction_visitors_monthly_canonical
    """,
}


def export_query(conn, filename, sql):
    with conn.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
    path = OUTPUT_DIR / filename
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[출력] {filename}: {len(rows):,}행")


def main():
    load_environment()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        for filename, sql in EXPORTS.items():
            export_query(conn, filename, sql)
    finally:
        conn.close()
    print(f"[완료] {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        raise SystemExit(2)
