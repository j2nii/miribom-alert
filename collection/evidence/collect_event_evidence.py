from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import pymysql
import requests
from dotenv import load_dotenv


SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/{search_type}"
SEARCH_TYPES = ("news", "blog", "webkr")
EVENT_WORDS = ("축제", "행사", "페스티벌", "관광", "공연", "대회", "박람회")
OFFICIAL_SUFFIXES = (
    ".go.kr",
    ".or.kr",
    "visitkorea.or.kr",
    "korean.visitkorea.or.kr",
)
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str:
    return html.unescape(TAG_RE.sub("", value or "")).strip()


def env_required(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            value = value.strip()
            if value.startswith("CHANGE_"):
                raise RuntimeError(f".env의 {name} 값을 실제 값으로 변경하세요.")
            return value
    raise RuntimeError(f"환경변수가 없습니다: {' 또는 '.join(names)}")


def connect_db():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=env_required("MYSQL_USER"),
        password=env_required("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def parse_result_date(search_type: str, item: dict) -> date | None:
    try:
        if search_type == "news" and item.get("pubDate"):
            return parsedate_to_datetime(item["pubDate"]).date()
        if search_type == "blog" and item.get("postdate"):
            return datetime.strptime(item["postdate"], "%Y%m%d").date()
    except (TypeError, ValueError, OverflowError):
        return None
    return None


def result_domain(search_type: str, item: dict) -> str:
    url = item.get("originallink") if search_type == "news" else item.get("link")
    if not url:
        url = item.get("link", "")
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_official(domain: str) -> bool:
    return any(domain == suffix.lstrip(".") or domain.endswith(suffix)
               for suffix in OFFICIAL_SUFFIXES)


def relevance(item: dict, search_type: str, region_name: str,
              peak_date: date) -> tuple[float, date | None, int | None, str, bool]:
    title = clean_text(item.get("title"))
    description = clean_text(item.get("description"))
    combined = f"{title} {description}"
    published = parse_result_date(search_type, item)
    days = (published - peak_date).days if published else None
    domain = result_domain(search_type, item)
    official = is_official(domain)

    score = {"news": 5.0, "webkr": 3.0, "blog": 1.0}[search_type]
    if region_name in combined:
        score += 4.0
    if any(word in combined for word in EVENT_WORDS):
        score += 4.0
    if official:
        score += 8.0
    if days is not None:
        distance = abs(days)
        if distance <= 30:
            score += 5.0
        elif distance <= 90:
            score += 3.0
        elif distance <= 180:
            score += 1.0
        else:
            score -= 2.0
    return score, published, days, domain, official


def query_text(row: dict) -> str:
    peak = row["peak_date"]
    return f'{row["region_name"]} {peak.year}년 {peak.month}월 축제 행사 관광'


def api_search(session: requests.Session, client_id: str, client_secret: str,
               search_type: str, query: str, display: int) -> dict:
    params = {
        "query": query,
        "display": display,
        "start": 1,
        "format": "json",
    }
    if search_type != "webkr":
        params["sort"] = "sim"
    response = session.get(
        SEARCH_URL.format(search_type=search_type),
        headers={
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
        },
        params=params,
        timeout=30,
    )
    if response.status_code in (401, 403, 429):
        try:
            body = response.json()
            detail = body.get("errorMessage") or body.get("errMsg")
            nested = body.get("error")
            if not detail and isinstance(nested, dict):
                detail = nested.get("message") or nested.get("details")
            detail = detail or response.text
        except ValueError:
            detail = response.text
        detail = clean_text(detail)[:300]
        if response.status_code == 401:
            raise RuntimeError(
                "NAVER API HUB 인증 실패(401). .env의 API HUB Client ID와 "
                "Client Secret이 정확한지, 애플리케이션에 검색 API가 "
                f"등록됐는지 확인하세요. 서버 응답: {detail}"
            )
        if response.status_code == 403:
            raise RuntimeError(
                "NAVER API HUB 권한 없음(403). 해당 애플리케이션의 사용 API에 "
                f"'검색'을 추가하세요. 서버 응답: {detail}"
            )
        raise RuntimeError(
            "NAVER API HUB 일일 호출 한도 초과(429)입니다. 한도가 "
            f"초기화된 뒤 다시 실행하세요. 서버 응답: {detail}"
        )
    response.raise_for_status()
    return response.json()


def load_targets(conn, tiers: list[str], limit: int) -> list[dict]:
    placeholders = ",".join(["%s"] * len(tiers))
    sql = f"""
        SELECT *
        FROM vw_event_research_priority
        WHERE research_priority IN ({placeholders})
        ORDER BY FIELD(research_priority, 'P1', 'P2', 'P3'),
                 research_priority_score DESC,
                 peak_date
    """
    params: list[object] = list(tiers)
    if limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def checkpoint_succeeded(conn, row: dict, search_type: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT status FROM event_evidence_checkpoint
               WHERE region_id=%s AND episode_no=%s AND search_type=%s""",
            (row["region_id"], row["episode_no"], search_type),
        )
        found = cur.fetchone()
    return bool(found and found["status"] == "success")


def clear_target(conn, row: dict, search_type: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM event_evidence_candidate
               WHERE region_id=%s AND episode_no=%s AND search_type=%s""",
            (row["region_id"], row["episode_no"], search_type),
        )
        cur.execute(
            """DELETE FROM event_evidence_checkpoint
               WHERE region_id=%s AND episode_no=%s AND search_type=%s""",
            (row["region_id"], row["episode_no"], search_type),
        )


def save_items(conn, run_id: int, row: dict, search_type: str,
               query: str, payload: dict) -> int:
    stored = 0
    peak_date = row["peak_date"]
    with conn.cursor() as cur:
        for rank, item in enumerate(payload.get("items", []), start=1):
            title = clean_text(item.get("title"))
            description = clean_text(item.get("description"))
            result_url = item.get("link") or item.get("originallink") or ""
            original_url = item.get("originallink")
            if not title or not result_url:
                continue
            score, published, days, domain, official = relevance(
                item, search_type, row["region_name"], peak_date
            )
            digest = hashlib.sha256(result_url.encode("utf-8")).hexdigest()
            cur.execute(
                """
                INSERT INTO event_evidence_candidate
                  (evidence_run_id, region_id, episode_no, peak_date,
                   search_type, query_text, result_rank, title, description,
                   result_url, original_url, source_domain, published_date,
                   days_from_peak, is_official_domain, relevance_score,
                   result_hash, raw_json)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  evidence_run_id=VALUES(evidence_run_id),
                  query_text=VALUES(query_text),
                  result_rank=VALUES(result_rank),
                  title=VALUES(title),
                  description=VALUES(description),
                  original_url=VALUES(original_url),
                  source_domain=VALUES(source_domain),
                  published_date=VALUES(published_date),
                  days_from_peak=VALUES(days_from_peak),
                  is_official_domain=VALUES(is_official_domain),
                  relevance_score=VALUES(relevance_score),
                  raw_json=VALUES(raw_json),
                  collected_at=CURRENT_TIMESTAMP
                """,
                (
                    run_id, row["region_id"], row["episode_no"], peak_date,
                    search_type, query, rank, title, description,
                    result_url, original_url, domain or None, published,
                    days, int(official), score, digest,
                    json.dumps(item, ensure_ascii=False),
                ),
            )
            stored += 1
        cur.execute(
            """
            INSERT INTO event_evidence_checkpoint
              (region_id, episode_no, search_type, status, attempt_count,
               result_count, last_attempt_at, last_error)
            VALUES (%s,%s,%s,'success',1,%s,NOW(),NULL)
            ON DUPLICATE KEY UPDATE
              status='success', attempt_count=attempt_count+1,
              result_count=VALUES(result_count), last_attempt_at=NOW(),
              last_error=NULL
            """,
            (row["region_id"], row["episode_no"], search_type, stored),
        )
    return stored


def save_failure(conn, row: dict, search_type: str, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_evidence_checkpoint
              (region_id, episode_no, search_type, status, attempt_count,
               result_count, last_attempt_at, last_error)
            VALUES (%s,%s,%s,'failed',1,0,NOW(),%s)
            ON DUPLICATE KEY UPDATE
              status='failed', attempt_count=attempt_count+1,
              last_attempt_at=NOW(), last_error=VALUES(last_error)
            """,
            (row["region_id"], row["episode_no"], search_type, error[:4000]),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", default="P1,P2",
                        help="수집 우선순위. 기본 P1,P2; 전체 P1,P2,P3")
    parser.add_argument("--limit", type=int, default=100,
                        help="에피소드 수. 0이면 제한 없음")
    parser.add_argument("--display", type=int, default=10,
                        help="검색 종류별 결과 수(1~100)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="API 호출 사이 대기 초")
    parser.add_argument("--refresh", action="store_true",
                        help="성공 체크포인트도 지우고 다시 수집")
    args = parser.parse_args()
    if not 1 <= args.display <= 100:
        parser.error("--display는 1~100이어야 합니다.")

    # Prefer this folder's .env over old system/session variables.
    load_dotenv(override=True)
    client_id = env_required("NAVER_API_HUB_CLIENT_ID")
    client_secret = env_required("NAVER_API_HUB_CLIENT_SECRET")
    tiers = [x.strip().upper() for x in args.tiers.split(",") if x.strip()]
    if not tiers or any(x not in {"P1", "P2", "P3"} for x in tiers):
        parser.error("--tiers는 P1,P2,P3 중 하나 이상이어야 합니다.")

    conn = connect_db()
    session = requests.Session()
    api_calls = stored_total = failures = 0
    errors: list[str] = []
    try:
        print(f"[환경 확인] Client ID {len(client_id)}자 · Client Secret {len(client_secret)}자")
        print("[인증 확인] NAVER API HUB 검색 API를 1회 시험합니다.")
        api_search(
            session, client_id, client_secret,
            "news", "관광 축제", 1,
        )
        print("[인증 성공]")
        targets = load_targets(conn, tiers, args.limit)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO event_evidence_run (target_episodes) VALUES (%s)",
                (len(targets),),
            )
            run_id = cur.lastrowid
        conn.commit()
        print(f"[대상] {len(targets)}개 에피소드 · 우선순위 {tiers}")

        for index, row in enumerate(targets, start=1):
            query = query_text(row)
            print(f'[{index}/{len(targets)}] {row["region_name"]} '
                  f'{row["peak_date"]} {row["research_priority"]}')
            for search_type in SEARCH_TYPES:
                try:
                    if args.refresh:
                        clear_target(conn, row, search_type)
                        conn.commit()
                    elif checkpoint_succeeded(conn, row, search_type):
                        print(f"  [건너뜀] {search_type}")
                        continue
                    payload = api_search(
                        session, client_id, client_secret,
                        search_type, query, args.display,
                    )
                    api_calls += 1
                    stored = save_items(
                        conn, run_id, row, search_type, query, payload
                    )
                    conn.commit()
                    stored_total += stored
                    print(f"  [성공] {search_type}: {stored}건")
                    time.sleep(max(0.0, args.delay))
                except Exception as exc:  # checkpoint each isolated target
                    conn.rollback()
                    failures += 1
                    message = f'{row["region_name"]}/{row["peak_date"]}/{search_type}: {exc}'
                    errors.append(message)
                    save_failure(conn, row, search_type, str(exc))
                    conn.commit()
                    print(f"  [실패] {search_type}: {exc}")

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
        print(f"[완료] API {api_calls}회 · 저장 {stored_total}건 · 실패 {failures}건")
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
