from __future__ import annotations

import csv
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError



ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "collected_data"
try:
    KST = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    # Windows Python installations may not ship the IANA time-zone database.
    # Korea has used UTC+09:00 without daylight-saving time since 1988, so this
    # fixed-offset fallback preserves the collection deadline correctly even
    # before the optional tzdata wheel is installed.
    KST = timezone(timedelta(hours=9), name="KST")
COLLECTION_DEADLINE = datetime(2026, 9, 22, 23, 59, 59, tzinfo=KST)


def load_environment() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")


def env_required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith("CHANGE_"):
        raise RuntimeError(f".env의 {name} 값을 실제 값으로 변경하세요.")
    return value


def service_key(kind: str) -> str:
    specific = (os.getenv(f"{kind}_API_SERVICE_KEY") or "").strip()
    value = specific or env_required("DATA_GO_KR_SERVICE_KEY")
    return unquote(value)


def assert_collection_open(now: datetime | None = None) -> None:
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    if current > COLLECTION_DEADLINE:
        raise RuntimeError(
            "수집 마감(2026-09-22 23:59:59 KST)이 지났습니다. "
            "프로젝트 규칙에 따라 신규 API 수집을 실행하지 않습니다. "
            "검증·내보내기·분석만 진행하세요."
        )


def connect_db(autocommit: bool = False):
    import pymysql

    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=env_required("MYSQL_USER"),
        password=env_required("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=autocommit,
        cursorclass=pymysql.cursors.DictCursor,
    )


def collection_range() -> tuple[date, date]:
    start = date.fromisoformat(os.getenv("COLLECTION_START_DATE", "2023-01-01"))
    end = date.fromisoformat(os.getenv("COLLECTION_END_DATE", "2026-08-31"))
    if start > end:
        raise RuntimeError("COLLECTION_START_DATE가 COLLECTION_END_DATE보다 늦습니다.")
    return start, end


def normalize_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    response = payload.get("response", payload)
    header = response.get("header", {}) if isinstance(response, dict) else {}
    result_code = str(header.get("resultCode", "00"))
    if result_code not in {"00", "0000"}:
        raise RuntimeError(
            f"API 오류 {result_code}: {header.get('resultMsg') or header.get('resultMessage')}"
        )
    body = response.get("body", {}) if isinstance(response, dict) else {}
    total = int(body.get("totalCount") or 0)
    items = body.get("items", {})
    if not items or isinstance(items, str):
        return [], total
    rows = items.get("item", []) if isinstance(items, dict) else items
    if isinstance(rows, dict):
        rows = [rows]
    return list(rows or []), total


def api_get_json(
    session: Any,
    url: str,
    params: dict[str, Any],
    *,
    attempts: int = 4,
) -> dict[str, Any]:
    import requests

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=60)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                snippet = response.text[:500].replace("\n", " ")
                raise RuntimeError(f"JSON이 아닌 API 응답입니다: {snippet}") from exc
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            wait = 2 ** (attempt - 1)
            print(f"  [재시도 {attempt}/{attempts}] {exc} · {wait}초 대기")
            time.sleep(wait)
    raise RuntimeError(f"API 호출 실패: {last_error}")


def as_float(value: Any) -> float | None:
    if value is None or str(value).strip() in {"", "-"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any, *formats: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def parse_datetime(value: Any, *formats: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def start_run(conn, source_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE final_collection_run
               SET finished_at=CURRENT_TIMESTAMP, status='failed',
                   error_message=COALESCE(
                       error_message,
                       '이전 실행이 완료되지 않아 후속 실행에서 중단 상태로 정리됨'
                   )
               WHERE source_name=%s AND status='running'""",
            (source_name,),
        )
        cur.execute(
            "INSERT INTO final_collection_run(source_name,status) VALUES (%s,'running')",
            (source_name,),
        )
        run_id = int(cur.lastrowid)
    conn.commit()
    return run_id


def finish_run(
    conn,
    run_id: int,
    status: str,
    rows_received: int,
    rows_upserted: int,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE final_collection_run
               SET finished_at=CURRENT_TIMESTAMP, status=%s, rows_received=%s,
                   rows_upserted=%s, error_message=%s
               WHERE run_id=%s""",
            (status, rows_received, rows_upserted, error_message, run_id),
        )
    conn.commit()


def export_query_csv(conn, sql: str, path: Path) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [item[0] for item in cur.description]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def month_chunks(start: date, end: date) -> Iterable[tuple[date, date]]:
    current = start.replace(day=1)
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        chunk_start = max(start, current)
        chunk_end = min(end, date.fromordinal(next_month.toordinal() - 1))
        yield chunk_start, chunk_end
        current = next_month


def day_chunks(start: date, end: date, days: int) -> Iterable[tuple[date, date]]:
    if days < 1:
        raise ValueError("days must be at least 1")
    current = start
    while current <= end:
        chunk_end = min(end, current + timedelta(days=days - 1))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)
