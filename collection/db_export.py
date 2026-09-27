"""팀 MySQL(tour_earlywarning)에서 분석·에이전트 입력을 내려받아 data/raw/db/에 CSV로 저장한다.

DB를 매번 조회하지 않고 파일로 고정하는 이유: 데이터 담당이 적재를 계속 갱신 중이라
같은 명령이 다른 결과를 낼 수 있다. 에이전트 결과는 어떤 스냅샷으로 만들었는지 남아야 한다
(manifest.json에 추출 시각과 행 수를 기록한다).

접속 정보는 .env의 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD (조회 전용 계정).

사용법:
    uv run python collection/db_export.py
"""

import json
import os
import ssl
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymysql
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "db"

# 유튜브가 적재된 사례 지역. 일별 원자료는 이 지역만 받는다 (전 지역 일별은 240만 행)
CASE_REGIONS = ["48310", "12130", "47940", "51210", "51750", "51810"]

QUERIES = {
    "dim_region": "select region_id, region_name, sido_code, region_type, is_synthetic from dim_region",
    # 전 지역 일별 검색지수·외지인 방문자 — 신호 임계값을 사례 지역이 아니라 전국 분포에서 정하기 위한 것
    "daily_all": """
        select region_id, observed_date, metric, value
        from fact_signal
        where observed_date >= '2022-12-01'
          and (metric = 'interest_naver' or (metric = 'realization_visitors' and segment = 'external'))
    """,
    "daily_case": f"""
        select region_id, observed_date, metric, segment, value
        from fact_signal
        where region_id in ({','.join(repr(r) for r in CASE_REGIONS)}) and observed_date >= '2022-01-01'
    """,
    # description/tags는 2026-09-27부터 데이터 담당이 적재하기 시작했다 (그 전엔 컬럼
    # 자체가 없어 agent2_apply.py가 collection/youtube_collect.py로 직접 재수집해 우회했다 —
    # docs/j2nii_진행상황.md §23 참고). 거제(48310)는 여전히 비어 있다(적재 이전 스냅샷).
    "youtube_case": """
        select video_id, region_id, source_region_name, keyword_text, published_at, window_month,
               view_rank, title, channel_name, description, tags, view_count, like_count, comment_count
        from youtube_video
    """,
    "datalab_monthly_panel": "select * from datalab_monthly_panel",
    "source_file": "select source_file_id, file_name, row_count, loaded_at, note from source_file",
    # 관광지 단위 방문자 수 (에이전트 hotspots 입력). province/district 텍스트만 있어
    # attraction_region_map으로 canonical_region_id까지 조인해서 내려받는다 (전량은
    # 847,656행이라 사례 지역만 필터링).
    "major_attraction_visitors_monthly": f"""
        select m.canonical_region_id as region_id, a.attraction_name, a.visitor_type,
               a.observed_month, a.visitor_count
        from major_attraction_visitors_monthly a
        join attraction_region_map m
          on m.province_name = a.province_name and m.district_name = a.district_name
        where m.canonical_region_id in ({','.join(repr(r) for r in CASE_REGIONS)})
    """,
    # 방문객 프로파일(성연령/거리/거주지/소비/동반유형) 원자료 (에이전트 visitor_profile 입력).
    # data_group은 필요한 5개 범주만, 지역은 사례 지역만 필터링 (전량은 283만 행).
    "datalab_detail_row": """
        select row_key, source_region_code as region_id, source_region_name,
               observed_month, query_start_month, query_end_month, data_group,
               source_row_no, row_json
        from datalab_detail_row
        where data_group in (
            '방문자 성연령별 분포', '거리별 방문자 분포', '방문자 거주지 분포',
            '관광소비_내국인', '관광소비_외국인', '동반유형 키워드', '동반유형 언급량'
        )
        and source_region_code in ({regions})
    """.format(regions=",".join(repr(r) for r in CASE_REGIONS)),
}


def connect() -> pymysql.connections.Connection:
    load_dotenv(ROOT / ".env")
    missing = [k for k in ("DB_HOST", "DB_USER", "DB_PASSWORD") if not os.getenv(k)]
    if missing:
        sys.exit(f".env에 {', '.join(missing)}가 없다 (.env.example 참고)")
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "tour_earlywarning"),
        # 서버가 SSL을 요구한다 (Require). 인증서 검증은 서버가 자체 서명이라 끈다
        ssl={"check_hostname": False, "verify_mode": ssl.CERT_NONE},
        connect_timeout=15,
        read_timeout=600,
        charset="utf8mb4",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    manifest = {"exported_at": datetime.now().astimezone().replace(microsecond=0).isoformat(), "tables": {}}
    with conn.cursor() as cur:
        for name, sql in QUERIES.items():
            cur.execute(sql)
            columns = [c[0] for c in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=columns)
            path = OUT_DIR / f"{name}.csv"
            df.to_csv(path, index=False, encoding="utf-8")
            manifest["tables"][name] = {"rows": len(df), "file": path.name}
            print(f"{name:<24} {len(df):>9,}행 → {path.relative_to(ROOT)}")
    conn.close()
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
