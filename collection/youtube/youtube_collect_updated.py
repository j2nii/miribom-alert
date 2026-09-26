"""YouTube Data API v3로 지역 관련 영상을 수집한다.

기본 검색어는 시계열 비교용으로 고정하고, 원인 탐색이 필요할 때만
--expanded-queries 옵션으로 추가 검색어를 사용한다.

사용법:
    uv run python collection/youtube_collect.py --region 거제
    uv run python collection/youtube_collect.py --region 거제 --expanded-queries --days 365
    uv run python collection/youtube_collect.py --region 거제 --queries "거제 여행" "거제 촬영지"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "youtube"
API = "https://www.googleapis.com/youtube/v3"

COST = {"search": 100, "videos": 1, "commentThreads": 1}

# 시계열 비교용 고정 검색어. 기존 수집 조건을 유지한다.
DEFAULT_QUERIES = ["{지역} 여행", "{지역} 가볼만한곳", "{지역} 맛집"]

# 바이럴 원인 탐색용 검색어. --expanded-queries에서만 추가한다.
EXPANDED_QUERIES = [
    "{지역} 축제",
    "{지역} 관광",
    "{지역} 촬영지",
    "{지역} 핫플",
    "{지역} 브이로그",
    "{지역} 성지순례",
]

# YouTube 업로더 태그와 분리해 저장하는 분석용 분류 사전.
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


class Quota:
    def __init__(self) -> None:
        self.used = 0

    def spend(self, endpoint: str, calls: int = 1) -> None:
        self.used += COST[endpoint] * calls


def get_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        sys.exit("YOUTUBE_API_KEY가 .env에 없습니다. .env.example을 참고하세요.")
    return key


def call(endpoint: str, key: str, **params) -> dict:
    params.update(key=key)
    response = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    if response.status_code != 200:
        detail = response.json().get("error", {}).get("message", response.text[:200])
        sys.exit(f"API 오류 {response.status_code} ({endpoint}): {detail}")
    return response.json()


def search_videos(key: str, query: str, days: int, limit: int, quota: Quota) -> list[str]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = call(
        "search",
        key,
        part="id",
        q=query,
        type="video",
        order="viewCount",
        maxResults=min(limit, 50),
        publishedAfter=published_after,
        regionCode="KR",
        relevanceLanguage="ko",
    )
    quota.spend("search")
    return [item["id"]["videoId"] for item in result.get("items", [])]


def fetch_details(key: str, video_ids: list[str], quota: Quota) -> list[dict]:
    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        result = call("videos", key, part="snippet,statistics,contentDetails", id=",".join(batch))
        quota.spend("videos")
        videos.extend(result.get("items", []))
    return videos


def fetch_comments(key: str, video_id: str, limit: int, quota: Quota) -> list[dict]:
    try:
        result = call("commentThreads", key, part="snippet", videoId=video_id, maxResults=limit, order="relevance")
    except SystemExit:
        return []
    quota.spend("commentThreads")
    return [
        {
            "text": item["snippet"]["topLevelComment"]["snippet"]["textOriginal"],
            "like_count": item["snippet"]["topLevelComment"]["snippet"]["likeCount"],
            "published_at": item["snippet"]["topLevelComment"]["snippet"]["publishedAt"][:10],
        }
        for item in result.get("items", [])
    ]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def derive_tags(title: str, description: str, source_tags: list[str]) -> list[str]:
    """제목·설명·원본 태그에서 분석용 범주 태그를 생성한다."""
    corpus = normalize_text(" ".join([title, description, *source_tags]))
    return [
        category
        for category, keywords in DERIVED_TAG_RULES.items()
        if any(normalize_text(keyword) in corpus for keyword in keywords)
    ]


def simplify(video: dict, matched_queries: list[str]) -> dict:
    snippet = video["snippet"]
    stats = video.get("statistics", {})
    description = snippet.get("description", "")
    source_tags = snippet.get("tags", [])
    return {
        "video_id": video["id"],
        "title": snippet["title"],
        "channel": snippet["channelTitle"],
        "published_at": snippet["publishedAt"][:10],
        # 원문과 업로더 태그는 자르지 않는다.
        "description": description,
        "tags": source_tags,
        # 분석용 태그는 원본 태그와 분리한다.
        "derived_tags": derive_tags(snippet["title"], description, source_tags),
        "matched_queries": matched_queries,
        "duration": video.get("contentDetails", {}).get("duration"),
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "url": f"https://www.youtube.com/watch?v={video['id']}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="거제", help="대상 지역명")
    parser.add_argument("--queries", nargs="*", help="직접 지정할 검색어 목록")
    parser.add_argument(
        "--expanded-queries",
        action="store_true",
        help="바이럴 원인 탐색용 검색어 6종을 기본 검색어에 추가",
    )
    parser.add_argument("--days", type=int, default=90, help="최근 N일 업로드분만")
    parser.add_argument("--limit", type=int, default=25, help="검색어당 수집 영상 수 (최대 50)")
    parser.add_argument("--comments", action="store_true", help="영상별 상위 댓글도 수집")
    parser.add_argument("--comment-limit", type=int, default=20)
    args = parser.parse_args()

    key = get_key()
    quota = Quota()
    if args.queries:
        queries = args.queries
        query_mode = "custom"
    else:
        templates = list(DEFAULT_QUERIES)
        if args.expanded_queries:
            templates.extend(EXPANDED_QUERIES)
        queries = [q.format(지역=args.region) for q in templates]
        query_mode = "expanded" if args.expanded_queries else "fixed"

    print(f"대상: {args.region} / 검색어 {len(queries)}개 / 최근 {args.days}일")
    print(f"검색 모드: {query_mode}\n")

    video_ids: list[str] = []
    query_matches: dict[str, list[str]] = {}
    for query in queries:
        found = search_videos(key, query, args.days, args.limit, quota)
        for video_id in found:
            query_matches.setdefault(video_id, []).append(query)
            if video_id not in video_ids:
                video_ids.append(video_id)
        print(f"  검색 '{query}': {len(found)}건")

    print(f"\n영상 상세 조회: {len(video_ids)}건")
    videos = [
        simplify(video, query_matches.get(video["id"], []))
        for video in fetch_details(key, video_ids, quota)
    ]

    if args.comments:
        print(f"댓글 수집: {len(videos)}개 영상")
        for video in videos:
            video["comments"] = fetch_comments(key, video["video_id"], args.comment_limit, quota)

    videos.sort(key=lambda v: -v["view_count"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = OUT_DIR / f"{args.region}_{stamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "region": args.region,
                "query_mode": query_mode,
                "queries": queries,
                "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "period_days": args.days,
                "count": len(videos),
                "videos": videos,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\n저장: {out_path.relative_to(ROOT)}")
    print(f"쿼터 사용: {quota.used} units / 일 10,000")
    if videos:
        print("\n상위 5건:")
        for video in videos[:5]:
            tags = ", ".join(video["derived_tags"]) or "분류 없음"
            print(f"  {video['view_count']:>9,}회  {video['published_at']}  {video['title'][:45]} [{tags}]")


if __name__ == "__main__":
    main()
