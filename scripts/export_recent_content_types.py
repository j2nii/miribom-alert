"""Export a reviewed, fixed title-based classification of the 2026-09-29 video snapshot.

This is deliberately separate from agent2's older LLM-classified archive. The
ordered-ID fingerprints prevent a later collection from inheriting these labels.
"""

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "data" / "prod"
TYPES = {
    "E": "예능·방송 노출형", "F": "맛집형", "P": "포토스팟형",
    "A": "체험·액티비티형", "V": "축제·이벤트형", "N": "자연경관형",
    "D": "드라마·영화촬영지형", "C": "코스·일정형", "X": "관광무관",
}

# One reviewed label per video in the committed recent_youtube snapshot.
# X covers titles whose regional tourism relevance cannot be established.
SNAPSHOTS = {
    "51750": ("253c0b05c19ba047", "C F N N D N A N D C A N N N D C V"),
    "48310": ("70ac00c920263442", "F F C F F E F F A F C F F C F F C A A A C F A F F A A C P N F F A N A F A"),
    "12130": ("3f31812b02ef92bb", "F C V V C F V F V F F V N F X C C F F N V X F V V F F C C X A X C V C C X C X F F"),
    "47940": ("e1445c9d67965562", "C C"),
    "51210": ("ba9e46afbccd2729", "C F F C F A F F F F F C F C C C A F F N F F F C F C A C C F A F"),
    "51810": ("48aff79e73daee6d", "V V V V C A N C A A N V V V V"),
}


def build(code, fingerprint, labels):
    source = json.loads((PROD / f"recent_youtube_{code}.json").read_text(encoding="utf-8"))
    videos = source["data"]["videos"]
    codes = labels.split()
    digest = hashlib.sha256("\n".join(v["video_id"] for v in videos).encode()).hexdigest()[:16]
    if digest != fingerprint or len(videos) != len(codes):
        raise ValueError(f"{code}: video snapshot changed; review labels again")

    items = []
    for video, category in zip(videos, codes, strict=True):
        item = {
            **video,
            "content_type": TYPES[category],
            "confidence": 0.6 if category != "X" else 0.5,
            "evidence": f"제목에 ‘{video['title'][:100]}’라고 표시됨",
        }
        items.append(item)

    counted = [item for item in items if item["content_type"] != "관광무관"]
    counts = Counter(item["content_type"] for item in counted)
    views = Counter()
    for item in counted:
        views[item["content_type"]] += item["view_count"]
    summary = [
        {"content_type": category, "count": count,
         "ratio": round(count / len(counted), 4), "total_views": views[category]}
        for category, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return {
        "_mock": False,
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "source": [{
            "name": "YouTube Data API v3 수집 영상의 제목 검토 분류",
            "provider": "Google / 제출본 수동 검토",
            "retrieved_at": source["source"][0]["retrieved_at"],
            "note": "지역별 최근 7일 게시·수집 시 조회수 500회 이상인 영상의 제목을 9개 유형으로 검토해 분류",
        }],
        "period": source["period"],
        "caveat": [
            "영상 내용을 시청하지 않고 제목만으로 분류했다.",
            "유튜브 전체 게시물은 아니며 검색어별 결과와 채널별 최대 2건의 표본이다.",
        ],
        "data": {
            "region": source["data"]["region"],
            "items": items,
            "summary": summary,
            "unclassified_count": len(items) - len(counted),
        },
    }


def main():
    for code, (fingerprint, labels) in SNAPSHOTS.items():
        payload = build(code, fingerprint, labels)
        path = PROD / f"recent_content_type_{code}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(code, len(payload["data"]["items"]), "videos,", len(payload["data"]["summary"]), "types")


if __name__ == "__main__":
    main()
