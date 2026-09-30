from __future__ import annotations

import argparse
import sys
import time

import requests
from dotenv import load_dotenv

from collect_event_evidence import (
    SEARCH_TYPES,
    api_search,
    connect_db,
    env_required,
    load_targets,
    save_items,
)


QUERY_TEMPLATES = (
    ("planned_event", "{region} {year}년 {month}월 축제 행사 대회 공연"),
    ("disruption", "{region} {year}년 {month}월 폭우 산불 사고 통제 재난"),
    ("viral_media", "{region} {year}년 {month}월 방송 촬영지 유튜브 핫플 맛집"),
    ("access_offer", "{region} {year}년 {month}월 개장 개통 무료 할인 관광"),
)


def query_specs(row: dict) -> list[tuple[str, str]]:
    peak = row["peak_date"]
    values = {
        "region": row["region_name"],
        "year": peak.year,
        "month": peak.month,
    }
    return [(category, template.format(**values))
            for category, template in QUERY_TEMPLATES]


def checkpoint_succeeded(conn, row: dict, category: str,
                         search_type: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT status FROM event_evidence_targeted_checkpoint
               WHERE region_id=%s AND episode_no=%s
                 AND query_category=%s AND search_type=%s""",
            (row["region_id"], row["episode_no"], category, search_type),
        )
        found = cur.fetchone()
    return bool(found and found["status"] == "success")


def save_checkpoint(conn, row: dict, category: str, search_type: str,
                    status: str, result_count: int = 0,
                    error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_evidence_targeted_checkpoint
              (region_id, episode_no, query_category, search_type, status,
               attempt_count, result_count, last_attempt_at, last_error)
            VALUES (%s,%s,%s,%s,%s,1,%s,NOW(),%s)
            ON DUPLICATE KEY UPDATE
              status=VALUES(status), attempt_count=attempt_count+1,
              result_count=VALUES(result_count), last_attempt_at=NOW(),
              last_error=VALUES(last_error)
            """,
            (row["region_id"], row["episode_no"], category, search_type,
             status, result_count, error[:4000] if error else None),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", default="P1,P2")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--display", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    if not 1 <= args.display <= 100:
        parser.error("--display는 1~100이어야 합니다.")

    load_dotenv(override=True)
    client_id = env_required("NAVER_API_HUB_CLIENT_ID")
    client_secret = env_required("NAVER_API_HUB_CLIENT_SECRET")
    tiers = [x.strip().upper() for x in args.tiers.split(",") if x.strip()]
    if not tiers or any(x not in {"P1", "P2", "P3"} for x in tiers):
        parser.error("--tiers는 P1,P2,P3 중 하나 이상이어야 합니다.")

    conn = connect_db()
    session = requests.Session()
    api_calls = stored_total = failures = skipped = 0
    errors: list[str] = []
    try:
        print("[인증 확인] NAVER API HUB 검색 API를 1회 시험합니다.")
        api_search(session, client_id, client_secret, "news", "관광 축제", 1)
        print("[인증 성공]")
        targets = load_targets(conn, tiers, args.limit)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO event_evidence_run (target_episodes) VALUES (%s)",
                (len(targets),),
            )
            run_id = cur.lastrowid
        conn.commit()
        total_planned = len(targets) * len(QUERY_TEMPLATES) * len(SEARCH_TYPES)
        print(f"[대상] {len(targets)}개 에피소드 · 최대 {total_planned}회 호출")
        print("[범주] 행사 · 재난/통제 · 미디어/바이럴 · 개장/혜택")

        for index, row in enumerate(targets, start=1):
            print(f'[{index}/{len(targets)}] {row["region_name"]} '
                  f'{row["peak_date"]} {row["research_priority"]}')
            for category, query in query_specs(row):
                for search_type in SEARCH_TYPES:
                    if checkpoint_succeeded(conn, row, category, search_type):
                        skipped += 1
                        continue
                    try:
                        payload = api_search(
                            session, client_id, client_secret,
                            search_type, query, args.display,
                        )
                        api_calls += 1
                        stored = save_items(
                            conn, run_id, row, search_type, query, payload
                        )
                        save_checkpoint(
                            conn, row, category, search_type,
                            "success", stored,
                        )
                        conn.commit()
                        stored_total += stored
                        print(f"  [성공] {category}/{search_type}: {stored}건")
                        time.sleep(max(0.0, args.delay))
                    except Exception as exc:
                        conn.rollback()
                        failures += 1
                        message = (f'{row["region_name"]}/{row["peak_date"]}/'
                                   f'{category}/{search_type}: {exc}')
                        errors.append(message)
                        save_checkpoint(
                            conn, row, category, search_type,
                            "failed", error=str(exc),
                        )
                        conn.commit()
                        print(f"  [실패] {category}/{search_type}: {exc}")

        status = "success" if failures == 0 else "partial"
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE event_evidence_run
                   SET finished_at=NOW(), status=%s, api_calls=%s,
                       stored_results=%s, failure_count=%s, error_summary=%s
                   WHERE evidence_run_id=%s""",
                (status, api_calls, stored_total, failures,
                 "\n".join(errors[:50]) or None, run_id),
            )
        conn.commit()
        print(f"[완료] API {api_calls}회 · 저장 시도 {stored_total}건 · "
              f"건너뜀 {skipped}회 · 실패 {failures}건")
        return 0 if failures == 0 else 2
    finally:
        session.close()
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        raise SystemExit(1)
