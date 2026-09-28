"""화면의 지역 검색이 쓰는 지역 사전 — data/prod/regions/index.json.

각 시군구에 대해 검색 이름(시도 정식명·약칭·접미사 뺀 이름), 사례 지역 여부, 지금 경보 단계,
화면에서 열 수 있는 데이터 종류를 한 파일에 모은다. 화면은 이 파일 하나로 검색·정렬·배지를 처리하고,
지역을 고른 뒤에야 그 지역 파일(예측·신호 추이·경보)을 받는다.

원자료(dim_region)의 시도 코드는 팀 DB 체계다. 광주광역시 5개 구가 전남(12)에 섞여 있어
(12210~12330) 여기서 바로잡는다 — 그대로 두면 "광주 동구"로 검색되지 않는다.

사용법 (export_forecast.py --all, export_signal_series.py --all, judge_signal_status.py --all 다음에)
    uv run python scripts/build_region_index.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data" / "raw" / "db"
PROD = ROOT / "data" / "prod"
OUT = PROD / "regions" / "index.json"

# 화면의 사례 지역 키 (web/src/data/manifest.js의 REGION_MANIFEST 키와 같아야 한다)
SHOWCASE = {"51750": "yeongwol", "48310": "geoje", "12130": "yeosu", "51210": "sokcho", "51810": "inje",
            "47940": "ulleung"}
DEFAULT_REGION = "48310"  # 거제는 파일명 접미사가 없다

SIDO = {  # 팀 DB 시도 코드 → (정식명, 약칭, 옛 이름·다른 부름)
    "11": ("서울특별시", "서울", ["서울시"]),
    "26": ("부산광역시", "부산", ["부산시"]),
    "27": ("대구광역시", "대구", ["대구시"]),
    "28": ("인천광역시", "인천", ["인천시"]),
    "29": ("광주광역시", "광주", ["광주시"]),
    "30": ("대전광역시", "대전", ["대전시"]),
    "31": ("울산광역시", "울산", ["울산시"]),
    "36": ("세종특별자치시", "세종", ["세종시"]),
    "41": ("경기도", "경기", []),
    "43": ("충청북도", "충북", []),
    "44": ("충청남도", "충남", []),
    "47": ("경상북도", "경북", []),
    "48": ("경상남도", "경남", []),
    "50": ("제주특별자치도", "제주", ["제주도"]),
    "51": ("강원특별자치도", "강원", ["강원도"]),
    "52": ("전북특별자치도", "전북", ["전라북도"]),
    "12": ("전라남도", "전남", []),
}
GWANGJU = {"12210", "12240", "12270", "12300", "12330"}
ALERT_ORDER = ["관심", "주의", "경계", "심각"]


def region_file(kind: str, code: str) -> Path:
    if code in SHOWCASE:
        return PROD / (f"{kind}.json" if code == DEFAULT_REGION else f"{kind}_{code}.json")
    return PROD / "regions" / f"{kind}_{code}.json"


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def short_name(name: str) -> str | None:
    """'영월군' → '영월'. 남는 글자가 두 자 미만이면(중구 → 중) 약칭을 만들지 않는다."""
    for suffix in ("특별자치시", "시", "군", "구"):
        if name.endswith(suffix) and len(name) - len(suffix) >= 2:
            return name[: -len(suffix)]
    return None


def main() -> None:
    dim = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str, "sido_code": str})
    entries = []
    for r in dim.itertuples():
        sido_code = "29" if r.region_id in GWANGJU else r.sido_code
        sido, sido_short, sido_alias = SIDO[sido_code]
        if r.is_synthetic:
            # 인천 중구권·서구권은 이동통신 자료가 합산 단위라 학습에만 쓰고 화면용 파일이 없다
            entries.append({"code": r.region_id, "name": r.region_name, "sido": sido, "sido_short": sido_short,
                            "aliases": sido_alias, "disabled": True,
                            "note": "원자료가 여러 구를 합친 단위로만 제공돼 개별 조회를 지원하지 않습니다"})
            continue

        status = load(region_file("signal_status", r.region_id))
        series = load(region_file("signal_series", r.region_id))
        forecast = load(region_file("forecast", r.region_id))
        has = [k for k, v in (("signal_status", status), ("signal_series", series), ("forecast", forecast)) if v]
        if region_file("outlook", r.region_id).exists():
            has.append("outlook")
        if r.region_id in SHOWCASE:
            has += [k for k in ("timeline", "hotspots", "visitor_profile", "content_type", "checklist", "precedent",
                                "briefing") if region_file(k, r.region_id).exists()]

        entry = {"code": r.region_id, "name": r.region_name, "sido": sido, "sido_short": sido_short,
                 "aliases": [a for a in [short_name(r.region_name)] + sido_alias if a], "has": has}
        if r.region_id in SHOWCASE:
            entry["key"] = SHOWCASE[r.region_id]
            entry["case"] = True
        if status:
            d = status["data"]
            entry["alert"] = d["alert_level"]
            entry["alert_as_of"] = d["as_of"]
            entry["exceeded"] = d["agreement"]["exceeded_count"]
        if series:
            eps = [e for e in series["data"]["episodes"] if e["metric"] == "search"]
            if eps:
                top = max(eps, key=lambda e: e["peak"])
                entry["search_peak"] = {"peak": top["peak"], "date": top["peak_date"], "confirm": top["confirm"]}
            entry["points"] = bool(series["data"]["points"]["attractions"])
        entries.append(entry)

    entries.sort(key=lambda e: (e["sido_short"], e["name"]))
    payload = {"generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
               "count": sum(not e.get("disabled") for e in entries),
               "alert_order": ALERT_ORDER,
               "regions": entries}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    alerts = pd.Series([e.get("alert") for e in entries if not e.get("disabled")]).value_counts().to_dict()
    missing = [e["name"] for e in entries if not e.get("disabled") and len(e["has"]) < 4]
    print(f"{payload['count']}곳 → {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f}KB)")
    print(f"  경보 단계: {alerts} · 사례 지역 {sum(bool(e.get('case')) for e in entries)}곳")
    print(f"  예측·전망·신호 추이·경보 중 빠진 게 있는 지역: {missing or '없음'}")


if __name__ == "__main__":
    main()
