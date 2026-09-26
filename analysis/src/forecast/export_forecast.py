"""검증된 h=7 모델로 지역별 forecast JSON을 만든다 — data/prod/forecast[_지역코드].json.

무엇을 내보내는가 (docs/meeting-notes/인계_forecast실측화_0926.md)
    - 모델: ablation.py의 LAG+CAL+FES+NAV+DLB (테스트 sMAPE 8.98%, MAE 7,603명). 같은 분할·같은 씨앗으로
      다시 학습하고, 테스트 성능이 재현되는지 확인한 뒤에만 내보낸다
    - 예측 대상: 패널 마지막 날(데이터 기준일) 다음 7일. 검증한 것이 h=7뿐이라 7일만 낸다 (90일 금지)
    - 구간: 그 지역의 테스트 기간 '실제/예측' 비율의 10·90분위 → 80% 구간. 표본이 모자라면 전국 분위수
    - 일별 경보 단계는 넣지 않는다. 경보는 월별 3신호 판정(D-13)이라 일별 임계가 없다

미래 7일의 달력·축제는 DB(analysis_calendar, event)에서 가져온다. analysis_calendar는 2026년 7월 이후
공휴일이 비어 있어(광복절이 평일로 적혀 있다) 천문연 월력요항으로 확인한 공휴일을 HOLIDAY_PATCH로 보탠다.

사용법:
    uv run python analysis/src/forecast/export_forecast.py                       # 거제·영월
    uv run python analysis/src/forecast/export_forecast.py --region 51750
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
sys.path.insert(0, str(ROOT / "collection"))
sys.path.insert(0, str(ROOT / "scripts"))

from ablation import datalab_features, fit_predict  # noqa: E402
from baseline import SPLITS, TARGET, build_features, smape  # noqa: E402
from build_panel import FESTIVAL_SQL, festival_flags, read_sql  # noqa: E402
from db_export import connect  # noqa: E402
from validate_data import validate_payload  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PROD = ROOT / "data" / "prod"

HORIZON = 7
SEEDS = 3
DEFAULT_REGION = "48310"  # 거제는 파일명 접미사 없이 forecast.json (agents/common.load_input 규칙)
VALIDATED = {"smape": 8.979, "mae": 7603.0}  # data/interim/ablation_h7.json의 LAG+CAL+FES+NAV+DLB (09-24 패널)
# DB 적재가 이어져 패널을 다시 만들면 변수가 조금 달라진다(09-26 재생성: sMAPE 8.966, MAE 7,575).
# 이 정도는 같은 모델로 보고, 화면에는 지금 예측을 만든 모델의 테스트 성능을 싣는다
TOLERANCE = {"smape": 0.05, "mae": 50}
INTERVAL = (0.10, 0.90)
MIN_INTERVAL_SAMPLES = 60
WEEKDAY = "월화수목금토일"

# analysis_calendar에 빠진 공휴일 (한국천문연구원 2026년 월력요항)
HOLIDAY_PATCH = {
    "2026-08-15": "광복절",
    "2026-08-17": "광복절 대체공휴일",
}


def future_rows(panel: pd.DataFrame, conn) -> tuple[pd.DataFrame, pd.DataFrame]:
    """패널 마지막 날 다음 HORIZON일의 빈 행(달력·축제만 채움)과 축제 목록을 만든다."""
    last = panel["observed_date"].max()
    start, end = last + pd.Timedelta(days=1), last + pd.Timedelta(days=HORIZON)
    calendar = read_sql(conn, f"""
        select calendar_date as observed_date, calendar_year, calendar_month, day_of_week,
               is_weekend, is_public_holiday, holiday_name
        from analysis_calendar where calendar_date between '{start.date()}' and '{end.date()}'""")
    if len(calendar) != HORIZON:
        sys.exit(f"analysis_calendar에 {start.date()}~{end.date()}가 {len(calendar)}일만 있다")
    calendar["observed_date"] = pd.to_datetime(calendar["observed_date"])
    patch = calendar["observed_date"].dt.strftime("%Y-%m-%d").map(HOLIDAY_PATCH)
    calendar.loc[patch.notna(), "holiday_name"] = patch[patch.notna()]
    calendar.loc[patch.notna(), "is_public_holiday"] = 1

    regions = panel[["region_id", "region_name"]].drop_duplicates()
    future = regions.merge(calendar, how="cross")
    festivals = read_sql(conn, FESTIVAL_SQL)
    for column in ("start_date", "end_date"):
        festivals[column] = pd.to_datetime(festivals[column])
    future = festival_flags(festivals, future)
    return future, festivals


def rest_run_length(frame: pd.DataFrame) -> pd.Series:
    """build_panel.py와 같은 정의 — 주말·공휴일이 이어지는 날 수 (평일은 0)."""
    one = frame.drop_duplicates("observed_date").sort_values("observed_date").set_index("observed_date")
    rest = (one["is_weekend"].astype(int) | one["is_public_holiday"].astype(int))
    block = (rest != rest.shift()).cumsum()
    run = rest.groupby(block).transform("size").where(rest == 1, 0)
    return frame["observed_date"].map(run).fillna(0).astype(int)


def interval_ratios(test: pd.DataFrame) -> tuple[pd.DataFrame, tuple[float, float]]:
    ratio = (test[TARGET] / test["pred"]).replace([np.inf, -np.inf], np.nan)
    frame = test.assign(ratio=ratio).dropna(subset=["ratio"])
    national = tuple(float(q) for q in frame["ratio"].quantile(INTERVAL))
    per_region = frame.groupby("region_id")["ratio"].agg(
        n="size", q_low=lambda s: s.quantile(INTERVAL[0]), q_high=lambda s: s.quantile(INTERVAL[1]))
    return per_region, national


def festival_names(festivals: pd.DataFrame, region: str, day: pd.Timestamp) -> tuple[list[str], list[str]]:
    """그날 진행 중인 축제, 7일 안에 시작하는 축제."""
    own = festivals[(festivals["region_id"] == region) & festivals["start_date"].notna() & festivals["end_date"].notna()]
    active = own[(own["start_date"] <= day) & (own["end_date"] >= day)]["event_name"].tolist()
    soon = own[(own["start_date"] > day) & (own["start_date"] <= day + pd.Timedelta(days=7))]
    upcoming = [f"{r.event_name}({r.start_date.month}/{r.start_date.day} 시작)" for r in soon.itertuples()]
    return active, upcoming


def build_payload(region: str, rows: pd.DataFrame, test: pd.DataFrame, history: pd.DataFrame,
                  intervals: pd.DataFrame, national: tuple[float, float], festivals: pd.DataFrame,
                  retrieved: str, data_end: pd.Timestamp, got: dict) -> dict:
    name = rows["region_name"].iloc[0]
    reg_test = test[test["region_id"] == region]
    reg_smape = smape(reg_test[TARGET].to_numpy(), reg_test["pred"].to_numpy())
    reg_mae = float(np.mean(np.abs(reg_test[TARGET] - reg_test["pred"])))
    if region in intervals.index and intervals.loc[region, "n"] >= MIN_INTERVAL_SAMPLES:
        q_low, q_high = intervals.loc[region, ["q_low", "q_high"]]
        interval_note = f"80% 구간은 {name} 테스트 기간 {int(intervals.loc[region, 'n'])}일의 실제/예측 비율 10·90분위다."
    else:
        q_low, q_high = national
        interval_note = f"{name}의 테스트 표본이 {MIN_INTERVAL_SAMPLES}일 미만이라 80% 구간은 전국 실제/예측 비율 분위수로 대신했다."

    daily, peaks = [], []
    for r in rows.sort_values("observed_date").itertuples():
        pred = float(r.pred)
        entry = {"date": r.observed_date.strftime("%Y-%m-%d"), "predicted": int(round(pred)),
                 "lower": int(round(pred * q_low)), "upper": int(round(pred * q_high)),
                 "is_holiday": bool(r.is_public_holiday)}
        active, upcoming = festival_names(festivals, region, r.observed_date)
        if active:
            entry["event"] = "·".join(active)
        daily.append(entry)
        reason = [f"{WEEKDAY[r.observed_date.weekday()]}요일"]
        if r.is_public_holiday:
            reason.append(r.holiday_name)
        if r.rest_run_length >= 3:
            reason.append(f"{int(r.rest_run_length)}일 연휴")
        reason += [f"{a} 기간" for a in active] + [f"{u} 직전" for u in upcoming]
        peaks.append({"date": entry["date"], "predicted": entry["predicted"], "reason": " · ".join(reason)})
    peak_days = sorted(peaks, key=lambda p: -p["predicted"])[:2]

    # 요일별 집중률: 데이터 기준일 직전 1년 실측
    recent = history[(history["region_id"] == region)
                     & (history["observed_date"] > data_end - pd.Timedelta(days=365))]
    share = recent.groupby(recent["observed_date"].dt.weekday)[TARGET].sum()
    share = (share / share.sum()).round(4)
    share.iloc[-1] = round(1 - share.iloc[:-1].sum(), 4)  # 반올림 오차를 일요일에 몰아 합을 1로
    weekday_concentration = [{"weekday": WEEKDAY[i], "ratio": float(share.loc[i])} for i in range(7)]

    start, end = daily[0]["date"], daily[-1]["date"]
    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {"name": "이동통신 기반 시군구 일별 방문자", "provider": "한국관광공사(공공데이터포털 15101972)",
             "retrieved_at": retrieved, "url": "https://www.data.go.kr/data/15101972/openapi.do",
             "note": "외지인 방문자수. 팀 DB vw_daily_core_signal"},
            {"name": "한국관광 데이터랩 월간 지표", "provider": "한국관광공사", "retrieved_at": retrieved,
             "url": "https://datalab.visitkorea.or.kr/", "note": "익월 17일 공개 시점을 지켜 결합"},
            {"name": "네이버 데이터랩 검색어 트렌드", "provider": "네이버", "retrieved_at": retrieved,
             "note": "전일까지의 검색지수만 사용"},
            {"name": "전국문화축제표준데이터·특일 정보", "provider": "행정안전부·한국천문연구원",
             "retrieved_at": retrieved, "note": "예측 대상일의 축제·공휴일"},
        ],
        "period": {"start": start, "end": end, "granularity": "일"},
        "caveat": [
            f"데이터 기준일 {data_end.date()} 기준 7일 앞 예측이다. 오늘부터의 7일이 아니다.",
            f"검증 sMAPE {got['smape']:.2f}%(MAE {got['mae']:,.0f}명), 228개 시군구 공통 모델, "
            f"테스트 {SPLITS['test'][0]}~{SPLITS['test'][1]} {len(test):,}건. "
            f"{name}만 보면 sMAPE {reg_smape:.2f}%, MAE {reg_mae:,.0f}명이다. "
            f"(09-24 동결 수치 sMAPE {VALIDATED['smape']:.2f}%·MAE {VALIDATED['mae']:,.0f}명과 같은 구성이며, "
            "이후 DB 갱신으로 입력이 조금 달라진 차이다.)",
            "7일 앞(h=7)만 검증했으므로 그보다 먼 날은 제공하지 않는다.",
            interval_note + " 구간을 벗어나는 날이 5일 중 1일꼴로 생긴다.",
            "일별 경보 단계는 제공하지 않는다. 경보는 월별 3신호 판정(D-13)이라 일별 임계가 없다.",
        ],
        "data": {
            "region": {"code": region, "name": name},
            "model": {
                "name": "부스팅 회귀(HistGradientBoosting) — 방문자 시차 + 달력 + 축제 + 검색 + 데이터랩 월간",
                "trained_on": {"start": SPLITS["train"][0], "end": SPLITS["valid"][1], "granularity": "일"},
                "metric": {"name": "MAE", "value": round(got["mae"]),
                           "validation_period": {"start": SPLITS["test"][0], "end": SPLITS["test"][1], "granularity": "일"}},
                "features": ["방문자 시차(4일 지연 공개 반영)", "요일·공휴일·연휴길이", "축제 전후",
                             "네이버 검색지수(전일까지)", "데이터랩 월간(익월 17일 공개 반영)"],
            },
            "daily": daily,
            "weekday_concentration": weekday_concentration,
            "peak_days": peak_days,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", nargs="+", default=["48310", "51750"], help="지역 코드 (기본 거제·영월)")
    args = parser.parse_args()

    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    missing = set(args.region) - set(panel["region_id"])
    if missing:
        sys.exit(f"패널에 없는 지역: {sorted(missing)}")
    data_end = panel["observed_date"].max()
    retrieved = json.loads((INTERIM / "panel_quality.json").read_text(encoding="utf-8"))["built_at"][:10]

    conn = connect()
    future, festivals = future_rows(panel, conn)
    conn.close()
    combined = pd.concat([panel, future], ignore_index=True).sort_values(["region_id", "observed_date"])
    combined = combined.reset_index(drop=True)
    combined["rest_run_length"] = rest_run_length(combined)

    data = pd.concat([build_features(combined, HORIZON), datalab_features(combined, HORIZON)], axis=1)
    data = data.merge(combined[["region_id", "observed_date", "holiday_name"]],
                      on=["region_id", "observed_date"], how="left")
    lag = [c for c in data.columns if c.startswith("vis_")]
    columns = (lag + ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday", "rest_run_length",
                      "festival_active", "festival_pre", "festival_post",
                      "naver_last", "naver_mean7", "naver_mean28", "naver_ratio_7_28", "naver_jump", "naver_year_ratio"]
               + [c for c in data.columns if c.startswith("dlb_")])

    def between(start, end):
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)]

    fit = between(SPLITS["train"][0], SPLITS["valid"][1]).dropna(subset=lag + [TARGET])
    test = between(*SPLITS["test"])
    test = test[test[lag].notna().all(axis=1)].copy()
    target = data[data["observed_date"] > data_end]
    target = target[target["region_id"].isin(args.region)].copy()
    if target[lag].isna().any().any():
        sys.exit("예측 대상일의 방문자 시차 변수에 결측이 있다")

    both = pd.concat([test, target])
    both["pred"] = np.mean([fit_predict(fit, both, columns, seed) for seed in range(SEEDS)], axis=0)
    test, target = both.iloc[:len(test)].copy(), both.iloc[len(test):].copy()

    got = {"smape": smape(test[TARGET].to_numpy(), test["pred"].to_numpy()),
           "mae": float(np.mean(np.abs(test[TARGET] - test["pred"])))}
    print(f"테스트 재현: sMAPE {got['smape']:.3f}% (기록 {VALIDATED['smape']}), MAE {got['mae']:,.1f} (기록 {VALIDATED['mae']:,.1f})")
    if abs(got["smape"] - VALIDATED["smape"]) > TOLERANCE["smape"] or abs(got["mae"] - VALIDATED["mae"]) > TOLERANCE["mae"]:
        sys.exit("검증 성능이 재현되지 않는다 — 패널이나 코드가 ablation 실행 때와 다르다. 내보내지 않는다")

    intervals, national = interval_ratios(test)
    PROD.mkdir(parents=True, exist_ok=True)
    for region in args.region:
        payload = build_payload(region, target[target["region_id"] == region], test, panel,
                                intervals, national, festivals, retrieved, data_end, got)
        if problems := validate_payload("forecast", payload):
            sys.exit(f"{region} 스키마 검증 실패: {problems[:5]}")
        path = PROD / ("forecast.json" if region == DEFAULT_REGION else f"forecast_{region}.json")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        d = payload["data"]
        print(f"\n{d['region']['name']}({region}) → {path.relative_to(ROOT)}")
        for day in d["daily"]:
            print(f"  {day['date']}  {day['predicted']:>7,}  [{day['lower']:>7,} ~ {day['upper']:>7,}]"
                  f"{'  공휴일' if day['is_holiday'] else ''}{'  ' + day['event'] if 'event' in day else ''}")
        print("  피크: " + ", ".join(f"{p['date']} ({p['reason']})" for p in d["peak_days"]))
        print(f"  {payload['caveat'][1]}")


if __name__ == "__main__":
    main()
