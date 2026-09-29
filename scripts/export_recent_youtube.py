"""Export the latest seven calendar days of region travel videos for the UI.

Run collection/youtube_collect.py with --days 7 --sort date first. This feed is
separate from the historical LLM-classified content_type contract.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "youtube"
PROD = ROOT / "data" / "prod"
REGIONS = {
    "48310": ("거제", "거제시"),
    "12130": ("여수", "여수시"),
    "47940": ("울릉", "울릉군"),
    "51210": ("속초", "속초시"),
    "51750": ("영월", "영월군"),
    "51810": ("인제", "인제군"),
}
TRAVEL_TERMS = (
    "여행", "관광", "가볼", "맛집", "카페", "시장", "숙소", "숙박", "호텔", "펜션",
    "캠핑", "차박", "축제", "꽃밭", "트레킹", "산책", "드라이브", "풍경", "명소",
    "체험", "휴양", "계곡", "해변", "해수욕장", "섬", "포토", "브이로그", "vlog",
    "travel", "tour", "trip", "먹방", "방문", "코스", "갈만", "먹을", "힐링",
    "외도", "청령포", "장릉", "동강", "관음도", "행남", "자작나무", "폭포", "절경",
)
EXCLUDE_TERMS = (
    "매매", "급매", "분양", "부동산", "매물", "임대", "전원주택", "토지매입",
    "아파트시세", "인제대학교", "인제대학", "인제의대", "플란체",
    "김포맛집", "원주맛집", "제주시인제", "국감", "국정감사", "주문은 사이트",
)
ALIASES = {
    "울릉": ("울릉", "ulleung"),
    "여수": ("여수", "yeosu", "麗水"),
    "거제": ("거제", "geoje"),
    "속초": ("속초", "sokcho"),
    "영월": ("영월", "yeongwol"),
    "인제": ("인제", "inje"),
}


def relevant(video, region):
    title = video.get("title", "").lower()
    if not any(alias.lower() in title for alias in ALIASES[region]):
        return False
    if any(term.lower() in title for term in EXCLUDE_TERMS):
        return False
    if region == "인제" and ("제주" in title or re.search(r"제주시\s*인제", title)):
        return False
    if not any(term.lower() in title for term in TRAVEL_TERMS):
        return False
    title_before_tags = title.split("#", 1)[0].strip()
    if len(title_before_tags) >= 18 and not any(term.lower() in title_before_tags for term in TRAVEL_TERMS):
        return False
    return True


def main():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    end = now.date()
    start = end - timedelta(days=6)
    for code, (region, name) in REGIONS.items():
        candidates = sorted(RAW.glob(f"{region}_*.json"))
        if not candidates:
            raise FileNotFoundError(f"No YouTube collection for {region}")
        raw = json.loads(candidates[-1].read_text(encoding="utf-8"))
        if raw.get("sort") != "date" or raw.get("period_days") != 7:
            raise ValueError(f"{region}: latest collection must use --days 7 --sort date")
        items = [
            {key: video[key] for key in ("video_id", "title", "channel", "published_at", "view_count")}
            for video in raw["videos"]
            if start.isoformat() <= video["published_at"] <= end.isoformat()
            and relevant(video, region)
        ]
        items.sort(key=lambda video: (video["published_at"], video["view_count"]), reverse=True)
        channel_counts = {}
        limited = []
        for video in items:
            channel = video["channel"]
            if channel_counts.get(channel, 0) >= 3:
                continue
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
            limited.append(video)
        items = limited
        payload = {
            "_mock": False,
            "generated_at": now.isoformat(timespec="seconds"),
            "source": [{
                "name": "YouTube Data API v3",
                "provider": "Google",
                "retrieved_at": raw["collected_at"][:10],
                "note": f"{', '.join(raw['queries'])} 검색어별 최신 최대 50건에서 지역 관광 관련 영상 선별, 채널별 최대 3건",
            }],
            "period": {"start": start.isoformat(), "end": end.isoformat(), "granularity": "일"},
            "caveat": ["검색어와 검색 결과 수 제한 때문에 유튜브의 전체 게시 영상을 뜻하지 않습니다."],
            "data": {"region": {"code": code, "name": name}, "videos": items},
        }
        path = PROD / f"recent_youtube_{code}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(raw['videos'])}건 조회, {len(items)}건 표시 → {path.name}")


if __name__ == "__main__":
    main()
