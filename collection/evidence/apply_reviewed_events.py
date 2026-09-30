from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import date, datetime

import pymysql
from dotenv import load_dotenv


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수가 없습니다: {name}")
    return value


def parse_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} 날짜 형식은 YYYY-MM-DD여야 합니다: {value}") from exc


def load_reviewed(path: str) -> list[dict]:
    reviewed = []
    with open(path, encoding="utf-8-sig", newline="") as fp:
        for row_no, row in enumerate(csv.DictReader(fp), start=2):
            decision = (row.get("decision") or "").strip().lower()
            if not decision:
                continue
            if decision not in {"accepted", "rejected", "duplicate"}:
                raise ValueError(f"{row_no}행 decision 값이 잘못됐습니다: {decision}")
            if not (row.get("evidence_id") or "").strip():
                raise ValueError(f"{row_no}행 evidence_id 값이 비어 있습니다.")
            row["_decision"] = decision
            if decision != "accepted":
                reviewed.append(row)
                continue
            for field in ("event_name", "event_start", "event_end"):
                if not (row.get(field) or "").strip():
                    raise ValueError(f"{row_no}행 accepted 항목의 {field} 값이 비어 있습니다.")
            start = parse_date(row["event_start"], "event_start")
            end = parse_date(row["event_end"], "event_end")
            if end < start:
                raise ValueError(f"{row_no}행 event_end가 event_start보다 빠릅니다.")
            row["_start"] = start
            row["_end"] = end
            reviewed.append(row)
    return reviewed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", default="event_review_candidates.csv")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    load_dotenv(override=True)
    rows = load_reviewed(args.csv_path)
    accepted_count = sum(row["_decision"] == "accepted" for row in rows)
    print(f"[검증] 검토 {len(rows)}건 · accepted {accepted_count}건")
    if not rows:
        print("반영할 검토 결과가 없습니다.")
        return 0
    if not args.commit:
        print("DB는 변경하지 않았습니다. 실제 적재하려면 --commit을 추가하세요.")
        return 0

    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=required("MYSQL_USER"),
        password=required("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            for row in rows:
                evidence_id = int(row["evidence_id"])
                cur.execute(
                    "SELECT region_id, COALESCE(original_url, result_url) evidence_url "
                    "FROM event_evidence_candidate WHERE evidence_id=%s",
                    (evidence_id,),
                )
                evidence = cur.fetchone()
                if not evidence:
                    raise RuntimeError(f"evidence_id {evidence_id}가 DB에 없습니다.")
                note = (row.get("review_note") or "").strip() or None
                if row["_decision"] != "accepted":
                    cur.execute(
                        """
                        INSERT INTO event_evidence_decision
                          (evidence_id, decision, review_note, reviewed_at)
                        VALUES (%s,%s,%s,NOW())
                        ON DUPLICATE KEY UPDATE
                          decision=VALUES(decision), event_name=NULL,
                          event_type=NULL, event_start=NULL, event_end=NULL,
                          review_note=VALUES(review_note), reviewed_at=NOW()
                        """,
                        (evidence_id, row["_decision"], note),
                    )
                    continue
                key_seed = (
                    f'{evidence["region_id"]}|{row["event_name"]}|{row["_start"]}'
                ).encode("utf-8")
                event_key = "WEB_" + hashlib.sha256(key_seed).hexdigest()[:24]
                cur.execute(
                    """
                    INSERT INTO event
                      (event_key, region_id, event_name, event_type,
                       evidence_url, evidence_note)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      event_name=VALUES(event_name), event_type=VALUES(event_type),
                      evidence_url=VALUES(evidence_url),
                      evidence_note=VALUES(evidence_note)
                    """,
                    (event_key, evidence["region_id"], row["event_name"].strip(),
                     (row.get("event_type") or "").strip() or None,
                     evidence["evidence_url"], note),
                )
                cur.execute("SELECT event_id FROM event WHERE event_key=%s", (event_key,))
                event_id = cur.fetchone()["event_id"]
                cur.execute(
                    """
                    INSERT INTO event_point (event_id, point_type, point_date, definition_note)
                    VALUES (%s,'T0',%s,'검토 CSV에서 확인한 행사 시작일'),
                           (%s,'end',%s,'검토 CSV에서 확인한 행사 종료일')
                    ON DUPLICATE KEY UPDATE
                      point_date=VALUES(point_date),
                      definition_note=VALUES(definition_note)
                    """,
                    (event_id, row["_start"], event_id, row["_end"]),
                )
                cur.execute(
                    """
                    INSERT INTO event_evidence_decision
                      (evidence_id, decision, event_name, event_type,
                       event_start, event_end, review_note, reviewed_at)
                    VALUES (%s,'accepted',%s,%s,%s,%s,%s,NOW())
                    ON DUPLICATE KEY UPDATE
                      decision='accepted', event_name=VALUES(event_name),
                      event_type=VALUES(event_type), event_start=VALUES(event_start),
                      event_end=VALUES(event_end), review_note=VALUES(review_note),
                      reviewed_at=NOW()
                    """,
                    (evidence_id, row["event_name"].strip(),
                     (row.get("event_type") or "").strip() or None,
                     row["_start"], row["_end"], note),
                )
        conn.commit()
        print(f"[반영 완료] 검토 {len(rows)}건 · 이벤트 {accepted_count}건")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
