from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

import pymysql
from dotenv import load_dotenv
from python_calamine import CalamineWorkbook


BASE_DIR = Path(__file__).resolve().parent
MONTH_RE = re.compile(r"^(\d{4})년\s*(\d{1,2})월$")
DATALAB_ZIP_RE = re.compile(
    r"^(?P<code>[A-Za-z0-9_]+)_tab(?P<tab>\d+)_.*_(?P<start>\d{6})_(?P<end>\d{6})\.zip$",
    re.IGNORECASE,
)


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", data, 0, 1, "UTF-8/CP949/EUC-KR 디코딩 실패")


def csv_rows(data: bytes):
    text = decode_csv(data)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return
    reader.fieldnames = [clean(x) for x in reader.fieldnames]
    for row_no, raw in enumerate(reader, start=2):
        row = {clean(k): clean(v) for k, v in raw.items() if k is not None}
        if any(row.values()):
            yield row_no, row


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_key(*parts) -> str:
    text = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_number(value):
    text = clean(value).replace(",", "")
    if not text or text in {"-", "N/A", "nan", "None"}:
        return None
    text = text.replace("명", "").replace("건", "").replace("%", "").strip()
    try:
        return Decimal(text)
    except InvalidOperation:
        match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return Decimal(match.group())
        except InvalidOperation:
            return None


def parse_int(value):
    number = parse_number(value)
    return None if number is None else int(number)


def parse_korean_count(value):
    text = clean(value)
    if not text or re.match(r"^\d{4}\s*:", text) or "절대 방문객수 미기재" in text:
        return None
    match = re.match(r"^([\d,.]+)\s*만", text)
    if match:
        return int(Decimal(match.group(1).replace(",", "")) * 10000)
    match = re.match(r"^([\d,]+)\s*명", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def parse_date(value):
    text = clean(value)
    if not text:
        return None
    text = re.sub(r"\s+", "", text)
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y.%m", "%Y%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    match = re.search(r"(20\d{2})[^0-9]?(\d{1,2})[^0-9]?(\d{1,2})?", text)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day or 1))
        except ValueError:
            return None
    return None


def month_date(yyyymm: str):
    return datetime.strptime(yyyymm, "%Y%m").date()


def month_from_row(row: dict[str, str]):
    for key in ("기준연월", "기준년월", "기준 연월", "연월"):
        value = row.get(key)
        if value and re.fullmatch(r"\d{6}", re.sub(r"\D", "", value)):
            return month_date(re.sub(r"\D", "", value))
    return None


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default)


def db_connect():
    password = os.environ.get("MYSQL_PASSWORD", "")
    if not password or password.startswith("CHANGE_"):
        raise RuntimeError(".env의 MYSQL_PASSWORD를 실제 yaho_loader 비밀번호로 바꾸세요.")
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "yaho_loader"),
        password=password,
        database=os.environ.get("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def execute_schema(conn):
    sql = (BASE_DIR / "01_create_received_data_schema.sql").read_text(encoding="utf-8")
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    with conn.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    conn.commit()


def register_source(conn, path: Path, kind: str) -> int:
    digest = sha256_file(path)
    size = path.stat().st_size
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ingest_source_file
                (source_kind, source_path, file_name, sha256, byte_size, load_status)
            VALUES (%s, %s, %s, %s, %s, 'loading')
            ON DUPLICATE KEY UPDATE
                source_kind=VALUES(source_kind), source_path=VALUES(source_path),
                file_name=VALUES(file_name), byte_size=VALUES(byte_size), load_status='loading'
            """,
            (kind, str(path.resolve()), path.name, digest, size),
        )
        cursor.execute("SELECT source_id FROM ingest_source_file WHERE sha256=%s", (digest,))
        return int(cursor.fetchone()["source_id"])


def finish_source(conn, source_id: int, status: str):
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE ingest_source_file SET load_status=%s, last_loaded_at=CURRENT_TIMESTAMP WHERE source_id=%s",
            (status, source_id),
        )


def upsert_member(conn, source_id: int, member_name: str, row_count, target, status, error=None):
    key = hash_key(source_id, member_name)
    extension = PurePosixPath(member_name).suffix.lower().lstrip(".") or None
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ingest_archive_member
                (member_key, source_id, member_name, member_extension, row_count,
                 structured_target, load_status, error_message)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                row_count=VALUES(row_count), structured_target=VALUES(structured_target),
                load_status=VALUES(load_status), error_message=VALUES(error_message),
                loaded_at=CURRENT_TIMESTAMP
            """,
            (key, source_id, member_name, extension, row_count, target, status, error),
        )


def executemany_batches(conn, sql: str, rows, batch_size=2000):
    total = 0
    batch = []
    with conn.cursor() as cursor:
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                cursor.executemany(sql, batch)
                total += len(batch)
                batch.clear()
        if batch:
            cursor.executemany(sql, batch)
            total += len(batch)
    return total


def infer_region_name(zip_path: Path, region_code: str):
    parent = zip_path.parent.name
    prefixes = (region_code + "_", region_code + "-")
    for prefix in prefixes:
        if parent.startswith(prefix):
            return parent[len(prefix):].strip() or None
    return None


def datalab_group(member_name: str):
    stem = PurePosixPath(member_name).stem.strip()
    stem = re.sub(r"^\d{12,14}_", "", stem).strip()
    return stem


def process_datalab_zip(path: Path, conn=None, scan_only=False):
    match = DATALAB_ZIP_RE.match(path.name)
    if not match:
        return {"zip": 0, "members": 0, "rows": 0}
    code = match.group("code")
    tab = int(match.group("tab"))
    start_month = month_date(match.group("start"))
    end_month = month_date(match.group("end"))
    region_name = infer_region_name(path, code)
    source_id = None if scan_only else register_source(conn, path, "datalab_download_zip")
    members = rows_total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".csv"):
                    continue
                members += 1
                member_rows = []
                group = datalab_group(info.filename)
                for row_no, row in csv_rows(archive.read(info.filename)):
                    observed = month_from_row(row)
                    row_region = region_name
                    if not row_region:
                        candidate = clean(row.get("지역명"))
                        if candidate and "전국" not in candidate:
                            row_region = candidate
                    row_json = canonical_json(row)
                    period_key = observed.isoformat() if observed else f"{start_month}:{end_month}"
                    row_key = hash_key(code, tab, group, period_key, row_json)
                    member_rows.append(
                        (
                            row_key, source_id, info.filename, tab, code, row_region,
                            start_month, end_month, observed, group, row_no, row_json,
                        )
                    )
                row_count = len(member_rows)
                rows_total += row_count
                if not scan_only:
                    executemany_batches(
                        conn,
                        """
                        INSERT INTO datalab_detail_row
                            (row_key, source_id, member_name, tab_no, source_region_code,
                             source_region_name, query_start_month, query_end_month,
                             observed_month, data_group, source_row_no, row_json)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE
                            source_id=VALUES(source_id), member_name=VALUES(member_name),
                            source_region_name=COALESCE(VALUES(source_region_name), source_region_name),
                            source_row_no=VALUES(source_row_no), row_json=VALUES(row_json),
                            loaded_at=CURRENT_TIMESTAMP
                        """,
                        member_rows,
                    )
                    upsert_member(conn, source_id, info.filename, row_count, "datalab_detail_row", "loaded")
        if not scan_only:
            finish_source(conn, source_id, "loaded")
            conn.commit()
        return {"zip": 1, "members": members, "rows": rows_total}
    except Exception as exc:
        if not scan_only:
            conn.rollback()
            finish_source(conn, source_id, "failed")
            conn.commit()
        raise RuntimeError(f"DataLab ZIP 처리 실패: {path} - {exc}") from exc


def upsert_reference_document(conn, source_id, member_name, document_type, size=None, region_hint=None):
    title = PurePosixPath(member_name).stem
    key = hash_key(source_id, member_name)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reference_document_catalog
                (document_key, source_id, member_name, document_type, title, region_hint, byte_size)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                document_type=VALUES(document_type), title=VALUES(title),
                region_hint=VALUES(region_hint), byte_size=VALUES(byte_size),
                loaded_at=CURRENT_TIMESTAMP
            """,
            (key, source_id, member_name, document_type, title, region_hint, size),
        )


def process_portal_zip(path: Path, conn=None, scan_only=False):
    source_id = None if scan_only else register_source(conn, path, "portal_additional_zip")
    counts = {"catalog": 0, "residence": 0, "jeju_daily": 0, "documents": 0, "members": 0}
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                counts["members"] += 1
                name = PurePosixPath(info.filename).name
                lower = name.lower()
                target = "reference_document_catalog"
                row_count = None
                if lower.endswith(".pdf"):
                    counts["documents"] += 1
                    if not scan_only:
                        upsert_reference_document(conn, source_id, info.filename, "pdf", info.file_size)
                elif lower.endswith(".csv"):
                    rows = list(csv_rows(archive.read(info.filename)))
                    row_count = len(rows)
                    if "제주특별자치도_내국인관광지입장객수추이" in name:
                        target = "jeju_attraction_visitors_daily"
                        counts["jeju_daily"] += row_count
                        if not scan_only:
                            values = []
                            for _, row in rows:
                                observed = parse_date(row.get("날짜"))
                                attraction = clean(row.get("관광지명"))
                                if observed and attraction:
                                    values.append((observed, attraction, parse_int(row.get("관광객수")), source_id))
                            executemany_batches(
                                conn,
                                """INSERT INTO jeju_attraction_visitors_daily
                                (observed_date, attraction_name, visitor_count, source_id)
                                VALUES (%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE visitor_count=VALUES(visitor_count),
                                source_id=VALUES(source_id), loaded_at=CURRENT_TIMESTAMP""",
                                values,
                            )
                    elif "거주지별내국인관광객통계" in name:
                        target = "domestic_tourist_residence_annual"
                        counts["residence"] += row_count
                        if not scan_only:
                            values = []
                            for _, row in rows:
                                year = parse_int(row.get("기준 연도"))
                                residence = clean(row.get("거주지"))
                                if year and residence:
                                    values.append(
                                        (year, residence, parse_int(row.get("응답자 수(명)")),
                                         parse_number(row.get("구성비(%)")), source_id)
                                    )
                            executemany_batches(
                                conn,
                                """INSERT INTO domestic_tourist_residence_annual
                                (reference_year, residence_name, respondent_count, share_pct, source_id)
                                VALUES (%s,%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE respondent_count=VALUES(respondent_count),
                                share_pct=VALUES(share_pct), source_id=VALUES(source_id),
                                loaded_at=CURRENT_TIMESTAMP""",
                                values,
                            )
                    elif "추가수집_카탈로그" in name:
                        target = "external_collection_catalog"
                        counts["catalog"] += row_count
                        if not scan_only:
                            values = []
                            for _, row in rows:
                                title = clean(row.get("제목"))
                                if not title:
                                    continue
                                raw_date = clean(row.get("등록일"))
                                key = hash_key(row.get("출처"), row.get("구분"), title, row.get("저장파일명(다운로드폴더)"))
                                values.append(
                                    (key, clean(row.get("출처")) or None, clean(row.get("구분")) or None,
                                     title, parse_date(raw_date), raw_date or None,
                                     clean(row.get("저장파일명(다운로드폴더)")) or None,
                                     clean(row.get("비고")) or None, source_id)
                                )
                            executemany_batches(
                                conn,
                                """INSERT INTO external_collection_catalog
                                (catalog_key, source_name, category_name, title, registered_date,
                                 registered_date_raw, stored_file_name, note, source_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE registered_date=VALUES(registered_date),
                                registered_date_raw=VALUES(registered_date_raw), stored_file_name=VALUES(stored_file_name),
                                note=VALUES(note), source_id=VALUES(source_id), loaded_at=CURRENT_TIMESTAMP""",
                                values,
                            )
                    else:
                        target = "catalog_only_unrecognized_csv"
                else:
                    target = "reference_document_catalog"
                    counts["documents"] += 1
                    if not scan_only:
                        upsert_reference_document(conn, source_id, info.filename, PurePosixPath(name).suffix.lstrip(".") or "file", info.file_size)
                if not scan_only:
                    upsert_member(conn, source_id, info.filename, row_count, target, "loaded")
        if not scan_only:
            finish_source(conn, source_id, "loaded")
            conn.commit()
        return counts
    except Exception as exc:
        if not scan_only:
            conn.rollback()
            finish_source(conn, source_id, "failed")
            conn.commit()
        raise RuntimeError(f"포털 ZIP 처리 실패: {path} - {exc}") from exc


def parse_interest_rank_rows(rows, source_id):
    values = []
    for _, row in rows:
        region = clean(row.get("지역"))
        attraction = clean(row.get("관광지명"))
        rank = parse_int(row.get("순위"))
        if region and attraction and rank:
            values.append((region, rank, attraction, parse_int(row.get("총등록건수")), source_id))
    return values


def parse_case_rows(rows, source_id):
    values = []
    for _, row in rows:
        region = clean(row.get("지역"))
        if not region:
            continue
        announced = parse_date(row.get("발표일"))
        survey = clean(row.get("조사기간")) or None
        key = hash_key(region, announced, survey, row.get("방문객수"))
        visitor_text = clean(row.get("방문객수")) or None
        values.append(
            (key, region, announced, survey, parse_korean_count(visitor_text), visitor_text,
             clean(row.get("전년대비_증감")) or None, clean(row.get("출처")) or None,
             clean(row.get("비고")) or None, source_id)
        )
    return values


def parse_major_attraction_xls(data: bytes, source_id, member_name: str):
    workbook = CalamineWorkbook.from_filelike(io.BytesIO(data))
    rows = workbook.get_sheet_by_index(0).to_python()
    if len(rows) < 3:
        return []
    month_columns = []
    for index, value in enumerate(rows[1]):
        match = MONTH_RE.match(clean(value))
        if match:
            month_columns.append((index, date(int(match.group(1)), int(match.group(2)), 1)))
    values = []
    for row in rows[2:]:
        if len(row) < 4:
            continue
        province, district, attraction, visitor_type = (clean(row[i]) for i in range(4))
        if not (province and district and attraction and visitor_type):
            continue
        for column, observed_month in month_columns:
            if column >= len(row) or clean(row[column]) == "":
                continue
            count = parse_int(row[column])
            if count is None:
                continue
            key = hash_key(province, district, attraction, visitor_type, observed_month)
            values.append(
                (key, province, district, attraction, visitor_type, observed_month,
                 count, source_id, member_name)
            )
    return values


def region_hint_from_xls(name: str):
    match = re.search(r"_([^_/]+)\.xls$", name, re.IGNORECASE)
    return match.group(1) if match else None


def process_knowledge_zip(path: Path, conn=None, scan_only=False):
    source_id = None if scan_only else register_source(conn, path, "tourism_knowledge_zip")
    counts = {"cases": 0, "ranks": 0, "attraction_months": 0, "documents": 0, "members": 0}
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                counts["members"] += 1
                name = PurePosixPath(info.filename).name
                lower = name.lower()
                data = archive.read(info.filename)
                target = "reference_document_catalog"
                row_count = None
                if lower.endswith(".xls"):
                    values = parse_major_attraction_xls(data, source_id, info.filename)
                    row_count = len(values)
                    counts["attraction_months"] += row_count
                    counts["documents"] += 1
                    target = "major_attraction_visitors_monthly"
                    if not scan_only:
                        upsert_reference_document(
                            conn, source_id, info.filename, "xls", info.file_size,
                            region_hint_from_xls(info.filename),
                        )
                        executemany_batches(
                            conn,
                            """INSERT INTO major_attraction_visitors_monthly
                            (attraction_month_key, province_name, district_name, attraction_name,
                             visitor_type, observed_month, visitor_count, source_id, source_member_name)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON DUPLICATE KEY UPDATE visitor_count=VALUES(visitor_count),
                            source_id=VALUES(source_id), source_member_name=VALUES(source_member_name),
                            loaded_at=CURRENT_TIMESTAMP""",
                            values,
                        )
                elif lower.endswith(".csv"):
                    rows = list(csv_rows(data))
                    if "실측방문자수" in name:
                        values = parse_case_rows(rows, source_id)
                        row_count = len(values)
                        counts["cases"] += row_count
                        target = "observed_visitors_case"
                        if not scan_only:
                            executemany_batches(
                                conn,
                                """INSERT INTO observed_visitors_case
                                (case_key, region_name, announced_date, survey_period, visitor_count,
                                 visitor_count_text, yoy_change_text, source_url, note, source_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE visitor_count=VALUES(visitor_count),
                                visitor_count_text=VALUES(visitor_count_text),
                                yoy_change_text=VALUES(yoy_change_text), source_url=VALUES(source_url),
                                note=VALUES(note), source_id=VALUES(source_id), loaded_at=CURRENT_TIMESTAMP""",
                                values,
                            )
                    elif "관심관광지" in re.sub(r"[ _]", "", name):
                        values = parse_interest_rank_rows(rows, source_id)
                        row_count = len(values)
                        counts["ranks"] += row_count
                        target = "domestic_interest_attraction_rank"
                        if not scan_only:
                            executemany_batches(
                                conn,
                                """INSERT INTO domestic_interest_attraction_rank
                                (region_name, ranking, attraction_name, total_registration_count, source_id)
                                VALUES (%s,%s,%s,%s,%s)
                                ON DUPLICATE KEY UPDATE total_registration_count=VALUES(total_registration_count),
                                source_id=VALUES(source_id), loaded_at=CURRENT_TIMESTAMP""",
                                values,
                            )
                    else:
                        row_count = len(rows)
                        target = "catalog_only_unrecognized_csv"
                else:
                    counts["documents"] += 1
                    if not scan_only:
                        upsert_reference_document(conn, source_id, info.filename, PurePosixPath(name).suffix.lstrip(".") or "file", info.file_size)
                if not scan_only:
                    upsert_member(conn, source_id, info.filename, row_count, target, "loaded")
        if not scan_only:
            finish_source(conn, source_id, "loaded")
            conn.commit()
        return counts
    except Exception as exc:
        if not scan_only:
            conn.rollback()
            finish_source(conn, source_id, "failed")
            conn.commit()
        raise RuntimeError(f"관광지식정보시스템 ZIP 처리 실패: {path} - {exc}") from exc


def locate_path(explicit, env_name, fallbacks):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get(env_name):
        candidates.append(Path(os.environ[env_name]))
    candidates.extend(Path(item) for item in fallbacks)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def print_validation(conn):
    checks = [
        ("DataLab 세부 원본 행", "SELECT COUNT(*) n FROM datalab_detail_row"),
        ("DataLab 지역", "SELECT COUNT(DISTINCT source_region_code) n FROM datalab_detail_row"),
        ("DataLab 파일 유형", "SELECT COUNT(DISTINCT data_group) n FROM datalab_detail_row"),
        ("제주 관광지 일별", "SELECT COUNT(*) n FROM jeju_attraction_visitors_daily"),
        ("거주지 연간 통계", "SELECT COUNT(*) n FROM domestic_tourist_residence_annual"),
        ("외부 수집 카탈로그", "SELECT COUNT(*) n FROM external_collection_catalog"),
        ("실측 방문자 사례", "SELECT COUNT(*) n FROM observed_visitors_case"),
        ("관심 관광지 순위", "SELECT COUNT(*) n FROM domestic_interest_attraction_rank"),
        ("주요 관광지 월별 입장객", "SELECT COUNT(*) n FROM major_attraction_visitors_monthly"),
        ("참고 문서", "SELECT COUNT(*) n FROM reference_document_catalog"),
        ("적재 실패 파일", "SELECT COUNT(*) n FROM ingest_archive_member WHERE load_status='failed'"),
    ]
    with conn.cursor() as cursor:
        print("\n[DB 검증]")
        for label, sql in checks:
            cursor.execute(sql)
            print(f"  {label:<24} {cursor.fetchone()['n']:,}")
        cursor.execute(
            """SELECT MIN(observed_month) min_date, MAX(observed_month) max_date,
                      COUNT(DISTINCT attraction_name) attractions
               FROM major_attraction_visitors_monthly"""
        )
        row = cursor.fetchone()
        print(f"  주요 관광지 범위          {row['min_date']} ~ {row['max_date']} · {row['attractions']:,}개 관광지")


def main():
    load_dotenv(BASE_DIR / ".env")
    parser = argparse.ArgumentParser(description="받아 둔 관광 데이터 전체 추가 적재")
    parser.add_argument("--datalab-dir")
    parser.add_argument("--portal-zip")
    parser.add_argument("--knowledge-zip")
    parser.add_argument("--create-schema", action="store_true")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    if not any((args.create_schema, args.scan_only, args.commit, args.validate)):
        parser.error("--create-schema, --scan-only, --commit, --validate 중 하나를 선택하세요.")

    data_root = Path(os.environ.get("DATA_ROOT", r"C:\Users\han\yaho"))
    datalab_dir = locate_path(
        args.datalab_dir, "DATALAB_DOWNLOADS",
        [data_root / "datalab_collector" / "datalab_downloads", Path("datalab_downloads")],
    )
    portal_zip = locate_path(
        args.portal_zip, "PORTAL_ZIP",
        [data_root / "포털추가수집.zip", Path("포털추가수집.zip")],
    )
    knowledge_zip = locate_path(
        args.knowledge_zip, "KNOWLEDGE_ZIP",
        [data_root / "관광지식정보시스템_데이터.zip", Path("관광지식정보시스템_데이터.zip")],
    )

    if args.scan_only or args.commit:
        missing = []
        if not datalab_dir or not datalab_dir.is_dir():
            missing.append(f"DataLab 폴더: {datalab_dir}")
        if not portal_zip or not portal_zip.is_file():
            missing.append(f"포털 ZIP: {portal_zip}")
        if not knowledge_zip or not knowledge_zip.is_file():
            missing.append(f"관광지식정보 ZIP: {knowledge_zip}")
        if missing:
            raise FileNotFoundError("\n".join(["다음 경로를 찾지 못했습니다."] + missing + [".env 경로를 수정하세요."]))

    conn = None
    if args.create_schema or args.commit or args.validate:
        conn = db_connect()
    try:
        if args.create_schema:
            execute_schema(conn)
            print("[OK] 추가 적재 테이블과 조회 뷰를 만들었습니다.")

        if args.scan_only or args.commit:
            if args.commit:
                execute_schema(conn)
            print(f"[DataLab] {datalab_dir}")
            totals = {"zip": 0, "members": 0, "rows": 0}
            zip_paths = sorted(datalab_dir.rglob("*_tab*.zip"))
            for index, path in enumerate(zip_paths, start=1):
                result = process_datalab_zip(path, conn, args.scan_only)
                for key in totals:
                    totals[key] += result[key]
                if index % 100 == 0 or index == len(zip_paths):
                    print(f"  {index}/{len(zip_paths)} ZIP · 누적 {totals['rows']:,}행")
            print(f"  결과: {totals['zip']:,} ZIP · {totals['members']:,} CSV · {totals['rows']:,}행")

            print(f"[포털 추가수집] {portal_zip}")
            portal = process_portal_zip(portal_zip, conn, args.scan_only)
            print("  " + " · ".join(f"{k}={v:,}" for k, v in portal.items()))

            print(f"[관광지식정보시스템] {knowledge_zip}")
            knowledge = process_knowledge_zip(knowledge_zip, conn, args.scan_only)
            print("  " + " · ".join(f"{k}={v:,}" for k, v in knowledge.items()))
            print("[OK] 스캔 완료" if args.scan_only else "[OK] 전체 적재 완료")

        if args.validate:
            execute_schema(conn)
            print_validation(conn)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[중단] 사용자가 작업을 중단했습니다.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n[오류] {exc}", file=sys.stderr)
        raise SystemExit(2)
