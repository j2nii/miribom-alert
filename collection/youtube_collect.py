"""YouTube Data API v3로 지역 관련 영상을 수집한다.

쿼터 설계: search.list는 호출당 100 units(하루 10,000 = 100회)라 검색 횟수를 인자로 제한하고,
영상 상세는 videos.list 배치 조회(50건당 1 unit)로 받는다.

사용법:
    uv run python collection/youtube_collect.py --region 거제
    uv run python collection/youtube_collect.py --region 거제 --queries "거제 여행" "거제 맛집" --days 90 --comments
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "youtube"
API = "https://www.googleapis.com/youtube/v3"

COST = {"search": 100, "videos": 1, "commentThreads": 1}

# 고정 검색어 템플릿 (설계결정 D-06)
# 시계열 비교를 하려면 수집 조건이 같아야 한다. 검색어가 바뀌면 건수 변화가
# 수요 변화인지 검색어 변화인지 구분할 수 없다.
# 지역명 단독 검색은 쓰지 않는다 — 인물명·상품명과 겹쳐 관광 콘텐츠가 밀려난다
# (2026-09-12 '거제' 실측에서 상위가 인물 예능으로 채워짐).
DEFAULT_QUERIES = ["{지역} 여행", "{지역} 가볼만한곳", "{지역} 맛집"]


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


def search_videos(key: str, query: str, days: int, limit: int, quota: Quota, sort: str = "viewCount") -> list[str]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = call(
        "search",
        key,
        part="id",
        q=query,
        type="video",
        order=sort,
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
        return []  # 댓글 비활성 영상
    quota.spend("commentThreads")
    return [
        {
            "text": item["snippet"]["topLevelComment"]["snippet"]["textOriginal"],
            "like_count": item["snippet"]["topLevelComment"]["snippet"]["likeCount"],
            "published_at": item["snippet"]["topLevelComment"]["snippet"]["publishedAt"][:10],
        }
        for item in result.get("items", [])
    ]


def simplify(video: dict) -> dict:
    snippet = video["snippet"]
    stats = video.get("statistics", {})
    return {
        "video_id": video["id"],
        "title": snippet["title"],
        "channel": snippet["channelTitle"],
        "published_at": snippet["publishedAt"][:10],
        "description": snippet.get("description", "")[:1500],
        "tags": snippet.get("tags", [])[:20],
        "duration": video.get("contentDetails", {}).get("duration"),
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "url": f"https://www.youtube.com/watch?v={video['id']}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="거제", help="대상 지역명")
    parser.add_argument("--queries", nargs="*", help="검색어 목록. 기본값은 고정 템플릿 3종(설계결정 D-06)")
    parser.add_argument("--days", type=int, default=90, help="최근 N일 업로드분만")
    parser.add_argument("--limit", type=int, default=25, help="검색어당 수집 영상 수 (최대 50)")
    parser.add_argument("--sort", choices=["viewCount", "date"], default="viewCount",
                        help="검색 결과 정렬. 최근 게시 영상 수집에는 date 사용")
    parser.add_argument("--comments", action="store_true", help="영상별 상위 댓글도 수집 (영상당 1 unit)")
    parser.add_argument("--comment-limit", type=int, default=20)
    args = parser.parse_args()

    key = get_key()
    quota = Quota()
    queries = args.queries or [q.format(지역=args.region) for q in DEFAULT_QUERIES]

    print(f"대상: {args.region} / 검색어 {len(queries)}개 / 최근 {args.days}일\n")

    video_ids: list[str] = []
    for query in queries:
        found = search_videos(key, query, args.days, args.limit, quota, args.sort)
        new = [v for v in found if v not in video_ids]
        video_ids.extend(new)
        print(f"  검색 '{query}': {len(found)}건 (신규 {len(new)}건)")

    print(f"\n영상 상세 조회: {len(video_ids)}건")
    videos = [simplify(v) for v in fetch_details(key, video_ids, quota)]

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
                "queries": queries,
                "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "period_days": args.days,
                "sort": args.sort,
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
            print(f"  {video['view_count']:>9,}회  {video['published_at']}  {video['title'][:45]}")


if __name__ == "__main__":
    main()
