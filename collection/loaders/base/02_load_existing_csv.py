# -*- coding: utf-8 -*-
"""야호레이더 기존 CSV/ZIP을 MySQL에 멱등 적재한다.

사용 예:
  pip install -r requirements.txt
  python 02_load_existing_csv.py --data-dir C:\\Users\\han\\yaho

01_schema.sql을 먼저 실행해야 한다. 같은 파일을 다시 실행해도 UPSERT된다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import pymysql
except ImportError:
    sys.exit("PyMySQL이 없습니다. 먼저: pip install -r requirements.txt")


REQUIRED = (
    "region_master.csv",
    "region_scope.csv",
    "signals_visitors_v2.csv",
    "naver_all_daily_v2.csv",
    "yt_videos_top.csv",
    "관광_월별패널_259개지역.csv",
)
OPTIONAL_ZIPS = ("포털추가수집.zip", "관광지식정보시스템_데이터.zip")
SEGMENT = {"1": "local", "2": "external", "3": "foreign"}
YT_REGION = {
    "거제": "48310", "영월": "51750", "인제": "51810",
    "여수": "12130", "속초": "51210", "울릉": "47940",
}

# 행정개편 전 코드를 분석용 정본 코드로 연결한다.
OLD_TO_CANONICAL = {
    "29110": "12210", "29140": "12240", "29155": "12270",
    "29170": "12300", "29200": "12330",
    "46110": "12110", "46130": "12130", "46150": "12150",
    "46170": "12170", "46230": "12190",
    "46710": "12710", "46720": "12720", "46730": "12730",
    "46770": "12740", "46780": "12750", "46790": "12760",
    "46800": "12770", "46810": "12780", "46820": "12790",
    "46830": "12800", "46840": "12810", "46860": "12820",
    "46870": "12830", "46880": "12840", "46890": "12850",
    "46900": "12860", "46910": "12870",
    "28110": "IC_MID", "28140": "IC_MID",
    "28125": "IC_MID", "28155": "IC_MID",
    "28260": "INCHEON_WEST", "28275": "INCHEON_WEST",
    "28290": "INCHEON_WEST",
    "INCHEON_MID": "IC_MID", "HWASEONG": "41590",
}

SPECIAL_NAMES = {
    "41590": "화성시",
    "IC_MID": "인천 중구권(합산)",
    "INCHEON_WEST": "인천 서구권(합산)",
}
SPECIAL_SIDO = {"IC_MID": "28", "INCHEON_WEST": "28"}

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


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'") )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def register_file(cur, path: Path, row_count: int | None, note: str = "") -> int:
    digest = sha256(path)
    cur.execute(
        """INSERT INTO source_file(file_name, sha256, byte_size, row_count, note)
           VALUES (%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE file_name=VALUES(file_name),
             byte_size=VALUES(byte_size), row_count=VALUES(row_count), note=VALUES(note)""",
        (path.name, digest, path.stat().st_size, row_count, note or None),
    )
    cur.execute("SELECT source_file_id FROM source_file WHERE sha256=%s", (digest,))
    return int(cur.fetchone()[0])


def chunks(iterator, size=5000):
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def blank_to_none(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value == "" else value


def integer(value):
    value = blank_to_none(value)
    return None if value is None else int(float(value))


def read_dicts(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def load_reference_tables(conn, data_dir: Path):
    master_path = data_dir / "region_master.csv"
    scope_path = data_dir / "region_scope.csv"
    visitors_path = data_dir / "signals_visitors_v2.csv"

    master_rows = list(read_dicts(master_path))
    scope_rows = list(read_dicts(scope_path))
    canonical_ids = {r["region"] for r in read_dicts(visitors_path)}
    master_by_id = {r["region"]: r for r in master_rows}

    with conn.cursor() as cur:
        master_file = register_file(cur, master_path, len(master_rows), "제공된 원천 지역 마스터")
        scope_file = register_file(cur, scope_path, len(scope_rows), "제공된 원천 분석 범위")

        cur.executemany(
            """INSERT INTO stg_region_master
               (source_region_id,source_region_name,sido_code,reform_note,source_file_id)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE source_region_name=VALUES(source_region_name),
                 sido_code=VALUES(sido_code),reform_note=VALUES(reform_note),
                 source_file_id=VALUES(source_file_id)""",
            [(r["region"], r["name"], blank_to_none(r["시도코드"]),
              blank_to_none(r["개편"]), master_file) for r in master_rows],
        )
        cur.executemany(
            """INSERT INTO stg_region_scope
               (source_region_id,keep_flag,region_level,exclusion_reason,source_file_id)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE keep_flag=VALUES(keep_flag),
                 region_level=VALUES(region_level),exclusion_reason=VALUES(exclusion_reason),
                 source_file_id=VALUES(source_file_id)""",
            [(r["region"], int(r["keep"]), blank_to_none(r["level"]),
              blank_to_none(r["reason"]), scope_file) for r in scope_rows],
        )

        dim = []
        for region_id in sorted(canonical_ids):
            src = master_by_id.get(region_id, {})
            name = SPECIAL_NAMES.get(region_id) or src.get("name") or region_id
            sido = SPECIAL_SIDO.get(region_id) or blank_to_none(src.get("시도코드"))
            if sido is None and region_id.isdigit():
                sido = region_id[:2]
            synthetic = int(not region_id.isdigit())
            dim.append((region_id, name, sido, "aggregate" if synthetic else "basic", synthetic))
        cur.executemany(
            """INSERT INTO dim_region(region_id,region_name,sido_code,region_type,is_synthetic)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE region_name=VALUES(region_name),sido_code=VALUES(sido_code),
                 region_type=VALUES(region_type),is_synthetic=VALUES(is_synthetic)""",
            dim,
        )

        aliases = []
        for old, canonical in OLD_TO_CANONICAL.items():
            if canonical in canonical_ids:
                aliases.append(("administrative_code", old, canonical, "행정개편/합산 규칙"))
        aliases.extend(("canonical", rid, rid, "정본 코드") for rid in canonical_ids)
        cur.executemany(
            """INSERT INTO region_alias
               (source_system,source_region_key,canonical_region_id,mapping_reason)
               VALUES (%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE canonical_region_id=VALUES(canonical_region_id),
                 mapping_reason=VALUES(mapping_reason)""",
            aliases,
        )
    conn.commit()
    print(f"[지역] 분석 정본 {len(canonical_ids):,}개 · 원천 master {len(master_rows):,}개")
    return canonical_ids


def load_visitors(conn, path: Path, canonical_ids: set[str]):
    count = csv_rows(path)
    with conn.cursor() as cur:
        file_id = register_file(cur, path, count, "data.go.kr 일별 방문자수 v2")
        sql = """INSERT INTO fact_signal
                 (region_id,source_region_id,observed_date,metric,segment,value,
                  source_system,granularity,source_file_id)
                 VALUES (%s,%s,%s,'realization_visitors',%s,%s,
                         'data.go.kr/15101972','day',%s)
                 ON DUPLICATE KEY UPDATE value=VALUES(value),source_file_id=VALUES(source_file_id)"""
        def rows():
            for r in read_dicts(path):
                region = r["region"]
                if region not in canonical_ids:
                    raise ValueError(f"방문자수에 알 수 없는 정본 코드: {region}")
                segment = SEGMENT.get(r["tou_div"])
                if not segment:
                    raise ValueError(f"알 수 없는 tou_div: {r['tou_div']}")
                yield (region, region, r["date"], segment, r["value"], file_id)
        for batch in chunks(rows()):
            cur.executemany(sql, batch)
    conn.commit()
    print(f"[방문자수] {count:,}행")


def load_naver(conn, path: Path, canonical_ids: set[str]):
    count = csv_rows(path)
    kept = skipped = 0
    with conn.cursor() as cur:
        file_id = register_file(cur, path, count, "네이버 데이터랩 일별 검색지수 v2")
        sql = """INSERT INTO fact_signal
                 (region_id,source_region_id,observed_date,metric,segment,value,
                  source_system,granularity,source_file_id)
                 VALUES (%s,%s,%s,'interest_naver','',%s,
                         'naver_search_trend','day',%s)
                 ON DUPLICATE KEY UPDATE value=VALUES(value),source_file_id=VALUES(source_file_id)"""
        batch = []
        for r in read_dicts(path):
            source_region = r["region"]
            region = "INCHEON_WEST" if source_region == "28260" else source_region
            if region not in canonical_ids:
                skipped += 1
                continue
            batch.append((region, source_region, r["date"], r["value"], file_id))
            kept += 1
            if len(batch) >= 5000:
                cur.executemany(sql, batch); batch = []
        if batch:
            cur.executemany(sql, batch)
    conn.commit()
    print(f"[네이버] 원천 {count:,}행 · 적재 {kept:,}행 · 범위 밖 {skipped:,}행")


def parse_utc_to_kst(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def load_youtube(conn, path: Path, canonical_ids: set[str]):
    count = csv_rows(path)
    seen = set()
    rows = []
    with conn.cursor() as cur:
        file_id = register_file(cur, path, count, "YouTube 월별 조회수 상위 영상")
        for r in read_dicts(path):
            if r["videoId"] in seen:
                continue
            seen.add(r["videoId"])
            region = YT_REGION.get(r["region"])
            if not region or region not in canonical_ids:
                raise ValueError(f"YouTube 지역 매핑 실패: {r['region']}")
            rows.append((
                r["videoId"], region, r["region"], blank_to_none(r["keyword"]),
                parse_utc_to_kst(r["publishedAt"]), r["title"], blank_to_none(r["channel"]),
                integer(r["view_rank"]), blank_to_none(r["window"]), integer(r["viewCount"]),
                integer(r["likeCount"]), integer(r["commentCount"]), file_id,
            ))
        sql = """INSERT INTO youtube_video
                 (video_id,region_id,source_region_name,keyword_text,published_at,title,
                  channel_name,view_rank,window_month,view_count,like_count,comment_count,source_file_id)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                 ON DUPLICATE KEY UPDATE region_id=VALUES(region_id),keyword_text=VALUES(keyword_text),
                   published_at=VALUES(published_at),title=VALUES(title),channel_name=VALUES(channel_name),
                   view_rank=VALUES(view_rank),window_month=VALUES(window_month),
                   view_count=VALUES(view_count),like_count=VALUES(like_count),
                   comment_count=VALUES(comment_count),source_file_id=VALUES(source_file_id)"""
        for batch in chunks(rows):
            cur.executemany(sql, batch)
    conn.commit()
    print(f"[YouTube] 원천 {count:,}행 · 고유 영상 {len(rows):,}건")


def build_panel_mapper(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT region_id,region_name,sido_code FROM dim_region")
        rows = cur.fetchall()
    by_name = defaultdict(list)
    by_sido_name = {}
    for region_id, name, sido in rows:
        by_name[name].append(region_id)
        if sido:
            by_sido_name[(sido, name)] = region_id

    prefixes = {
        "서울특별시 ": "11", "부산광역시 ": "26", "대구광역시 ": "27",
        "대전광역시 ": "30", "울산광역시 ": "31",
        "전남광주통합특별시 ": "12", "강원특별자치도 ": "51",
    }

    def map_name(source_name: str):
        name = " ".join(source_name.split())
        # 인천 2026 개편 전후 명칭은 기간별 합산 규칙 검토 전에는 자동 연결하지 않는다.
        if name.startswith("인천광역시 "):
            return None
        for prefix, sido in prefixes.items():
            if name.startswith(prefix):
                return by_sido_name.get((sido, name[len(prefix):]))
        # '고양시 덕양구' 같은 일반구와 신규 화성 구는 분석 정본에 억지 합산하지 않는다.
        if "시 " in name:
            return None
        matches = by_name.get(name, [])
        return matches[0] if len(matches) == 1 else None
    return map_name


def load_datalab_panel(conn, path: Path):
    count = csv_rows(path)
    mapper = build_panel_mapper(conn)
    mapped_regions, unmapped_regions = set(), set()
    with conn.cursor() as cur:
        file_id = register_file(cur, path, count, "관광 데이터랩 259개 지역 월별 통합 패널")
        placeholders = ",".join(["%s"] * 34)
        sql = f"""INSERT INTO datalab_monthly_panel
          (source_region_name,period_start,canonical_region_id,
           visitors,visitors_prev_year,visitors_yoy_pct,unique_visitors,overnight_guest_pct,
           sns_mentions,avg_nights,stay_minutes,stay_minutes_national,overnight_visit_pct,
           overnight_visit_pct_national,lodging_searches,lodging_searches_prev,
           lodging_searches_yoy_pct,navigation_searches,tourism_spend_domestic_krw_thousand,
           tourism_spend_outsider_krw_thousand,tourism_spend_local_krw_thousand,
           spend_share_domestic_pct,spend_share_outsider_pct,spend_share_local_pct,
           local_currency_spend_krw_thousand,stay_1night_pct,stay_2nights_pct,stay_3nights_pct,
           stay_4nights_pct,stay_5nights_pct,stay_6nights_pct,stay_7plus_nights_pct,
           stay_type_total_pct,source_file_id)
          VALUES ({placeholders})
          ON DUPLICATE KEY UPDATE canonical_region_id=VALUES(canonical_region_id),
           visitors=VALUES(visitors),visitors_prev_year=VALUES(visitors_prev_year),
           visitors_yoy_pct=VALUES(visitors_yoy_pct),unique_visitors=VALUES(unique_visitors),
           overnight_guest_pct=VALUES(overnight_guest_pct),sns_mentions=VALUES(sns_mentions),
           avg_nights=VALUES(avg_nights),stay_minutes=VALUES(stay_minutes),
           stay_minutes_national=VALUES(stay_minutes_national),
           overnight_visit_pct=VALUES(overnight_visit_pct),
           overnight_visit_pct_national=VALUES(overnight_visit_pct_national),
           lodging_searches=VALUES(lodging_searches),lodging_searches_prev=VALUES(lodging_searches_prev),
           lodging_searches_yoy_pct=VALUES(lodging_searches_yoy_pct),
           navigation_searches=VALUES(navigation_searches),
           tourism_spend_domestic_krw_thousand=VALUES(tourism_spend_domestic_krw_thousand),
           tourism_spend_outsider_krw_thousand=VALUES(tourism_spend_outsider_krw_thousand),
           tourism_spend_local_krw_thousand=VALUES(tourism_spend_local_krw_thousand),
           spend_share_domestic_pct=VALUES(spend_share_domestic_pct),
           spend_share_outsider_pct=VALUES(spend_share_outsider_pct),
           spend_share_local_pct=VALUES(spend_share_local_pct),
           local_currency_spend_krw_thousand=VALUES(local_currency_spend_krw_thousand),
           stay_1night_pct=VALUES(stay_1night_pct),stay_2nights_pct=VALUES(stay_2nights_pct),
           stay_3nights_pct=VALUES(stay_3nights_pct),stay_4nights_pct=VALUES(stay_4nights_pct),
           stay_5nights_pct=VALUES(stay_5nights_pct),stay_6nights_pct=VALUES(stay_6nights_pct),
           stay_7plus_nights_pct=VALUES(stay_7plus_nights_pct),
           stay_type_total_pct=VALUES(stay_type_total_pct),source_file_id=VALUES(source_file_id)"""
        def rows():
            for r in read_dicts(path):
                canonical = mapper(r["지역"])
                (mapped_regions if canonical else unmapped_regions).add(r["지역"])
                period = datetime.strptime(r["기준연월"], "%Y%m").date()
                yield (r["지역"], period, canonical,
                       *(blank_to_none(r[c]) for c in PANEL_COLUMNS), file_id)
        for batch in chunks(rows(), 1000):
            cur.executemany(sql, batch)
    conn.commit()
    print(f"[데이터랩 월별] {count:,}행 · 자동 연결 {len(mapped_regions)}개 지역 · 보류 {len(unmapped_regions)}개 지역")


def catalog_zip(conn, path: Path):
    with conn.cursor() as cur:
        file_id = register_file(cur, path, None, "원본 보존 ZIP; 파일 목록만 DB에 등록")
        with zipfile.ZipFile(path) as zf:
            rows = [(file_id, info.filename, info.file_size, info.compress_size,
                     f"{info.CRC:08x}") for info in zf.infolist() if not info.is_dir()]
        cur.executemany(
            """INSERT INTO source_archive_entry
               (source_file_id,entry_name,byte_size,compressed_size,crc32)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE byte_size=VALUES(byte_size),
                 compressed_size=VALUES(compressed_size),crc32=VALUES(crc32)""", rows)
    conn.commit()
    print(f"[ZIP 목록] {path.name}: {len(rows)}개 파일")


def connect():
    required = ["MYSQL_USER", "MYSQL_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        sys.exit(f".env 설정 누락: {', '.join(missing)}")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "yaho_radar"),
        charset="utf8mb4",
        autocommit=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="CSV와 ZIP이 있는 yaho 폴더")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env)
    data_dir = args.data_dir.resolve()
    missing = [name for name in REQUIRED if not (data_dir / name).is_file()]
    if missing:
        sys.exit("필수 파일 누락:\n  " + "\n  ".join(missing))

    conn = connect()
    try:
        canonical = load_reference_tables(conn, data_dir)
        load_visitors(conn, data_dir / "signals_visitors_v2.csv", canonical)
        load_naver(conn, data_dir / "naver_all_daily_v2.csv", canonical)
        load_youtube(conn, data_dir / "yt_videos_top.csv", canonical)
        load_datalab_panel(conn, data_dir / "관광_월별패널_259개지역.csv")
        for name in OPTIONAL_ZIPS:
            path = data_dir / name
            if path.is_file():
                catalog_zip(conn, path)
        print("\n완료. 다음: mysql -u yaho_loader -p yaho_radar < 03_validate.sql")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
