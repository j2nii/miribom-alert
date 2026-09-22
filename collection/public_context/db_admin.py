from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, connect_db, load_environment


VALIDATION_QUERIES = (
    ("festival", """SELECT COUNT(*) AS rows_actual, COUNT(DISTINCT content_id) AS contents,
                            MIN(event_start_date) AS date_min, MAX(event_end_date) AS date_max
                     FROM raw_tourapi_festival"""),
    ("asos", """SELECT COUNT(*) AS rows_actual, COUNT(DISTINCT station_id) AS stations,
                        MIN(observed_date) AS date_min, MAX(observed_date) AS date_max
                 FROM raw_kma_asos_daily"""),
    ("warnings", """SELECT COUNT(*) AS rows_actual, COUNT(DISTINCT station_id) AS stations,
                            MIN(announcement_at) AS date_min, MAX(announcement_at) AS date_max
                     FROM raw_kma_warning"""),
    ("runs", """SELECT r.source_name, r.status, r.rows_received, r.rows_upserted,
                        r.started_at, r.finished_at
                 FROM final_collection_run r
                 JOIN (SELECT source_name, MAX(run_id) AS run_id
                       FROM final_collection_run GROUP BY source_name) latest
                   ON latest.run_id=r.run_id
                 ORDER BY r.source_name"""),
    ("anomaly_ready", """SELECT COUNT(*) AS episodes, COUNT(DISTINCT region_id) AS regions,
                                 MIN(episode_start) AS date_min, MAX(episode_end) AS date_max
                          FROM vw_anomaly_analysis_ready"""),
    ("anomaly_enriched", """SELECT COUNT(*) AS episodes,
                                    COUNT(DISTINCT region_id) AS regions,
                                    SUM(enriched_data_status='datalab_and_attraction') AS both_sources,
                                    SUM(enriched_data_status='datalab_detail_only') AS datalab_only,
                                    SUM(enriched_data_status='attraction_only') AS attraction_only,
                                    SUM(enriched_data_status='no_new_detail') AS no_new_detail
                             FROM vw_anomaly_analysis_enriched"""),
    ("mapping_gaps", """SELECT
                                (SELECT COUNT(*) FROM vw_datalab_detail_unmapped)
                                  AS datalab_unmapped,
                                (SELECT COUNT(*) FROM vw_attraction_region_unmapped)
                                  AS attraction_unmapped"""),
    ("event_evidence", """SELECT COUNT(*) AS evidence_rows,
                                  COUNT(DISTINCT region_id, episode_no) AS episodes,
                                  COUNT(DISTINCT search_type) AS search_types
                           FROM event_evidence_candidate"""),
    ("collection_queue", """SELECT collection_priority,
                                    COUNT(*) AS episodes,
                                    COUNT(DISTINCT region_id) AS regions
                             FROM vw_additional_collection_priority
                             GROUP BY collection_priority
                             ORDER BY FIELD(collection_priority,'P1','P2','P3')"""),
)


def sql_statements(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def create_tables() -> None:
    sql = (ROOT / "01_create_tables.sql").read_text(encoding="utf-8")
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            for statement in sql_statements(sql):
                cur.execute(statement)
        conn.commit()
    finally:
        conn.close()
    print("[OK] final collection tables created")


def print_rows(name: str, rows: list[dict]) -> None:
    print(f"\n[{name}]")
    if not rows:
        print("(no rows)")
        return
    columns = list(rows[0].keys())
    print("\t".join(columns))
    for row in rows:
        print("\t".join("NULL" if row[col] is None else str(row[col]) for col in columns))


def validate() -> None:
    conn = connect_db()
    failed_runs = 0
    try:
        for name, sql in VALIDATION_QUERIES:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = list(cur.fetchall())
                print_rows(name, rows)
                if name == "runs":
                    failed_runs = sum(1 for row in rows if row["status"] == "failed")
            except Exception as exc:
                print(f"\n[{name}] unavailable: {exc}")
    finally:
        conn.close()
    if failed_runs:
        print(f"\n[주의] 실패 수집 실행 {failed_runs}건이 있습니다. 같은 수집 명령을 다시 실행하세요.")
    else:
        print("\n[OK] validation completed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("create-tables", "validate"))
    args = parser.parse_args()
    load_environment()
    if args.command == "create-tables":
        create_tables()
    else:
        validate()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
