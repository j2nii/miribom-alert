"""Backfill YouTube descriptions/tags and load regional JSON files into MySQL.

Dry run (default):
    uv run python collection/youtube/backfill_youtube_metadata.py

Commit with full metadata refresh:
    uv run python collection/youtube/backfill_youtube_metadata.py --refresh-api --commit
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "raw" / "youtube"
DEFAULT_REPORT = ROOT / "data" / "processed" / "youtube_metadata_load_report.json"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"

REGION_NAMES = {
    "속초": ("51210", "속초시"),
    "여수": ("12130", "여수시"),
    "영월": ("51750", "영월군"),
    "울릉": ("47940", "울릉군"),
    "인제": ("51810", "인제군"),
    "거제": ("48310", "거제시"),
}

DERIVED_TAG_RULES = {
    "여행의도": ["여행", "관광", "가볼만한곳", "당일치기", "여행코스", "나들이"],
    "축제_행사": ["축제", "페스티벌", "행사", "공연", "콘서트", "불꽃놀이"],
    "촬영지_콘텐츠": [
        "촬영지", "영화", "드라마", "예능", "유튜브", "아이돌", "뮤직비디오",
        "성지순례", "바이럴", "로케이션",
    ],
    "음식_맛집": ["맛집", "먹방", "음식", "카페", "디저트", "시장", "로컬푸드"],
    "자연_힐링": ["자연", "힐링", "숲", "산", "바다", "해변", "해수욕장", "계곡", "공원"],
    "역사_문화": ["역사", "문화", "유적", "박물관", "사찰", "왕릉", "문화재"],
    "레포츠": ["레포츠", "서핑", "등산", "트레킹", "캠핑", "낚시", "스키", "자전거"],
    "숙박": ["호텔", "펜션", "리조트", "숙소", "캠핑장", "게스트하우스"],
    "교통_접근": ["주차", "교통", "버스", "기차", "드라이브", "가는법", "코스"],
    "재난_안전": ["폭우", "태풍", "산불", "폭설", "사고", "통제", "침수", "재난"],
    "지역홍보": ["홍보대사", "공식", "관광공사", "시청", "군청", "문화관광재단"],
    "계절여행": ["봄여행", "여름휴가", "단풍", "설경", "벚꽃", "휴가철", "피서"],
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def derive_tags(title: str, description: str, source_tags: list[str]) -> list[str]:
    corpus = normalize_text(" ".join([title, description, *source_tags]))
    return [
        category
        for category, keywords in DERIVED_TAG_RULES.items()
        if any(normalize_text(keyword) in corpus for keyword in keywords)
    ]


def env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def connect_db(args: argparse.Namespace):
    password = env_value("MYSQL_PASSWORD", "DB_PASSWORD")
    if not password:
        password = getpass.getpass(f"MySQL password for {args.db_user}: ")
    return pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=password,
        database=args.db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_files(input_dir: Path, pattern: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    files: list[dict[str, Any]] = []
    videos: dict[str, dict[str, Any]] = {}
    paths = sorted(input_dir.glob(pattern))
    if not paths:
        raise RuntimeError(f"No JSON files matched: {input_dir / pattern}")

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        region = str(payload.get("region", "")).strip()
        if region not in REGION_NAMES:
            raise RuntimeError(f"Unknown region '{region}' in {path.name}")
        region_id, canonical_name = REGION_NAMES[region]
        rows = payload.get("videos", [])
        if not isinstance(rows, list):
            raise RuntimeError(f"videos must be an array: {path.name}")

        file_info = {
            "path": path,
            "file_name": path.name,
            "sha256": sha256_file(path),
            "byte_size": path.stat().st_size,
            "row_count": len(rows),
            "region": region,
            "region_id": region_id,
            "canonical_name": canonical_name,
            "queries": payload.get("queries", []),
        }
        files.append(file_info)

        for rank, raw in enumerate(rows, start=1):
            video_id = str(raw.get("video_id", "")).strip()
            if not video_id:
                continue
            record = videos.setdefault(video_id, dict(raw))
            record.setdefault("associations", [])
            record["associations"].append(
                {
                    "file_name": path.name,
                    "region_id": region_id,
                    "source_region_name": region,
                    "queries": payload.get("queries", []),
                    "view_rank": rank,
                }
            )
    return files, videos


def youtube_key() -> str:
    key = env_value("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is missing from the repository .env file")
    return key


def refresh_metadata(videos: dict[str, dict[str, Any]]) -> tuple[int, list[str]]:
    key = youtube_key()
    video_ids = sorted(videos)
    returned_ids: set[str] = set()
    calls = 0
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        response = requests.get(
            YOUTUBE_API + "/videos",
            params={
                "key": key,
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(batch),
            },
            timeout=30,
        )
        if response.status_code != 200:
            detail = response.json().get("error", {}).get("message", response.text[:300])
            raise RuntimeError(f"YouTube API {response.status_code}: {detail}")
        calls += 1
        for item in response.json().get("items", []):
            video_id = item["id"]
            returned_ids.add(video_id)
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            record = videos[video_id]
            record.update(
                {
                    "title": snippet.get("title", record.get("title", "")),
                    "channel": snippet.get("channelTitle", record.get("channel", "")),
                    "published_at": snippet.get("publishedAt", record.get("published_at", "")),
                    "description": snippet.get("description", ""),
                    "tags": snippet.get("tags", []),
                    "duration": item.get("contentDetails", {}).get("duration"),
                    "view_count": int(stats.get("viewCount", record.get("view_count", 0) or 0)),
                    "like_count": int(stats.get("likeCount", record.get("like_count", 0) or 0)),
                    "comment_count": int(stats.get("commentCount", record.get("comment_count", 0) or 0)),
                }
            )
    unavailable = sorted(set(video_ids) - returned_ids)
    return calls, unavailable


def verify_regions(conn, files: list[dict[str, Any]]) -> None:
    expected = {item["region_id"]: item["canonical_name"] for item in files}
    placeholders = ",".join(["%s"] * len(expected))
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT region_id, region_name FROM dim_region WHERE region_id IN ({placeholders})",
            tuple(expected),
        )
        actual = {row["region_id"]: row["region_name"] for row in cur.fetchall()}
    if actual != expected:
        raise RuntimeError(f"Region mapping mismatch: expected={expected}, actual={actual}")


def existing_ids(conn, video_ids: list[str]) -> set[str]:
    found: set[str] = set()
    with conn.cursor() as cur:
        for start in range(0, len(video_ids), 500):
            batch = video_ids[start : start + 500]
            placeholders = ",".join(["%s"] * len(batch))
            cur.execute(f"SELECT video_id FROM youtube_video WHERE video_id IN ({placeholders})", batch)
            found.update(row["video_id"] for row in cur.fetchall())
    return found


def register_files(conn, files: list[dict[str, Any]]) -> dict[str, int]:
    ids: dict[str, int] = {}
    sql = """
        INSERT INTO source_file (file_name, sha256, byte_size, row_count, note)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            source_file_id = LAST_INSERT_ID(source_file_id),
            row_count = VALUES(row_count),
            note = VALUES(note)
    """
    with conn.cursor() as cur:
        for item in files:
            note = f"YouTube metadata JSON; region={item['canonical_name']}; imported by metadata backfill"
            cur.execute(
                sql,
                (item["file_name"], item["sha256"], item["byte_size"], item["row_count"], note),
            )
            ids[item["file_name"]] = int(cur.lastrowid)
    return ids


def parse_published_at(value: str) -> datetime:
    clean = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(clean)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def load_records(
    conn,
    videos: dict[str, dict[str, Any]],
    file_ids: dict[str, int],
) -> tuple[int, int, int]:
    video_sql = """
        INSERT INTO youtube_video (
            video_id, region_id, source_region_name, keyword_text, published_at,
            title, description, tags, derived_tags, duration_iso, metadata_fetched_at,
            channel_name, view_rank, window_month, view_count, like_count, comment_count,
            source_file_id
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, NOW(),
            %s, %s, %s, %s, %s, %s,
            %s
        )
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            description = VALUES(description),
            tags = VALUES(tags),
            derived_tags = VALUES(derived_tags),
            duration_iso = VALUES(duration_iso),
            metadata_fetched_at = NOW(),
            channel_name = VALUES(channel_name),
            view_count = VALUES(view_count),
            like_count = VALUES(like_count),
            comment_count = VALUES(comment_count)
    """
    match_sql = """
        INSERT INTO youtube_video_region_match (
            video_id, region_id, source_region_name, collected_queries, source_file_id
        ) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            source_region_name = VALUES(source_region_name),
            collected_queries = VALUES(collected_queries),
            source_file_id = VALUES(source_file_id),
            last_seen_at = CURRENT_TIMESTAMP
    """

    inserted_or_updated = 0
    associations = 0
    multi_region = 0
    with conn.cursor() as cur:
        for video_id, record in sorted(videos.items()):
            links = sorted(record["associations"], key=lambda x: (x["region_id"], x["file_name"]))
            primary = links[0]
            source_tags = [str(x) for x in (record.get("tags") or [])]
            derived = derive_tags(
                str(record.get("title", "")),
                str(record.get("description", "")),
                source_tags,
            )
            published_at = parse_published_at(str(record["published_at"]))
            queries = primary.get("queries", [])
            cur.execute(
                video_sql,
                (
                    video_id,
                    primary["region_id"],
                    primary["source_region_name"],
                    queries[0] if queries else None,
                    published_at,
                    str(record.get("title", "")),
                    str(record.get("description", "")),
                    json.dumps(source_tags, ensure_ascii=False),
                    json.dumps(derived, ensure_ascii=False),
                    record.get("duration"),
                    str(record.get("channel", "")) or None,
                    primary.get("view_rank"),
                    published_at.strftime("%Y-%m"),
                    int(record.get("view_count", 0) or 0),
                    int(record.get("like_count", 0) or 0),
                    int(record.get("comment_count", 0) or 0),
                    file_ids[primary["file_name"]],
                ),
            )
            inserted_or_updated += 1
            if len({link["region_id"] for link in links}) > 1:
                multi_region += 1
            for link in links:
                cur.execute(
                    match_sql,
                    (
                        video_id,
                        link["region_id"],
                        link["source_region_name"],
                        json.dumps(link.get("queries", []), ensure_ascii=False),
                        file_ids[link["file_name"]],
                    ),
                )
                associations += 1
    return inserted_or_updated, associations, multi_region


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--pattern", default="*_20260924_*.json")
    parser.add_argument("--refresh-api", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--db-host", default=env_value("MYSQL_HOST", "DB_HOST", default="localhost"))
    parser.add_argument("--db-port", type=int, default=int(env_value("MYSQL_PORT", "DB_PORT", default="3306")))
    parser.add_argument("--db-name", default=env_value("MYSQL_DATABASE", "DB_NAME", default="tour_earlywarning"))
    parser.add_argument("--db-user", default=env_value("MYSQL_USER", "DB_USER", default="yaho_loader"))
    return parser


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = build_parser().parse_args()
    files, videos = load_files(args.input_dir, args.pattern)
    api_calls = 0
    unavailable: list[str] = []
    if args.refresh_api:
        api_calls, unavailable = refresh_metadata(videos)

    conn = connect_db(args)
    try:
        verify_regions(conn, files)
        found = existing_ids(conn, sorted(videos))
        summary: dict[str, Any] = {
            "mode": "commit" if args.commit else "dry_run",
            "input_files": len(files),
            "input_rows": sum(item["row_count"] for item in files),
            "unique_videos": len(videos),
            "existing_videos": len(found),
            "new_videos": len(videos) - len(found),
            "regional_associations": sum(len(v["associations"]) for v in videos.values()),
            "cross_region_video_count": sum(
                len({x["region_id"] for x in v["associations"]}) > 1 for v in videos.values()
            ),
            "youtube_api_calls": api_calls,
            "youtube_api_units": api_calls,
            "api_unavailable_videos": unavailable,
        }

        if args.commit:
            file_ids = register_files(conn, files)
            loaded, associations, multi_region = load_records(conn, videos, file_ids)
            conn.commit()
            summary.update(
                {
                    "loaded_videos": loaded,
                    "loaded_associations": associations,
                    "loaded_multi_region_videos": multi_region,
                }
            )
        else:
            conn.rollback()

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nReport: {args.report}")
        if not args.commit:
            print("Dry run only. Database was not changed.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
