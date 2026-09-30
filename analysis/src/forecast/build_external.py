"""외부·추가 수집 데이터를 예측 실험에 쓸 수 있는 형태로 내린다.

"검색 API나 추가 수집 데이터를 넣으면 성능이 오르는가"를 재려면 먼저
각 원천이 (1) 몇 개 지역을 덮는지 (2) 언제 공개되는지를 확정해야 한다.
여기서는 원자료만 내리고, 공개시점 지연 규칙은 ablation.py의 특징 생성에서 건다.
원자료에 미리 지연을 걸면 나중에 규칙을 바꿔 검증할 수 없기 때문이다.

출력 (data/interim/)
    datalab_monthly.csv   한국관광 데이터랩 월간 (228지역, 2020-01~2026-08)
    viral_keyword_daily.csv  바이럴 키워드 일별 (2지역만 — 사례용)
    evidence_daily.csv    뉴스·블로그 근거 발행일별 건수 (표본 편향 있음 — 검증용)
"""

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "collection"))
from db_export import connect  # noqa: E402

INTERIM = ROOT / "data" / "interim"

DATALAB_COLUMNS = [
    "visitors", "visitors_yoy_pct", "unique_visitors", "sns_mentions",
    "navigation_searches", "lodging_searches", "lodging_searches_yoy_pct",
    "tourism_spend_outsider_krw_thousand", "tourism_spend_domestic_krw_thousand",
    "avg_nights", "overnight_visit_pct", "stay_minutes",
]


def fetch(connection, sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, connection)


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    connection = connect()

    datalab = fetch(connection, f"""
        SELECT canonical_region_id AS region_id, period_start,
               {", ".join(DATALAB_COLUMNS)}
        FROM vw_datalab_canonical_monthly
        WHERE period_start >= '2021-01-01'
        ORDER BY canonical_region_id, period_start
    """)
    datalab.to_csv(INTERIM / "datalab_monthly.csv", index=False, encoding="utf-8")
    print(f"데이터랩 월간: {len(datalab):,}행 · {datalab['region_id'].nunique()}지역 · "
          f"{datalab['period_start'].min()}~{datalab['period_start'].max()}")
    filled = (datalab[DATALAB_COLUMNS].notna().mean() * 100).round(1)
    print("  컬럼별 채움률(%): " + ", ".join(f"{k} {v}" for k, v in filled.items()))

    viral = fetch(connection, """
        SELECT region_id, observed_date, keyword_group, ratio
        FROM viral_keyword_signal_daily ORDER BY region_id, observed_date
    """)
    viral.to_csv(INTERIM / "viral_keyword_daily.csv", index=False, encoding="utf-8")
    print(f"바이럴 키워드: {len(viral):,}행 · {viral['region_id'].nunique()}지역 "
          f"· 키워드군 {viral['keyword_group'].nunique()}개")

    evidence = fetch(connection, """
        SELECT region_id, published_date, search_type,
               COUNT(*) AS article_count,
               SUM(is_official_domain) AS official_count,
               COUNT(DISTINCT episode_no) AS episode_count
        FROM event_evidence_candidate
        WHERE published_date IS NOT NULL
        GROUP BY region_id, published_date, search_type
        ORDER BY region_id, published_date
    """)
    evidence.to_csv(INTERIM / "evidence_daily.csv", index=False, encoding="utf-8")
    timing = fetch(connection, """
        SELECT search_type, days_from_peak, COUNT(*) AS article_count,
               COUNT(DISTINCT region_id) AS regions
        FROM event_evidence_candidate
        WHERE published_date IS NOT NULL AND days_from_peak IS NOT NULL
        GROUP BY search_type, days_from_peak
        ORDER BY search_type, days_from_peak
    """)
    timing.to_csv(INTERIM / "evidence_timing.csv", index=False, encoding="utf-8")
    after = timing.loc[timing["days_from_peak"] > 0, "article_count"].sum()
    total = timing["article_count"].sum()
    print(f"근거 기사 발행 시점: 피크 이후 {after:,}건 / 전체 {total:,}건 ({after / total * 100:.1f}%)")

    print(f"근거 기사(발행일별): {len(evidence):,}행 · {evidence['region_id'].nunique()}지역 "
          f"· 수집 대상 에피소드 {evidence['episode_count'].max()}개 이하")
    connection.close()


if __name__ == "__main__":
    main()
