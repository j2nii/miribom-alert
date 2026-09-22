#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_SYSTEM = "culture_festival_standard"
START_LIMIT = "2023-01-01"
END_LIMIT = "2026-08-31"

SIDO_CODES = {
    "서울특별시": "11", "부산광역시": "26", "대구광역시": "27",
    "인천광역시": "28", "광주광역시": "12", "대전광역시": "30",
    "울산광역시": "31", "세종특별자치시": "36", "경기도": "41",
    "강원도": "51", "강원특별자치도": "51", "충청북도": "43",
    "충청남도": "44", "전라북도": "52", "전북특별자치도": "52",
    "전라남도": "12", "경상북도": "47", "경상남도": "48",
    "제주특별자치도": "50", "제주도": "50",
}

SIDO_TEXT_CODES = {
    **SIDO_CODES,
    "서울": "11", "부산": "26", "대구": "27", "인천": "28",
    "광주": "12", "대전": "30", "울산": "31", "세종": "36",
    "경기": "41", "강원": "51", "충북": "43", "충남": "44",
    "전북": "52", "전남": "12", "경북": "47", "경남": "48", "제주": "50",
}

# 시군구 필드까지 비어 있고 광역 단위 기관만 적힌 소수 행사입니다.
EVENT_REGION_OVERRIDES = {
    "동인천 낭만축제": "IC_MID",
    "부산국제록페스티벌": "26530",  # 삼락생태공원, 부산 사상구
    "울산조선해양축제": "31170",    # 일산해수욕장, 울산 동구
    "울산대공원 장미축제": "31140",  # 울산대공원, 울산 남구
}

NAME_FIX = {
    "창원특례시": "창원시", "수원특례시": "수원시",
    "고양특례시": "고양시", "용인특례시": "용인시",
    "화성특례시": "화성시", "청원군": "청주시",
    "마산시": "창원시", "진해시": "창원시", "당진군": "당진시",
}


def cli():
    p = argparse.ArgumentParser(description="문화축제 표준데이터를 event/event_point에 적재")
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--env", type=Path, default=ROOT / ".env")
    p.add_argument("--start", default=START_LIMIT)
    p.add_argument("--end", default=END_LIMIT)
    p.add_argument("--commit", action="store_true")
    return p.parse_args()


def load_env(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def connect():
    try:
        import pymysql
    except ImportError as exc:
        raise SystemExit("PyMySQL이 없습니다. 00_setup.cmd를 먼저 실행하세요.") from exc
    required = ["MYSQL_USER", "MYSQL_PASSWORD"]
    missing = [k for k in required if not os.getenv(k) or os.getenv(k) == "CHANGE_ME"]
    if missing:
        raise SystemExit(".env 설정 필요: " + ", ".join(missing))
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4", autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def clean(v) -> str:
    return "" if v is None else str(v).strip()


def parse_date(v: str):
    s = clean(v).removesuffix(".0")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"날짜 해석 실패: {v}")


def normalize_name(v: str) -> str:
    s = re.sub(r"\s+", "", clean(v))
    return NAME_FIX.get(s, s)


def read_sources(data_dir: Path, start, end):
    files = sorted(data_dir.glob("KC_488_WNTY_CLTFSTVL_*.csv"))
    if len(files) != 7:
        raise SystemExit(f"CSV 7개가 필요합니다. 현재 {len(files)}개: {data_dir}")
    rows, stats = [], []
    for path in files:
        m = re.search(r"_(\d{4})\.csv$", path.name)
        snapshot = int(m.group(1)) if m else 0
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            source = list(csv.DictReader(f))
        kept = 0
        for r in source:
            begin, finish = parse_date(r["FSTVL_BEGIN_DE"]), parse_date(r["FSTVL_END_DE"])
            if not (start <= begin <= end):
                continue
            r.update(_source_path=path, _snapshot=snapshot, _begin=begin, _end=finish)
            rows.append(r); kept += 1
        stats.append((path, len(source), kept))

    rows.sort(key=lambda r: r["_snapshot"])
    unique = {}
    for r in rows:
        key = (
            normalize_name(r["FCLTY_NM"]), clean(r["CTPRVN_NM"]),
            normalize_name(r["SIGNGU_NM"]), r["_begin"], r["_end"],
        )
        unique[key] = r
    return list(unique.values()), stats


def fetch_regions(cur):
    cur.execute("SELECT region_id,region_name,sido_code FROM dim_region")
    return cur.fetchall()


def table_exists(cur, table_name):
    cur.execute("SHOW TABLES LIKE %s", (table_name,))
    return cur.fetchone() is not None


def fetch_aux_maps(cur):
    datalab = {}
    if table_exists(cur, "datalab_region_mapping"):
        cur.execute("""SELECT source_region_name,canonical_region_id,valid_from,valid_to
                       FROM datalab_region_mapping""")
        for r in cur.fetchall():
            datalab.setdefault(normalize_name(r["source_region_name"]), []).append(r)
    attraction = {}
    if table_exists(cur, "attraction_region_map"):
        cur.execute("""SELECT province_name,district_name,canonical_region_id
                       FROM attraction_region_map""")
        for r in cur.fetchall():
            key = (clean(r["province_name"]), normalize_name(r["district_name"]))
            attraction[key] = r["canonical_region_id"]
    return datalab, attraction


def valid_on(mapping, event_date):
    return ((mapping.get("valid_from") is None or mapping["valid_from"] <= event_date)
            and (mapping.get("valid_to") is None or mapping["valid_to"] >= event_date))


def map_region(row, regions, datalab_maps, attraction_maps):
    sido = SIDO_CODES.get(clean(row["CTPRVN_NM"]))
    district = normalize_name(row["SIGNGU_NM"])
    if not district and sido == "36":
        district = "세종특별자치시"

    # 법정동 코드 앞 5자리가 정본 코드와 같으면 가장 강한 매핑으로 사용합니다.
    legal_raw = clean(row.get("LEGALDONG_CD")).removesuffix(".0")
    legal = re.sub(r"\D", "", legal_raw).ljust(10, "0")
    legal5 = legal[:5] if len(legal) >= 5 else ""
    direct = [r for r in regions if r["region_id"] == legal5]
    if len(direct) == 1:
        return direct[0]["region_id"], "legal_code"

    # 수원시 장안구(41111)처럼 분석 정본이 상위 시(41110)인 일반구입니다.
    parent5 = legal5[:4] + "0" if len(legal5) == 5 else ""
    parent = [r for r in regions if r["region_id"] == parent5]
    if len(parent) == 1 and clean(parent[0]["sido_code"]) == sido:
        return parent[0]["region_id"], "legal_parent_city"

    candidates = [r for r in regions if normalize_name(r["region_name"]) == district]
    if sido:
        candidates = [r for r in candidates if clean(r["sido_code"]) == sido]
    if len(candidates) == 1:
        return candidates[0]["region_id"], "sido_name"

    # 기존 관광지/데이터랩 매핑을 재사용합니다.
    province = clean(row["CTPRVN_NM"])
    attraction_id = attraction_maps.get((province, district))
    if attraction_id:
        return attraction_id, "attraction_region_map"

    datalab_keys = [district, normalize_name(province + " " + clean(row["SIGNGU_NM"]))]
    for key in datalab_keys:
        matches = [m for m in datalab_maps.get(key, []) if valid_on(m, row["_begin"])]
        ids = {m["canonical_region_id"] for m in matches}
        if len(ids) == 1:
            return ids.pop(), "datalab_region_mapping"

    # 일반구 자료에서 시 이름이 SIGNGU_NM에서 빠진 경우 주소로 상위 시를 확인합니다.
    address = normalize_name(clean(row.get("RDNMADR_NM")) + " " + clean(row.get("OPMTN_PLACE_NM")))
    parent_candidates = [
        r for r in regions
        if clean(r["sido_code"]) == sido
        and normalize_name(r["region_name"]).endswith(("시", "군"))
        and normalize_name(r["region_name"]) in address
    ]
    if len(parent_candidates) == 1:
        return parent_candidates[0]["region_id"], "address_parent_city"

    # 일부 원본은 지역 관련 구조화 열이 전부 비어 있으나 제공기관·주소에는
    # '강원특별자치도 영월군'처럼 명확한 지역이 남아 있습니다.
    raw_text = " ".join(clean(row.get(k)) for k in (
        "CTPRVN_NM", "SIGNGU_NM", "RDNMADR_NM", "OPMTN_PLACE_NM",
        "PROVD_INSTT_NM", "MNNST_NM", "AUSPC_INSTT_NM", "FCLTY_NM",
    ))
    text = normalize_name(raw_text)
    inferred_sido = sido
    if not inferred_sido:
        # 긴 정식 명칭을 먼저 검사해 '전북' 같은 짧은 표현보다 우선합니다.
        aliases = sorted(SIDO_TEXT_CODES.items(), key=lambda x: len(x[0]), reverse=True)
        found = {code for alias, code in aliases if normalize_name(alias) in text}
        if len(found) == 1:
            inferred_sido = found.pop()

    # 인천 개편 지역은 dim_region에서 일반 구 코드 대신 합산 정본을 사용합니다.
    if inferred_sido == "28":
        if any(token in text for token in ("인천광역시중구", "인천광역시동구", "동인천")):
            if any(r["region_id"] == "IC_MID" for r in regions):
                return "IC_MID", "incheon_reform_text"
        if "인천광역시서구" in text:
            if any(r["region_id"] == "INCHEON_WEST" for r in regions):
                return "INCHEON_WEST", "incheon_reform_text"

    text_candidates = [
        r for r in regions
        if (not inferred_sido or clean(r["sido_code"]) == inferred_sido)
        and normalize_name(r["region_name"]) in text
    ]
    if text_candidates:
        longest = max(len(normalize_name(r["region_name"])) for r in text_candidates)
        best = [r for r in text_candidates if len(normalize_name(r["region_name"])) == longest]
        if len(best) == 1:
            return best[0]["region_id"], "source_text_region"

    override = EVENT_REGION_OVERRIDES.get(clean(row.get("FCLTY_NM")))
    if override and any(r["region_id"] == override for r in regions):
        return override, "event_override"
    return None, "unmapped"


def event_key(row, region_id):
    raw = "|".join([
        region_id, normalize_name(row["FCLTY_NM"]),
        row["_begin"].isoformat(), row["_end"].isoformat(),
    ])
    return "culture_festival:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


def file_hash(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_unmapped(rows):
    path = ROOT / "festival_unmapped.csv"
    fields = [
        "FCLTY_NM", "CTPRVN_NM", "SIGNGU_NM", "LEGALDONG_CD", "FSTVL_BEGIN_DE",
        "RDNMADR_NM", "OPMTN_PLACE_NM", "PROVD_INSTT_NM", "MNNST_NM", "AUSPC_INSTT_NM",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


def main():
    opt = cli(); load_env(opt.env)
    start, end = parse_date(opt.start), parse_date(opt.end)
    rows, stats = read_sources(opt.data_dir, start, end)
    print(f"[정제] {len(rows):,}개 고유 축제 · {start}~{end}")
    for p, total, kept in stats:
        print(f"  {p.name}: 원본 {total:,}행 · 기간 내 {kept:,}행")

    conn = connect()
    try:
        with conn.cursor() as cur:
            regions = fetch_regions(cur)
            datalab_maps, attraction_maps = fetch_aux_maps(cur)
            mapped, unmapped = [], []
            for r in rows:
                rid, method = map_region(r, regions, datalab_maps, attraction_maps)
                if rid:
                    r["_region_id"], r["_mapping_method"] = rid, method
                    mapped.append(r)
                else:
                    unmapped.append(r)
            print(f"[지역] 매핑 {len(mapped):,}건 · 미매핑 {len(unmapped):,}건 · 정본 {len(set(r['_region_id'] for r in mapped)):,}개")
            if unmapped:
                report = write_unmapped(unmapped)
                raise RuntimeError(f"미매핑 행이 있어 중단합니다: {report}")
            if not opt.commit:
                print("[검증 전용] DB는 변경하지 않았습니다.")
                print("실제 적재: 02_load_festivals.cmd")
                return 0

            source_ids = {}
            for p, total, _ in stats:
                digest = file_hash(p)
                cur.execute(
                    """INSERT INTO source_file(file_name,sha256,byte_size,row_count,note)
                       VALUES(%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE file_name=VALUES(file_name),
                         byte_size=VALUES(byte_size),row_count=VALUES(row_count),note=VALUES(note)""",
                    (p.name, digest, p.stat().st_size, total, "문화 빅데이터 플랫폼 전국 문화축제 표준데이터"),
                )
                cur.execute("SELECT source_file_id FROM source_file WHERE sha256=%s", (digest,))
                source_ids[p] = cur.fetchone()["source_file_id"]

            for i, r in enumerate(mapped, 1):
                key = event_key(r, r["_region_id"])
                note = " | ".join(filter(None, [
                    f"장소={clean(r.get('OPMTN_PLACE_NM'))}",
                    f"주최={clean(r.get('MNNST_NM'))}",
                    f"주관={clean(r.get('AUSPC_INSTT_NM'))}",
                    f"내용={clean(r.get('FSTVL_CN'))}",
                    f"매핑={r['_mapping_method']}",
                ]))
                cur.execute(
                    """INSERT INTO event
                         (event_key,region_id,event_name,event_type,evidence_url,evidence_note,source_file_id)
                       VALUES(%s,%s,%s,'festival',%s,%s,%s)
                       ON DUPLICATE KEY UPDATE region_id=VALUES(region_id),event_name=VALUES(event_name),
                         event_type=VALUES(event_type),evidence_url=VALUES(evidence_url),
                         evidence_note=VALUES(evidence_note),source_file_id=VALUES(source_file_id)""",
                    (key, r["_region_id"], clean(r["FCLTY_NM"])[:255],
                     clean(r.get("HMPG_ADDR")) or None, note, source_ids[r["_source_path"]]),
                )
                cur.execute("SELECT event_id FROM event WHERE event_key=%s", (key,))
                event_id = cur.fetchone()["event_id"]
                for typ, date in (("T0", r["_begin"]), ("end", r["_end"])):
                    cur.execute(
                        """INSERT INTO event_point(event_id,point_type,point_date,definition_note)
                           VALUES(%s,%s,%s,%s)
                           ON DUPLICATE KEY UPDATE point_date=VALUES(point_date),definition_note=VALUES(definition_note)""",
                        (event_id, typ, date, "문화축제 표준데이터 시작일" if typ == "T0" else "문화축제 표준데이터 종료일"),
                    )
                if i % 500 == 0:
                    print(f"  적재 {i:,}/{len(mapped):,}")
            conn.commit()

            cur.execute("SELECT COUNT(*) events,COUNT(DISTINCT region_id) regions FROM event WHERE event_key LIKE 'culture_festival:%'")
            result = cur.fetchone()
            cur.execute("""SELECT COUNT(*) points FROM event_point p JOIN event e ON e.event_id=p.event_id
                           WHERE e.event_key LIKE 'culture_festival:%'""")
            points = cur.fetchone()["points"]
            print(f"[적재 완료] 축제 {result['events']:,}건 · 지역 {result['regions']:,}개 · 시점 {points:,}건")
        return 0
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
