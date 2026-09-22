from __future__ import annotations

import argparse
import csv
import os

import pymysql
from dotenv import load_dotenv


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수가 없습니다: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="event_review_candidates.csv")
    parser.add_argument("--per-episode", type=int, default=5)
    args = parser.parse_args()
    load_dotenv(override=True)
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=required("MYSQL_USER"),
        password=required("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT evidence_id, region_id, region_name, episode_no,
                       episode_start, episode_end, search_peak_date, peak_date,
                       pattern_hint, research_priority, search_type,
                       relevance_score, is_official_domain, published_date,
                       days_from_peak, title, description, source_domain,
                       COALESCE(original_url, result_url) AS evidence_url,
                       '' AS decision, '' AS event_name, '' AS event_type,
                       '' AS event_start, '' AS event_end, '' AS review_note
                FROM vw_event_evidence_review_queue
                WHERE evidence_rank_in_episode <= %s
                ORDER BY FIELD(research_priority, 'P1', 'P2', 'P3'),
                         research_priority_score DESC,
                         region_id, episode_no, evidence_rank_in_episode
                """,
                (args.per_episode,),
            )
            rows = list(cur.fetchall())
        if not rows:
            raise RuntimeError("내보낼 검색 근거가 없습니다. 먼저 수집기를 실행하세요.")
        with open(args.output, "w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"[완료] {args.output} · {len(rows)}행")
        print("decision 열에는 accepted / rejected / duplicate 중 하나를 입력하세요.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
