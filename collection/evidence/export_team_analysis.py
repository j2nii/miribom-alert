from __future__ import annotations

import csv
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수가 없습니다: {name}")
    return value


def export_query(conn, output_path: Path, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = list(cur.fetchall())
        columns = [item[0] for item in cur.description]
    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    load_dotenv(override=True)
    output_dir = Path("team_analysis_export")
    output_dir.mkdir(exist_ok=True)
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=required("MYSQL_USER"),
        password=required("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    exports = {
        "anomaly_analysis_ready.csv": """
            SELECT *
            FROM vw_anomaly_analysis_ready
            ORDER BY peak_anomaly_score DESC, region_id, episode_no
        """,
        "anomaly_external_candidates.csv": """
            SELECT *
            FROM vw_anomaly_analysis_ready
            WHERE explanation_status IN (
              'verified_external_evidence',
              'strong_external_candidate',
              'possible_external_candidate'
            )
            ORDER BY FIELD(
              explanation_status,
              'verified_external_evidence',
              'strong_external_candidate',
              'possible_external_candidate'
            ), peak_anomaly_score DESC
        """,
        "anomaly_unresolved.csv": """
            SELECT *
            FROM vw_anomaly_analysis_unresolved
            ORDER BY peak_anomaly_score DESC, region_id, episode_no
        """,
        "analysis_status_summary.csv": """
            SELECT
              explanation_status,
              COUNT(*) AS episodes,
              COUNT(DISTINCT region_id) AS regions,
              ROUND(AVG(peak_anomaly_score), 3) AS avg_anomaly_score,
              ROUND(AVG(peak_naver_ratio), 3) AS avg_naver_ratio,
              ROUND(AVG(peak_visitor_ratio), 3) AS avg_visitor_ratio,
              ROUND(AVG(datalab_sns_mentions_mom_pct), 3)
                AS avg_sns_mom_pct,
              ROUND(AVG(datalab_navigation_searches_mom_pct), 3)
                AS avg_navigation_mom_pct,
              ROUND(AVG(datalab_outsider_spend_mom_pct), 3)
                AS avg_outsider_spend_mom_pct
            FROM vw_anomaly_analysis_ready
            GROUP BY explanation_status
            ORDER BY FIELD(
              explanation_status,
              'verified_event', 'calendar_related',
              'verified_external_evidence', 'strong_external_candidate',
              'possible_external_candidate', 'researched_unresolved',
              'not_researched'
            )
        """,
        "analysis_cause_summary.csv": """
            SELECT
              auto_cause_type,
              auto_confidence,
              COUNT(*) AS episodes,
              COUNT(DISTINCT region_id) AS regions,
              ROUND(AVG(peak_anomaly_score), 3) AS avg_anomaly_score,
              ROUND(AVG(search_to_visit_lag_days), 3) AS avg_search_to_visit_lag
            FROM vw_anomaly_analysis_ready
            WHERE explanation_status IN (
              'verified_external_evidence',
              'strong_external_candidate',
              'possible_external_candidate'
            )
            GROUP BY auto_cause_type, auto_confidence
            ORDER BY FIELD(auto_confidence, 'verified', 'high', 'medium'),
                     episodes DESC
        """,
    }
    try:
        for filename, sql in exports.items():
            count = export_query(conn, output_dir / filename, sql)
            print(f"[출력] {filename}: {count}행")
        print(f"[완료] {output_dir.resolve()}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
