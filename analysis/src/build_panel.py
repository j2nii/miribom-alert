"""분석 패널 생성 — 일별 신호 + 달력 + 날씨 + 축제를 한 장의 표로 만든다.

이 패널이 예측 모델의 유일한 입력이다. 여기 들어가는 변수는 모두 "예측 시점에 알 수 있는 것"만이며,
판단 근거는 docs/분석_누출점검표.md에 있다.

출처
- vw_daily_core_signal : 지역·날짜별 네이버 검색지수와 방문자수 (228지역, 2023-01-01~2026-08-14)
- raw_kma_asos_daily + region_asos_station_map : 관측소 날씨를 지역에 매핑 (149/228 지역)
- event + event_point : 문화축제 표준데이터 2,562건의 시작일(T0)·종료일(end)

주의
- 강수량 NULL은 결측이 아니라 '비가 오지 않음'이다 (ASOS 표기 관행) → 0으로 채우고 채운 표시를 남긴다
- 날씨가 없는 79개 지역은 버리지 않는다. weather_available 플래그로 구분해 모델에서 따로 본다

사용법:
    uv run python analysis/src/build_panel.py
출력:
    data/interim/panel_daily.csv          분석 패널
    data/interim/panel_quality.json       품질 점검 결과
    data/interim/weather_unmapped.csv     날씨 미매핑 지역 목록
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "collection"))

from db_export import connect  # noqa: E402

OUT_DIR = ROOT / "data" / "interim"
RAW_DIR = ROOT / "data" / "raw" / "db"
FESTIVAL_WINDOW = 7  # 축제 전후 며칠까지 영향으로 볼 것인가

CORE_SQL = """
    select region_id, region_name, observed_date, calendar_year, calendar_month,
           day_of_week, is_weekend, is_public_holiday, holiday_name,
           naver_interest, visitors_external, visitors_local, visitors_foreign
    from vw_daily_core_signal
"""

WEATHER_SQL = """
    select m.region_id, a.observed_date,
           a.avg_temperature_c, a.min_temperature_c, a.max_temperature_c,
           a.precipitation_mm, a.max_wind_speed_ms, a.avg_humidity_pct, a.snow_depth_cm
    from region_asos_station_map m
    join raw_kma_asos_daily a on a.station_id = m.station_id
"""

FESTIVAL_SQL = """
    select e.event_id, e.region_id, e.event_name,
           max(case when p.point_type = 'T0' then p.point_date end)  as start_date,
           max(case when p.point_type = 'end' then p.point_date end) as end_date
    from event e
    join event_point p on p.event_id = e.event_id
    where e.event_type = 'festival'
    group by e.event_id, e.region_id, e.event_name
"""


def read_sql(conn, sql: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql)
        return pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])


def festival_flags(festivals: pd.DataFrame, panel_keys: pd.DataFrame) -> pd.DataFrame:
    """축제 기간을 일별 플래그로 편다. 한 날짜에 축제가 여럿이면 건수로 센다."""
    rows = []
    for row in festivals.itertuples():
        if pd.isna(row.start_date) or pd.isna(row.end_date) or row.end_date < row.start_date:
            continue
        span = pd.date_range(row.start_date, row.end_date, freq="D")
        pre = pd.date_range(row.start_date - pd.Timedelta(days=FESTIVAL_WINDOW), row.start_date - pd.Timedelta(days=1))
        post = pd.date_range(row.end_date + pd.Timedelta(days=1), row.end_date + pd.Timedelta(days=FESTIVAL_WINDOW))
        for dates, column in ((span, "festival_active"), (pre, "festival_pre"), (post, "festival_post")):
            rows.append(pd.DataFrame({"region_id": row.region_id, "observed_date": dates, column: 1}))
    if not rows:
        return panel_keys.assign(festival_active=0, festival_pre=0, festival_post=0)

    flags = pd.concat(rows, ignore_index=True).fillna(0)
    flags = flags.groupby(["region_id", "observed_date"], as_index=False).sum(numeric_only=True)
    merged = panel_keys.merge(flags, on=["region_id", "observed_date"], how="left")
    for column in ("festival_active", "festival_pre", "festival_post"):
        merged[column] = merged.get(column, 0).fillna(0).astype(int)
    return merged


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    print("DB 조회 중...")
    core = read_sql(conn, CORE_SQL)
    weather = read_sql(conn, WEATHER_SQL)
    festivals = read_sql(conn, FESTIVAL_SQL)
    regions = read_sql(conn, "select region_id, region_name, sido_code, region_type from dim_region")
    conn.close()

    core["observed_date"] = pd.to_datetime(core["observed_date"])
    weather["observed_date"] = pd.to_datetime(weather["observed_date"])
    for column in ("start_date", "end_date"):
        festivals[column] = pd.to_datetime(festivals[column])
    numeric = ["naver_interest", "visitors_external", "visitors_local", "visitors_foreign"]
    core[numeric] = core[numeric].astype(float)
    core.to_csv(RAW_DIR / "core_signal.csv", index=False, encoding="utf-8")

    # 날씨: 강수량 NULL은 '비 안 옴'이라 0으로 채우되 채운 사실을 남긴다
    weather_numeric = ["avg_temperature_c", "min_temperature_c", "max_temperature_c",
                       "precipitation_mm", "max_wind_speed_ms", "avg_humidity_pct", "snow_depth_cm"]
    weather[weather_numeric] = weather[weather_numeric].astype(float)
    weather["precip_was_null"] = weather["precipitation_mm"].isna().astype(int)
    weather["precipitation_mm"] = weather["precipitation_mm"].fillna(0.0)
    weather["snow_depth_cm"] = weather["snow_depth_cm"].fillna(0.0)

    panel = core.merge(weather, on=["region_id", "observed_date"], how="left")
    panel["weather_available"] = panel["avg_temperature_c"].notna().astype(int)
    panel = festival_flags(festivals, panel)

    # 달력 파생: 연휴 길이(공휴일·주말이 이어지는 날 수)
    panel = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True)
    rest = (panel["is_weekend"].astype(int) | panel["is_public_holiday"].astype(int)).astype(int)
    calendar = panel[["region_id", "observed_date"]].assign(is_rest=rest)
    one_region = calendar[calendar["region_id"] == calendar["region_id"].iloc[0]].set_index("observed_date")["is_rest"]
    block = (one_region != one_region.shift()).cumsum()
    run_length = one_region.groupby(block).transform("size").where(one_region == 1, 0)
    panel["rest_run_length"] = panel["observed_date"].map(run_length).fillna(0).astype(int)

    mapped_regions = sorted(set(weather["region_id"]))
    unmapped = regions[~regions["region_id"].isin(mapped_regions)][["region_id", "region_name"]]
    unmapped.to_csv(OUT_DIR / "weather_unmapped.csv", index=False, encoding="utf-8-sig")

    quality = {
        "built_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "rows": int(len(panel)),
        "regions": int(panel["region_id"].nunique()),
        "date_min": str(panel["observed_date"].min().date()),
        "date_max": str(panel["observed_date"].max().date()),
        "duplicate_region_date": int(panel.duplicated(["region_id", "observed_date"]).sum()),
        "expected_rows": int(panel["region_id"].nunique() * panel["observed_date"].nunique()),
        "weather_mapped_regions": len(mapped_regions),
        "weather_unmapped_regions": int(len(unmapped)),
        "weather_rows_available_pct": round(100 * panel["weather_available"].mean(), 1),
        "precip_filled_zero_pct": round(100 * panel["precip_was_null"].fillna(0).mean(), 1),
        "festival_active_days": int((panel["festival_active"] > 0).sum()),
        "festival_regions": int(festivals["region_id"].nunique()),
        "nulls": {c: int(panel[c].isna().sum()) for c in numeric},
    }
    (OUT_DIR / "panel_quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    panel.to_csv(OUT_DIR / "panel_daily.csv", index=False, encoding="utf-8")

    print(f"\n패널: {quality['rows']:,}행 · {quality['regions']}지역 · {quality['date_min']}~{quality['date_max']}")
    print(f"지역×날짜 중복: {quality['duplicate_region_date']}건 (기대 행 수 {quality['expected_rows']:,})")
    print(f"핵심 지표 결측: {quality['nulls']}")
    print(f"날씨: {quality['weather_mapped_regions']}/{quality['weather_mapped_regions'] + quality['weather_unmapped_regions']}개 지역 매핑, "
          f"행 기준 {quality['weather_rows_available_pct']}% · 강수 0으로 채운 비율 {quality['precip_filled_zero_pct']}%")
    print(f"축제: {quality['festival_regions']}개 지역, 축제 진행일 {quality['festival_active_days']:,}행")
    print(f"\n출력: {(OUT_DIR / 'panel_daily.csv').relative_to(ROOT)}, panel_quality.json, weather_unmapped.csv")


if __name__ == "__main__":
    main()
