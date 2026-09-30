from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import os
import sys
import time
from datetime import date, datetime, timedelta

import requests

from common import (
    KST,
    OUTPUT_DIR,
    ROOT,
    api_get_json,
    as_float,
    assert_collection_open,
    collection_range,
    connect_db,
    day_chunks,
    export_query_csv,
    finish_run,
    json_text,
    load_environment,
    normalize_items,
    parse_date,
    parse_datetime,
    service_key,
    start_run,
)


TOUR_ENDPOINTS = (
    ("KorService2/searchFestival2", "https://apis.data.go.kr/B551011/KorService2/searchFestival2"),
)
ASOS_ENDPOINT = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
WARNING_ENDPOINT = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList"


def paginated(
    session: requests.Session,
    url: str,
    base_params: dict,
    *,
    rows_per_page: int,
):
    page = 1
    while True:
        params = dict(base_params)
        params.update({"pageNo": page, "numOfRows": rows_per_page})
        payload = api_get_json(session, url, params)
        rows, total = normalize_items(payload)
        yield rows, total, page
        if not rows or page * rows_per_page >= total:
            break
        page += 1
        time.sleep(0.15)


def collect_festivals(conn, session: requests.Session) -> tuple[int, int]:
    source = "tourapi_festival"
    run_id = start_run(conn, source)
    received = stored = 0
    start, end = collection_range()
    key = service_key("TOUR")
    active_endpoint: tuple[str, str] | None = None
    try:
        for year in range(start.year, end.year + 1):
            year_start = max(start, date(year, 1, 1))
            year_end = min(end, date(year, 12, 31))
            base = {
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TourEarlyWarning",
                "_type": "json",
                "listYN": "Y",
                "arrange": "A",
                "eventStartDate": year_start.strftime("%Y%m%d"),
                "eventEndDate": year_end.strftime("%Y%m%d"),
            }
            ordered_endpoints = list(TOUR_ENDPOINTS)
            if active_endpoint is not None:
                ordered_endpoints.sort(key=lambda candidate: candidate != active_endpoint)
            errors: list[str] = []
            first_success = None
            selected = None
            for candidate in ordered_endpoints:
                try:
                    candidate_pages = paginated(
                        session, candidate[1], base, rows_per_page=1000
                    )
                    first_rows, first_total, first_page = next(candidate_pages)
                    result = (
                        candidate,
                        itertools.chain(
                            [(first_rows, first_total, first_page)], candidate_pages
                        ),
                    )
                    if first_success is None:
                        first_success = result
                    if first_rows or first_total > 0:
                        selected = result
                        break
                except Exception as exc:  # endpoint compatibility fallback
                    errors.append(f"{candidate[0]}: {exc}")
            if selected is None:
                selected = first_success
            if selected is None:
                raise RuntimeError("TourAPI 엔드포인트 확인 실패: " + " | ".join(errors))
            active_endpoint, pages = selected

            print(f"[행사] {year_start}~{year_end} · {active_endpoint[0]}")
            for rows, total, page in pages:
                print(f"  페이지 {page} · {len(rows)}건 / 전체 {total}건")
                received += len(rows)
                with conn.cursor() as cur:
                    for item in rows:
                        content_id = str(item.get("contentid") or item.get("contentId") or "").strip()
                        start_text = str(item.get("eventstartdate") or "").strip()
                        end_text = str(item.get("eventenddate") or "").strip()
                        if not content_id:
                            continue
                        digest_source = f"{content_id}|{start_text}|{end_text}"
                        festival_key = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
                        cur.execute(
                            """INSERT INTO raw_tourapi_festival(
                                   festival_key,content_id,title,event_start_date,event_end_date,
                                   address1,address2,area_code,sigungu_code,map_x,map_y,telephone,
                                   first_image,modified_time,source_api,raw_json)
                               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE
                                   title=VALUES(title), event_start_date=VALUES(event_start_date),
                                   event_end_date=VALUES(event_end_date), address1=VALUES(address1),
                                   address2=VALUES(address2), area_code=VALUES(area_code),
                                   sigungu_code=VALUES(sigungu_code), map_x=VALUES(map_x),
                                   map_y=VALUES(map_y), telephone=VALUES(telephone),
                                   first_image=VALUES(first_image), modified_time=VALUES(modified_time),
                                   source_api=VALUES(source_api), raw_json=VALUES(raw_json)""",
                            (
                                festival_key,
                                content_id,
                                item.get("title"),
                                parse_date(start_text, "%Y%m%d"),
                                parse_date(end_text, "%Y%m%d"),
                                item.get("addr1"),
                                item.get("addr2"),
                                item.get("areacode"),
                                item.get("sigungucode"),
                                as_float(item.get("mapx")),
                                as_float(item.get("mapy")),
                                item.get("tel"),
                                item.get("firstimage"),
                                item.get("modifiedtime"),
                                active_endpoint[0],
                                json_text(item),
                            ),
                        )
                        stored += 1
                conn.commit()
        finish_run(conn, run_id, "success", received, stored)
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", received, stored, str(exc)[:2000])
        raise

    rows = export_query_csv(
        conn,
        """SELECT content_id,title,event_start_date,event_end_date,address1,address2,
                  area_code,sigungu_code,map_x,map_y,telephone,source_api,collected_at
           FROM raw_tourapi_festival
           ORDER BY event_start_date,content_id""",
        OUTPUT_DIR / "tourapi_festivals_202301_202608.csv",
    )
    print(f"[행사 완료] API {received}건 처리 · DB/CSV {rows}건")
    return received, rows


def read_stations() -> list[dict[str, str]]:
    path = ROOT / "asos_stations.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def collect_asos(conn, session: requests.Session) -> tuple[int, int]:
    source = "kma_asos_daily"
    run_id = start_run(conn, source)
    received = stored = 0
    start, end = collection_range()
    key = service_key("KMA")
    stations = read_stations()
    try:
        for index, station in enumerate(stations, start=1):
            station_id = station["station_id"].strip()
            base = {
                "ServiceKey": key,
                "dataType": "JSON",
                "dataCd": "ASOS",
                "dateCd": "DAY",
                "startDt": start.strftime("%Y%m%d"),
                "endDt": end.strftime("%Y%m%d"),
                "stnIds": station_id,
            }
            station_received = 0
            # The KMA endpoint rejects requests above 1,000 rows (error 99).
            # Use a conservative page size and let paginated() fetch page 2.
            for rows, total, page in paginated(session, ASOS_ENDPOINT, base, rows_per_page=999):
                station_received += len(rows)
                received += len(rows)
                with conn.cursor() as cur:
                    for item in rows:
                        observed = parse_date(item.get("tm"), "%Y-%m-%d", "%Y%m%d")
                        actual_station = str(item.get("stnId") or station_id)
                        if observed is None:
                            continue
                        cur.execute(
                            """INSERT INTO raw_kma_asos_daily(
                                   station_id,observed_date,station_name,avg_temperature_c,
                                   min_temperature_c,max_temperature_c,precipitation_mm,
                                   avg_humidity_pct,max_wind_speed_ms,max_instant_wind_speed_ms,
                                   snow_depth_cm,weather_summary,raw_json)
                               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE
                                   station_name=VALUES(station_name),
                                   avg_temperature_c=VALUES(avg_temperature_c),
                                   min_temperature_c=VALUES(min_temperature_c),
                                   max_temperature_c=VALUES(max_temperature_c),
                                   precipitation_mm=VALUES(precipitation_mm),
                                   avg_humidity_pct=VALUES(avg_humidity_pct),
                                   max_wind_speed_ms=VALUES(max_wind_speed_ms),
                                   max_instant_wind_speed_ms=VALUES(max_instant_wind_speed_ms),
                                   snow_depth_cm=VALUES(snow_depth_cm),
                                   weather_summary=VALUES(weather_summary), raw_json=VALUES(raw_json)""",
                            (
                                actual_station,
                                observed,
                                item.get("stnNm") or station.get("station_name"),
                                as_float(item.get("avgTa")),
                                as_float(item.get("minTa")),
                                as_float(item.get("maxTa")),
                                as_float(item.get("sumRn")),
                                as_float(item.get("avgRhm")),
                                as_float(item.get("maxWs")),
                                as_float(item.get("maxInsWs")),
                                as_float(item.get("ddMes")),
                                item.get("iscs"),
                                json_text(item),
                            ),
                        )
                        stored += 1
                conn.commit()
            print(
                f"[기상 {index}/{len(stations)}] {station_id} "
                f"{station.get('station_name','')} · {station_received}건"
            )
            time.sleep(0.1)
        finish_run(conn, run_id, "success", received, stored)
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", received, stored, str(exc)[:2000])
        raise

    rows = export_query_csv(
        conn,
        """SELECT station_id,station_name,observed_date,avg_temperature_c,
                  min_temperature_c,max_temperature_c,precipitation_mm,
                  avg_humidity_pct,max_wind_speed_ms,max_instant_wind_speed_ms,
                  snow_depth_cm,weather_summary,collected_at
           FROM raw_kma_asos_daily
           ORDER BY station_id,observed_date""",
        OUTPUT_DIR / "kma_asos_daily_202301_202608.csv",
    )
    print(f"[기상 완료] API {received}건 처리 · DB/CSV {rows}건")
    return received, rows


def collect_warnings(conn, session: requests.Session) -> tuple[int, int]:
    source = "kma_weather_warning"
    run_id = start_run(conn, source)
    received = stored = 0
    start, end = collection_range()
    key = service_key("KMA")
    configured_station = (os.getenv("KMA_WARNING_STN_ID") or "").strip()
    try:
        # This endpoint exposes only the rolling seven-day window ending today.
        # It cannot backfill the historical analysis period.
        today_kst = datetime.now(KST).date()
        available_start = today_kst - timedelta(days=6)
        available_end = today_kst
        effective_start = max(start, available_start)
        effective_end = min(end, available_end)
        if effective_start > effective_end:
            note = (
                "기상특보 API는 오늘 기준 최근 7일만 조회할 수 있어 "
                f"요청 기간 {start}~{end}은 소급 수집할 수 없습니다."
            )
            finish_run(conn, run_id, "success", 0, 0, note)
            print(f"[특보 제외] {note}")
            return 0, 0
        chunks = list(day_chunks(effective_start, effective_end, 7))
        for index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            base = {
                "ServiceKey": key,
                "dataType": "JSON",
                "fromTmFc": chunk_start.strftime("%Y%m%d"),
                "toTmFc": chunk_end.strftime("%Y%m%d"),
            }
            if configured_station:
                base["stnId"] = configured_station
            chunk_received = 0
            for rows, total, page in paginated(session, WARNING_ENDPOINT, base, rows_per_page=1000):
                chunk_received += len(rows)
                received += len(rows)
                with conn.cursor() as cur:
                    for item in rows:
                        station_id = str(item.get("stnId") or configured_station or "").strip()
                        sequence = str(item.get("tmSeq") or "").strip()
                        tm_fc = str(item.get("tmFc") or "").strip()
                        title = str(item.get("title") or "").strip()
                        digest = hashlib.sha256(
                            f"{station_id}|{tm_fc}|{sequence}|{title}".encode("utf-8")
                        ).hexdigest()
                        cur.execute(
                            """INSERT INTO raw_kma_warning(
                                   warning_key,station_id,announcement_sequence,
                                   announcement_at,title,raw_json)
                               VALUES(%s,%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE station_id=VALUES(station_id),
                                   announcement_sequence=VALUES(announcement_sequence),
                                   announcement_at=VALUES(announcement_at),title=VALUES(title),
                                   raw_json=VALUES(raw_json)""",
                            (
                                digest,
                                station_id or None,
                                sequence or None,
                                parse_datetime(tm_fc, "%Y%m%d%H%M", "%Y-%m-%d %H:%M"),
                                title or None,
                                json_text(item),
                            ),
                        )
                        stored += 1
                conn.commit()
            print(
                f"[특보 {index}/{len(chunks)}] {chunk_start}~{chunk_end} · {chunk_received}건"
            )
            time.sleep(0.1)
        finish_run(conn, run_id, "success", received, stored)
    except Exception as exc:
        conn.rollback()
        finish_run(conn, run_id, "failed", received, stored, str(exc)[:2000])
        raise

    rows = export_query_csv(
        conn,
        """SELECT station_id,announcement_sequence,announcement_at,title,collected_at
           FROM raw_kma_warning
           ORDER BY announcement_at,station_id,announcement_sequence""",
        OUTPUT_DIR / "kma_weather_warnings_202301_202608.csv",
    )
    print(f"[특보 완료] API {received}건 처리 · DB/CSV {rows}건")
    return received, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="2026-09-22 마감 전 최종 공공데이터 수집")
    parser.add_argument(
        "source",
        choices=("festivals", "weather", "warnings", "all"),
        help="수집할 원천",
    )
    args = parser.parse_args()
    load_environment()
    assert_collection_open()
    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = connect_db()
    session = requests.Session()
    session.headers.update({"User-Agent": "tour-early-warning-final-collector/1.0"})
    try:
        if args.source in {"festivals", "all"}:
            collect_festivals(conn, session)
        if args.source in {"weather", "all"}:
            collect_asos(conn, session)
        if args.source in {"warnings", "all"}:
            collect_warnings(conn, session)
    finally:
        session.close()
        conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
