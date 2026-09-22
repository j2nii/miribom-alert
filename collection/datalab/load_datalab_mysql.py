#!/usr/bin/env python3
"""병합된 데이터랩 월별 CSV를 tour_earlywarning에 안전하게 UPSERT한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

PANEL_COLUMNS = (
    "방문자수", "방문자수_전년동월", "방문자수_증감률", "순방문자수", "숙박자비율",
    "SNS_언급량", "평균숙박일수", "체류시간_분", "체류시간_전국평균_분",
    "숙박방문자비율", "숙박방문자비율_전국평균", "숙박목적지_검색건수",
    "숙박목적지_검색건수_전년동기", "숙박목적지_검색건수_증감률",
    "내비게이션_목적지검색량_전체", "관광소비_내국인_천원", "관광소비_외지인_천원",
    "관광소비_현지인_천원", "전국대비_관광소비_내국인_비율",
    "전국대비_관광소비_외지인_비율", "전국대비_관광소비_현지인_비율",
    "지역화폐_소비금액_천원", "숙박유형별비율_1박", "숙박유형별비율_2박",
    "숙박유형별비율_3박", "숙박유형별비율_4박", "숙박유형별비율_5박",
    "숙박유형별비율_6박", "숙박유형별비율_7박이상", "숙박유형별비율_전체",
)
DB_COLUMNS = (
    "visitors", "visitors_prev_year", "visitors_yoy_pct", "unique_visitors", "overnight_guest_pct",
    "sns_mentions", "avg_nights", "stay_minutes", "stay_minutes_national", "overnight_visit_pct",
    "overnight_visit_pct_national", "lodging_searches", "lodging_searches_prev",
    "lodging_searches_yoy_pct", "navigation_searches", "tourism_spend_domestic_krw_thousand",
    "tourism_spend_outsider_krw_thousand", "tourism_spend_local_krw_thousand",
    "spend_share_domestic_pct", "spend_share_outsider_pct", "spend_share_local_pct",
    "local_currency_spend_krw_thousand", "stay_1night_pct", "stay_2nights_pct", "stay_3nights_pct",
    "stay_4nights_pct", "stay_5nights_pct", "stay_6nights_pct", "stay_7plus_nights_pct",
    "stay_type_total_pct",
)


def parse_args() -> argparse.Namespace:
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(
        description="데이터랩 월별 업데이트 CSV MySQL 적재",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("csv", type=Path, help="merge_datalab_downloads.py가 만든 CSV")
    p.add_argument("--env", type=Path, default=(base / "../yaho_mysql_setup/.env").resolve())
    p.add_argument("--commit", action="store_true", help="검증 후 실제 DB에 반영")
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


def blank_to_none(value: str):
    value = (value or "").strip()
    return None if not value else value


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        expected = {"지역", "기준연월", *PANEL_COLUMNS}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise SystemExit("CSV 필수 열 누락: " + ", ".join(sorted(missing)))
        rows = list(reader)
    keys = [(r["지역"].strip(), r["기준연월"].strip()) for r in rows]
    if len(keys) != len(set(keys)):
        raise SystemExit("CSV에 지역·월 중복 키가 있습니다. 적재를 중단합니다.")
    for region, period in keys:
        try:
            datetime.strptime(period, "%Y%m")
        except ValueError as exc:
            raise SystemExit(f"잘못된 기준연월: {region} {period}") from exc
    regions = {region for region, _ in keys}
    periods = {period for _, period in keys}
    expected_keys = {(region, period) for region in regions for period in periods}
    missing_keys = sorted(expected_keys - set(keys))
    if missing_keys:
        preview = ", ".join(f"{region} {period}" for region, period in missing_keys[:10])
        raise SystemExit(
            f"CSV 지역·월 조합이 {len(missing_keys):,}개 누락됐습니다: {preview}"
        )
    return rows


def connect():
    try:
        import pymysql
    except ImportError:
        raise SystemExit("PyMySQL이 없습니다. 먼저 00_setup.cmd를 실행하세요.")
    missing = [k for k in ("MYSQL_USER", "MYSQL_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f".env 설정 누락: {', '.join(missing)}")
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
        (path.name, digest, path.stat().st_size, row_count, "데이터랩 공식 다운로드 탭 2~5 병합 업데이트"),
    )
    cur.execute("SELECT source_file_id FROM source_file WHERE sha256=%s", (digest,))
    return int(cur.fetchone()[0])


def main() -> int:
    args = parse_args()
    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV를 찾을 수 없습니다: {csv_path}")
    rows = read_rows(csv_path)
    regions = sorted({r["지역"].strip() for r in rows})
    periods = sorted({r["기준연월"].strip() for r in rows})
    print(f"[CSV] {len(rows):,}행 · 지역 {len(regions):,}개 · {periods[0]}~{periods[-1]}")
    if not args.commit:
        print("[검증 전용] DB는 변경하지 않았습니다.")
        print(f"실제 적재: py load_datalab_mysql.py \"{csv_path}\" --commit")
        return 0

    load_dotenv(args.env.resolve())
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM datalab_monthly_panel")
            before = int(cur.fetchone()[0])
            cur.execute(
                """SELECT source_region_name, MAX(canonical_region_id)
                   FROM datalab_monthly_panel GROUP BY source_region_name"""
            )
            canonical = {name: region_id for name, region_id in cur.fetchall()}
            new_names = sorted(set(regions) - set(canonical))
            if new_names:
                preview = ", ".join(new_names[:10])
                raise RuntimeError(
                    f"기존 패널에 없는 지역명 {len(new_names)}개: {preview}. "
                    "행정개편 매핑 검토 후 적재하세요."
                )
            file_id = register_file(cur, csv_path, len(rows))
            placeholders = ",".join(["%s"] * 34)
            insert_cols = (
                "source_region_name", "period_start", "canonical_region_id", *DB_COLUMNS, "source_file_id"
            )
            updates = [
                f"{col}=COALESCE(VALUES({col}),{col})" for col in ("canonical_region_id", *DB_COLUMNS)
            ]
            updates.append("source_file_id=VALUES(source_file_id)")
            sql = (
                f"INSERT INTO datalab_monthly_panel ({','.join(insert_cols)}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {','.join(updates)}"
            )
            values = []
            for row in rows:
                name = row["지역"].strip()
                period = datetime.strptime(row["기준연월"].strip(), "%Y%m").date()
                metrics = [blank_to_none(row[col]) for col in PANEL_COLUMNS]
                values.append((name, period, canonical.get(name), *metrics, file_id))
            for index in range(0, len(values), 500):
                cur.executemany(sql, values[index:index + 500])
            cur.execute("SELECT COUNT(*) FROM datalab_monthly_panel")
            after = int(cur.fetchone()[0])
        conn.commit()
        print(f"[적재 완료] DB 전체 {before:,}행 → {after:,}행 (신규 {after - before:,}행)")
        print("빈 CSV 값은 기존 DB 값을 지우지 않고 보존했습니다.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
