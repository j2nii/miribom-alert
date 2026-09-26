"""화면의 '신호 추이' 차트용 JSON을 만든다 — data/prod/signal_series[_지역코드].json.

무엇을 담는가
    1) 일별: 검색지수·외지인 방문자의 '전년 동요일 대비 배율 7일 중앙값'(D-12 통계량)과 임계,
       외지인 방문자 실측·전년 같은 요일, 테스트 기간 7일 앞 백테스트 예측
    2) 임계 초과 구간(episodes) — agents/signals.py의 규칙 그대로. 에이전트① 타임라인과 같은 날짜가 나온다
    3) 월별: 관광지점 전년 대비 배율 vs 시군구 총량 전년 대비 배율 — point_level.py의 정의 그대로

판정을 새로 만들지 않는다. 이미 쓰는 정의(signals.py, point_level.py, export_forecast.py의 백테스트)를
화면이 그릴 수 있게 옮길 뿐이다. 그래서 차트의 숫자는 타임라인·확정수치와 어긋나지 않는다.

입력
    data/raw/db/daily_all.csv               (agents/signals.py가 읽는 일별 신호)
    data/interim/forecast_backtest_h7.csv   (export_forecast.py가 남기는 테스트 기간 실제·예측)
    data/interim/attraction_monthly.csv     (point_level.py가 남기는 관광지점 월별 입장객)
    data/interim/panel_daily.csv            (시군구 월 합계용)

사용법
    uv run python analysis/src/forecast/export_signal_series.py           # 사례 6개 지역
    uv run python analysis/src/forecast/export_signal_series.py --all     # 실제 시군구 226곳
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "scripts"))

from baseline import SPLITS, smape  # noqa: E402
from export_forecast import DEFAULT_REGION, SHOWCASE  # noqa: E402
from point_level import MIN_BASE, POINT_SURGE, REGION_FLAT, load_points, paired_point_ratios, region_monthly  # noqa: E402
from signals import BASELINE, MIN_DURATION, PERCENTILE, SignalFrames  # noqa: E402
from validate_data import validate_payload  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PROD = ROOT / "data" / "prod"

DAILY_START = "2025-09-01"   # 화면은 최근 1년을 그린다. 2026년 설(2/16~18)과 그 앞뒤가 들어간다
POINT_MONTHS = 12            # 지점 차트는 지점 자료 마지막 달부터 거슬러 12개월
TOP_ATTRACTIONS = 5          # 배율 최댓값이 큰 지점부터
MIN_POINT_MONTHS = 3         # 짝지어진 달이 이보다 적은 지점은 선이 끊겨 읽을 수 없다


def rnd(value, digits: int = 3):
    return None if value is None or pd.isna(value) else round(float(value), digits)


def whole(value):
    return None if value is None or pd.isna(value) else int(round(float(value)))


def daily_rows(frames: SignalFrames, backtest: pd.DataFrame, region: str, end: pd.Timestamp) -> list[dict]:
    days = pd.date_range(DAILY_START, end, freq="D")
    search = frames.stat["interest_naver"][region].reindex(days)
    visitors_stat = frames.stat["realization_visitors"][region].reindex(days)
    raw = frames.raw["realization_visitors"][region]
    visitors = raw.reindex(days)
    visitors_ly = raw.shift(364).reindex(days)
    pred = backtest[backtest["region_id"] == region].set_index("observed_date")["pred"].reindex(days)
    return [{"date": d.strftime("%Y-%m-%d"), "search_stat": rnd(search[d]), "visitors_stat": rnd(visitors_stat[d]),
             "visitors": whole(visitors[d]), "visitors_ly": whole(visitors_ly[d]), "backtest": whole(pred[d])}
            for d in days]


def episode_rows(frames: SignalFrames, region: str) -> list[dict]:
    rows = []
    for metric, key in (("interest_naver", "search"), ("realization_visitors", "visitors")):
        end = frames.data_end[metric].strftime("%Y-%m-%d")
        for ep in frames.episodes(metric, region, DAILY_START, end):
            rows.append({"metric": key, "start": ep.start.strftime("%Y-%m-%d"),
                         "confirm": ep.confirm.strftime("%Y-%m-%d"), "end": ep.end.strftime("%Y-%m-%d"),
                         "peak": round(ep.peak, 2), "peak_date": ep.peak_date.strftime("%Y-%m-%d")})
    return sorted(rows, key=lambda r: r["start"])


def backtest_summary(backtest: pd.DataFrame, region: str) -> dict:
    own = backtest[backtest["region_id"] == region]
    actual, pred = own["visitors_external"].to_numpy(), own["pred"].to_numpy()
    return {
        "period": {"start": SPLITS["test"][0], "end": SPLITS["test"][1], "granularity": "일"},
        "n": int(len(own)),
        "smape": round(float(smape(actual, pred)), 2),
        "mae": round(float(np.mean(np.abs(actual - pred)))),
        "national_smape": round(float(smape(backtest["visitors_external"].to_numpy(), backtest["pred"].to_numpy())), 2),
    }


def point_block(ratios: pd.DataFrame, regions: pd.DataFrame, region: str) -> tuple[dict, str | None]:
    own = ratios[(ratios["region_id"] == region) & (ratios["prev"] >= MIN_BASE)]
    block = {"months": [], "region_total": [], "attractions": [],
             "min_base": MIN_BASE, "surge": POINT_SURGE, "flat": REGION_FLAT}
    if own.empty:
        return block, None
    last = own["month"].max()
    months = pd.period_range(last - (POINT_MONTHS - 1), last, freq="M")
    block["months"] = [str(m) for m in months]

    total = regions[regions["region_id"] == region].set_index("month")
    block["region_total"] = [{"month": str(m),
                              "ratio": rnd(total["region_ratio"].get(m), 3),
                              "visitors": whole(total["visitors_external"].get(m))} for m in months]

    window = own[own["month"].isin(months)]
    candidates = []
    for name, group in window.groupby("attraction_name"):
        if len(group) < MIN_POINT_MONTHS:
            continue
        group = group.sort_values("month")
        candidates.append({
            "name": name,
            "max_ratio": round(float(group["point_ratio"].max()), 2),
            "series": [{"month": str(r.month), "ratio": round(float(r.point_ratio), 3),
                        "visitors": int(r.visitor_count), "prev": int(r.prev)} for r in group.itertuples()],
        })
    block["attractions"] = sorted(candidates, key=lambda c: -c["max_ratio"])[:TOP_ATTRACTIONS]
    return block, str(last)


def build_payload(region: str, name: str, frames: SignalFrames, backtest: pd.DataFrame,
                  ratios: pd.DataFrame, regions: pd.DataFrame) -> dict:
    search_end, visitors_end = frames.data_end["interest_naver"], frames.data_end["realization_visitors"]
    end = max(search_end, visitors_end)
    points, points_end = point_block(ratios, regions, region)
    summary = backtest_summary(backtest, region)
    retrieved = datetime.now().strftime("%Y-%m-%d")
    thresholds = {"search": frames.threshold["interest_naver"], "visitors": frames.threshold["realization_visitors"],
                  "min_duration": MIN_DURATION,
                  "basis": f"전년 같은 요일 대비 배율의 7일 중앙값, {BASELINE[0][:4]}년 전국 {int(PERCENTILE * 100)}백분위 "
                           f"(사례 지역을 보고 정하지 않음, D-12). {MIN_DURATION}일 연속 넘으면 {MIN_DURATION}번째 날 신호 확정"}

    caveat = [
        "검색 신호는 급증을 '미리' 알려주지 않는다. 2026년 시험 구간에서 월 단위 조기경보 판별력은 AUC 0.217(검증 0.941에서 방향이 뒤집힘), "
        "지점 급증 판별력은 AUC 0.482였다(확정수치_0924). 이 곡선은 사건을 사후에 확인하고 사례를 설명하는 용도다.",
        f"배율 곡선은 에이전트① 타임라인과 같은 규칙(agents/signals.py, D-12)으로 계산했다. 임계 검색 {thresholds['search']}배·"
        f"외지인 방문자 {thresholds['visitors']}배는 {BASELINE[0][:4]}년 전국 {int(PERCENTILE * 100)}백분위다.",
        f"백테스트 곡선은 각 날짜보다 7일 앞선 시점에 공개돼 있던 정보만 써서 낸 예측이다(방문자 4일·데이터랩 익월 17일 공개 반영). "
        f"{name} sMAPE {summary['smape']}%, 전국 {summary['national_smape']}%.",
        f"지점 배율은 같은 지점의 같은 달을 전년과 짝지어 비교했고, 전년 같은 달 입장객 {MIN_BASE:,}명 미만 지점은 뺐다(point_level.py). "
        "시군구 총량도 같은 잣대(월 합계 전년 대비)로 쟀다.",
        "1~2월의 전년 대비는 설 연휴 이동(2025년 1월 → 2026년 2월)으로 오염돼 있다. 이 두 달의 배율은 명절 효과를 포함한다.",
    ]
    if points_end is None:
        caveat.append(f"{name}은 전년 같은 달 {MIN_BASE:,}명 이상인 관광지점 입장객 자료가 없어 지점 비교를 그리지 않는다.")
    elif points_end < "2026-03":
        caveat.append(f"{name}의 관광지점 입장객은 DB에 {points_end}까지만 있다. 2026년 지점 비교는 할 수 없다.")

    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {"name": "이동통신 기반 시군구 일별 방문자", "provider": "한국관광공사(공공데이터포털 15101972)",
             "retrieved_at": retrieved, "url": "https://www.data.go.kr/data/15101972/openapi.do",
             "note": "외지인 방문자수. 팀 DB vw_daily_core_signal"},
            {"name": "네이버 데이터랩 검색어 트렌드", "provider": "네이버", "retrieved_at": retrieved,
             "note": "시군구명 검색지수"},
            {"name": "한국관광 데이터랩 인기 관광지 현황(관광지점 월별 입장객)", "provider": "한국관광공사",
             "retrieved_at": retrieved, "url": "https://datalab.visitkorea.or.kr/",
             "note": "major_attraction_visitors_monthly, 합계 기준"},
        ],
        "period": {"start": DAILY_START, "end": end.strftime("%Y-%m-%d"), "granularity": "일"},
        "caveat": caveat,
        "data": {
            "region": {"code": region, "name": name},
            "as_of": {"search": search_end.strftime("%Y-%m-%d"), "visitors": visitors_end.strftime("%Y-%m-%d"),
                      "points": points_end},
            "thresholds": thresholds,
            "daily": daily_rows(frames, backtest, region, end),
            "episodes": episode_rows(frames, region),
            "backtest": summary,
            "points": points,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", nargs="+", default=sorted(SHOWCASE), help="지역 코드 (기본 사례 6개 지역)")
    parser.add_argument("--all", action="store_true", help="실제 시군구 226곳 전체")
    args = parser.parse_args()

    backtest = pd.read_csv(INTERIM / "forecast_backtest_h7.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    names = (pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, usecols=["region_id", "region_name"])
             .drop_duplicates().set_index("region_id")["region_name"])
    if args.all:
        args.region = sorted(r for r in backtest["region_id"].unique() if r.isdigit())  # 합산 단위 제외
    frames = SignalFrames()
    ratios = paired_point_ratios(load_points())
    regions = region_monthly()

    (PROD / "regions").mkdir(parents=True, exist_ok=True)
    for region in args.region:
        payload = build_payload(region, names[region], frames, backtest, ratios, regions)
        if problems := validate_payload("signal_series", payload):
            sys.exit(f"{region} 스키마 검증 실패: {problems[:5]}")
        folder = PROD if region in SHOWCASE else PROD / "regions"
        path = folder / ("signal_series.json" if region == DEFAULT_REGION else f"signal_series_{region}.json")
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        if region not in SHOWCASE:
            continue
        d = payload["data"]
        eps = ", ".join(f"{e['metric']} {e['start']}~{e['end']}(확정 {e['confirm']}, 최고 {e['peak']})" for e in d["episodes"]) or "없음"
        tops = ", ".join(f"{a['name']} {a['max_ratio']}배" for a in d["points"]["attractions"][:3]) or "없음"
        print(f"{d['region']['name']}({region}) → {path.relative_to(ROOT)}  "
              f"[{path.stat().st_size / 1024:.0f}KB]\n  임계 초과 구간: {eps}\n"
              f"  백테스트 sMAPE {d['backtest']['smape']}% · 지점(~{d['as_of']['points']}): {tops}")


if __name__ == "__main__":
    main()
