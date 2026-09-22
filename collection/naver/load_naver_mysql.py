#!/usr/bin/env python3
"""네이버 일별 확장 정본을 tour_earlywarning.fact_signal에 UPSERT한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="네이버 확장 CSV MySQL 안전 적재")
    p.add_argument("csv", nargs="?", type=Path, default=base / "naver_all_daily_202301_202608.csv")
    p.add_argument("--env", type=Path, default=(base / "../yaho_mysql_setup/.env").resolve())
    p.add_argument("--commit", action="store_true", help="검증 후 실제 DB에 반영")
    p.add_argument("--expected-start", default="2023-01-01")
    p.add_argument("--expected-end", default="2026-08-31")
    p.add_argument("--expected-regions", type=int, default=228)
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[tuple[str, str, str]]:
    if not path.is_file():
        raise SystemExit(f"CSV를 찾을 수 없습니다: {path}")
    rows: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"region", "date", "value"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit("CSV 필수 열 누락: " + ", ".join(sorted(missing)))
        for line_no, row in enumerate(reader, 2):
            region = (row["region"] or "").strip()
            day = (row["date"] or "").strip()
            value = (row["value"] or "").strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
                number = float(value)
            except ValueError as exc:
                raise SystemExit(f"{line_no}행 날짜/수치 오류: {region}, {day}, {value}") from exc
            if not region or number < 0:
                raise SystemExit(f"{line_no}행 지역 또는 값 오류: {region}, {value}")
            key = (region, day)
            if key in seen:
                raise SystemExit(f"CSV에 중복 키가 있습니다: {region}, {day}")
            seen.add(key)
            rows.append((region, day, value))
    return rows


def validate_shape(rows: list[tuple[str, str, str]], args: argparse.Namespace) -> tuple[list[str], list[str]]:
    regions = sorted({r[0] for r in rows})
    days = sorted({r[1] for r in rows})
    expected_days = (datetime.strptime(args.expected_end, "%Y-%m-%d") -
                     datetime.strptime(args.expected_start, "%Y-%m-%d")).days + 1
    counts: dict[str, int] = {region: 0 for region in regions}
    for region, _, _ in rows:
        counts[region] += 1
    problems = []
    if len(regions) != args.expected_regions:
        problems.append(f"지역 {len(regions)}개 != {args.expected_regions}개")
    if not days or days[0] != args.expected_start or days[-1] != args.expected_end:
        problems.append(f"기간 {days[0] if days else '-'}~{days[-1] if days else '-'}")
    bad = [region for region, count in counts.items() if count != expected_days]
    if bad:
        problems.append(f"일수 불일치 지역 {len(bad)}개")
    if len(rows) != args.expected_regions * expected_days:
        problems.append(f"행수 {len(rows):,}행 != {args.expected_regions * expected_days:,}행")
    if problems:
        raise SystemExit("최종 CSV 구조 검증 실패: " + "; ".join(problems))
    return regions, days


def connect():
    try:
        import pymysql
    except ImportError:
        raise SystemExit("PyMySQL이 없습니다. 먼저 00_setup.cmd를 실행하세요.")
    missing = [key for key in ("MYSQL_USER", "MYSQL_PASSWORD") if not os.environ.get(key)]
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


def register_file(cur, path: Path, row_count: int) -> int:
    digest = sha256(path)
    cur.execute(
        """INSERT INTO source_file(file_name,sha256,byte_size,row_count,note)
           VALUES (%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE file_name=VALUES(file_name),byte_size=VALUES(byte_size),
             row_count=VALUES(row_count),note=VALUES(note)""",
        (path.name, digest, path.stat().st_size, row_count,
         "네이버 데이터랩 검색지수 2023-01~2026-08 겹침 구간 연결 정본"),
    )
    cur.execute("SELECT source_file_id FROM source_file WHERE sha256=%s", (digest,))
    return int(cur.fetchone()[0])


def main() -> int:
    args = parse_args()
    path = args.csv.resolve()
    rows = read_rows(path)
    regions, days = validate_shape(rows, args)
    print(f"[CSV 검증 완료] {len(rows):,}행 · {len(regions)}개 지역 · {days[0]}~{days[-1]}")
    if not args.commit:
        print("[검증 전용] DB는 변경하지 않았습니다.")
        print(f"실제 적재: py load_naver_mysql.py \"{path}\" --commit")
        return 0

    load_dotenv(args.env.resolve())
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT region_id FROM dim_region")
            known = {row[0] for row in cur.fetchall()}
            unknown = sorted(set(regions) - known)
            if unknown:
                raise RuntimeError(f"dim_region에 없는 지역 {len(unknown)}개: {', '.join(unknown[:15])}")
            cur.execute(
                """SELECT COUNT(*),COUNT(DISTINCT region_id),MIN(observed_date),MAX(observed_date)
                   FROM fact_signal
                   WHERE metric='interest_naver' AND source_system='naver_search_trend'"""
            )
            before = cur.fetchone()
            file_id = register_file(cur, path, len(rows))
            sql = """INSERT INTO fact_signal
                     (region_id,source_region_id,observed_date,metric,segment,value,
                      source_system,granularity,source_file_id)
                     VALUES (%s,%s,%s,'interest_naver','',%s,
                             'naver_search_trend','day',%s)
                     ON DUPLICATE KEY UPDATE value=VALUES(value),source_region_id=VALUES(source_region_id),
                       source_file_id=VALUES(source_file_id)"""
            values = [(region, region, day, value, file_id) for region, day, value in rows]
            for index in range(0, len(values), 5000):
                cur.executemany(sql, values[index:index + 5000])
            cur.execute(
                """SELECT COUNT(*),COUNT(DISTINCT region_id),MIN(observed_date),MAX(observed_date)
                   FROM fact_signal
                   WHERE metric='interest_naver' AND source_system='naver_search_trend'"""
            )
            after = cur.fetchone()
        conn.commit()
        print(f"[DB 적재 완료] {before[0]:,}행 → {after[0]:,}행")
        print(f"  지역 {after[1]}개 · {after[2]}~{after[3]}")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
