#!/usr/bin/env python3
"""Validate and UPSERT manually verified tourism events into MySQL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path


COLUMNS = (
    "event_key", "region_id", "event_name", "event_type",
    "t0_date", "ta_date", "tb_date", "end_date",
    "evidence_url", "evidence_note",
)
POINT_COLUMNS = {
    "T0": "t0_date",
    "Ta": "ta_date",
    "Tb": "tb_date",
    "end": "end_date",
}


def args() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="이벤트 CSV 검증 및 MySQL 적재")
    p.add_argument("csv", type=Path, nargs="?", default=base / "events_template.csv")
    p.add_argument(
        "--env", type=Path,
        default=(base / "../yaho_mysql_setup/.env").resolve(),
    )
    p.add_argument("--commit", action="store_true", help="검증 후 DB에 실제 반영")
    return p.parse_args()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def blank(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def parse_date(value: str | None, label: str) -> str | None:
    value = blank(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError(f"{label}: 날짜는 YYYY-MM-DD 형식이어야 합니다: {value}") from exc


def read_csv(path: Path) -> list[dict[str, str | None]]:
    if not path.is_file():
        raise SystemExit(f"CSV를 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise SystemExit("필수 열 누락: " + ", ".join(sorted(missing)))
        raw_rows = list(reader)

    rows: list[dict[str, str | None]] = []
    keys: set[str] = set()
    for line_no, raw in enumerate(raw_rows, start=2):
        if not any(blank(raw.get(c)) for c in COLUMNS):
            continue
        row = {c: blank(raw.get(c)) for c in COLUMNS}
        for required in ("event_key", "region_id", "event_name", "t0_date"):
            if row[required] is None:
                raise SystemExit(f"{line_no}행: {required} 값이 필요합니다.")
        if row["event_key"] in keys:
            raise SystemExit(f"중복 event_key: {row['event_key']}")
        keys.add(str(row["event_key"]))
        for field in POINT_COLUMNS.values():
            row[field] = parse_date(row[field], f"{line_no}행 {field}")
        if row["end_date"] and row["t0_date"] and row["end_date"] < row["t0_date"]:
            raise SystemExit(f"{line_no}행: end_date가 t0_date보다 빠릅니다.")
        rows.append(row)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect():
    try:
        import pymysql
    except ImportError:
        raise SystemExit("PyMySQL이 없습니다: py -m pip install PyMySQL")
    missing = [k for k in ("MYSQL_USER", "MYSQL_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise SystemExit(".env 설정 누락: " + ", ".join(missing))
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
    )


def main() -> int:
    opt = args()
    path = opt.csv.resolve()
    rows = read_csv(path)
    if not rows:
        print("[검증 완료] 이벤트 행이 없습니다. events_template.csv에 이벤트를 입력하세요.")
        return 0
    print(f"[CSV] 이벤트 {len(rows):,}건 · 지역 {len({r['region_id'] for r in rows}):,}개")
    if not opt.commit:
        print("[검증 전용] DB는 변경하지 않았습니다.")
        print(f'실제 적재: py load_events_mysql.py "{path}" --commit')
        return 0

    load_dotenv(opt.env.resolve())
    conn = connect()
    try:
        with conn.cursor() as cur:
            region_ids = sorted({str(r["region_id"]) for r in rows})
            placeholders = ",".join(["%s"] * len(region_ids))
            cur.execute(
                f"SELECT region_id FROM dim_region WHERE region_id IN ({placeholders})",
                region_ids,
            )
            known = {x[0] for x in cur.fetchall()}
            unknown = sorted(set(region_ids) - known)
            if unknown:
                raise RuntimeError("dim_region에 없는 코드: " + ", ".join(unknown))

            digest = sha256(path)
            cur.execute(
                """INSERT INTO source_file(file_name,sha256,byte_size,row_count,note)
                   VALUES (%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE file_name=VALUES(file_name),
                     byte_size=VALUES(byte_size),row_count=VALUES(row_count),note=VALUES(note)""",
                (path.name, digest, path.stat().st_size, len(rows), "수동 검증 이벤트 CSV"),
            )
            cur.execute("SELECT source_file_id FROM source_file WHERE sha256=%s", (digest,))
            source_file_id = int(cur.fetchone()[0])

            for row in rows:
                cur.execute(
                    """INSERT INTO event
                         (event_key,region_id,event_name,event_type,evidence_url,
                          evidence_note,source_file_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE region_id=VALUES(region_id),
                         event_name=VALUES(event_name),event_type=VALUES(event_type),
                         evidence_url=VALUES(evidence_url),
                         evidence_note=VALUES(evidence_note),
                         source_file_id=VALUES(source_file_id)""",
                    (
                        row["event_key"], row["region_id"], row["event_name"],
                        row["event_type"], row["evidence_url"],
                        row["evidence_note"], source_file_id,
                    ),
                )
                cur.execute("SELECT event_id FROM event WHERE event_key=%s", (row["event_key"],))
                event_id = int(cur.fetchone()[0])
                for point_type, field in POINT_COLUMNS.items():
                    if row[field] is None:
                        continue
                    cur.execute(
                        """INSERT INTO event_point
                             (event_id,point_type,point_date,definition_note)
                           VALUES (%s,%s,%s,%s)
                           ON DUPLICATE KEY UPDATE point_date=VALUES(point_date),
                             definition_note=VALUES(definition_note)""",
                        (event_id, point_type, row[field], f"events CSV {field}"),
                    )
        conn.commit()
        print(f"[적재 완료] 이벤트 {len(rows):,}건")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

