SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS datalab_sns_companion_monthly_canonical (
  canonical_region_id VARCHAR(20) NOT NULL,
  period_start DATE NOT NULL,
  companion_type VARCHAR(200) NOT NULL,
  mention_count DECIMAL(30,8) NULL,
  source_region_count INT UNSIGNED NOT NULL,
  PRIMARY KEY (canonical_region_id, period_start, companion_type),
  KEY ix_companion_period (period_start),
  CONSTRAINT fk_companion_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

TRUNCATE TABLE datalab_sns_companion_monthly_canonical;

INSERT INTO datalab_sns_companion_monthly_canonical
  (canonical_region_id, period_start, companion_type,
   mention_count, source_region_count)
WITH extracted AS (
  SELECT
    d.row_key,
    d.source_region_code,
    COALESCE(d.source_region_name, '') AS source_region_name,
    d.observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."동반유형명"')) AS category_name,
    CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."언급건수"')), '')
      AS DECIMAL(30,8)) AS metric_value,
    d.source_id,
    d.loaded_at
  FROM datalab_detail_row AS d
  WHERE d.data_group = '동반유형 언급량'
    AND d.observed_month IS NOT NULL
), ranked AS (
  SELECT e.*,
         ROW_NUMBER() OVER (
           PARTITION BY source_region_code, source_region_name,
                        observed_month, category_name
           ORDER BY loaded_at DESC, source_id DESC, row_key DESC
         ) AS rn
  FROM extracted AS e
  WHERE category_name IS NOT NULL
)
SELECT
  m.canonical_region_id,
  r.observed_month,
  r.category_name,
  SUM(r.metric_value),
  COUNT(DISTINCT CONCAT(r.source_region_code, '|', r.source_region_name))
FROM ranked AS r
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = r.source_region_code
 AND m.source_region_name = r.source_region_name
WHERE r.rn = 1
  AND (m.valid_from IS NULL OR r.observed_month >= m.valid_from)
  AND (m.valid_to IS NULL OR r.observed_month <= m.valid_to)
GROUP BY m.canonical_region_id, r.observed_month, r.category_name;

CREATE TABLE IF NOT EXISTS datalab_sns_travel_monthly_canonical (
  canonical_region_id VARCHAR(20) NOT NULL,
  period_start DATE NOT NULL,
  travel_type VARCHAR(200) NOT NULL,
  mention_count DECIMAL(30,8) NULL,
  source_region_count INT UNSIGNED NOT NULL,
  PRIMARY KEY (canonical_region_id, period_start, travel_type),
  KEY ix_travel_period (period_start),
  CONSTRAINT fk_travel_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

TRUNCATE TABLE datalab_sns_travel_monthly_canonical;

INSERT INTO datalab_sns_travel_monthly_canonical
  (canonical_region_id, period_start, travel_type,
   mention_count, source_region_count)
WITH extracted AS (
  SELECT
    d.row_key,
    d.source_region_code,
    COALESCE(d.source_region_name, '') AS source_region_name,
    d.observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."여행유형/트렌드명"')) AS category_name,
    CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."언급건수"')), '')
      AS DECIMAL(30,8)) AS metric_value,
    d.source_id,
    d.loaded_at
  FROM datalab_detail_row AS d
  WHERE d.data_group = '여행유형_트렌드 언급량'
    AND d.observed_month IS NOT NULL
), ranked AS (
  SELECT e.*,
         ROW_NUMBER() OVER (
           PARTITION BY source_region_code, source_region_name,
                        observed_month, category_name
           ORDER BY loaded_at DESC, source_id DESC, row_key DESC
         ) AS rn
  FROM extracted AS e
  WHERE category_name IS NOT NULL
)
SELECT
  m.canonical_region_id,
  r.observed_month,
  r.category_name,
  SUM(r.metric_value),
  COUNT(DISTINCT CONCAT(r.source_region_code, '|', r.source_region_name))
FROM ranked AS r
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = r.source_region_code
 AND m.source_region_name = r.source_region_name
WHERE r.rn = 1
  AND (m.valid_from IS NULL OR r.observed_month >= m.valid_from)
  AND (m.valid_to IS NULL OR r.observed_month <= m.valid_to)
GROUP BY m.canonical_region_id, r.observed_month, r.category_name;

CREATE TABLE IF NOT EXISTS datalab_navigation_destination_monthly_canonical (
  canonical_region_id VARCHAR(20) NOT NULL,
  period_start DATE NOT NULL,
  destination_type VARCHAR(200) NOT NULL,
  search_count DECIMAL(30,8) NULL,
  source_region_count INT UNSIGNED NOT NULL,
  PRIMARY KEY (canonical_region_id, period_start, destination_type),
  KEY ix_navigation_period (period_start),
  CONSTRAINT fk_navigation_detail_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

TRUNCATE TABLE datalab_navigation_destination_monthly_canonical;

INSERT INTO datalab_navigation_destination_monthly_canonical
  (canonical_region_id, period_start, destination_type,
   search_count, source_region_count)
WITH extracted AS (
  SELECT
    d.row_key,
    d.source_region_code,
    COALESCE(d.source_region_name, '') AS source_region_name,
    d.observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."목적지 유형"')) AS category_name,
    CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."목적지 검색량"')), '')
      AS DECIMAL(30,8)) AS metric_value,
    d.source_id,
    d.loaded_at
  FROM datalab_detail_row AS d
  WHERE d.data_group = '내비게이션 목적지 유형별 검색량'
    AND d.observed_month IS NOT NULL
), ranked AS (
  SELECT e.*,
         ROW_NUMBER() OVER (
           PARTITION BY source_region_code, source_region_name,
                        observed_month, category_name
           ORDER BY loaded_at DESC, source_id DESC, row_key DESC
         ) AS rn
  FROM extracted AS e
  WHERE category_name IS NOT NULL
)
SELECT
  m.canonical_region_id,
  r.observed_month,
  r.category_name,
  SUM(r.metric_value),
  COUNT(DISTINCT CONCAT(r.source_region_code, '|', r.source_region_name))
FROM ranked AS r
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = r.source_region_code
 AND m.source_region_name = r.source_region_name
WHERE r.rn = 1
  AND (m.valid_from IS NULL OR r.observed_month >= m.valid_from)
  AND (m.valid_to IS NULL OR r.observed_month <= m.valid_to)
GROUP BY m.canonical_region_id, r.observed_month, r.category_name;

CREATE TABLE IF NOT EXISTS datalab_spend_industry_monthly_canonical (
  canonical_region_id VARCHAR(20) NOT NULL,
  period_start DATE NOT NULL,
  visitor_segment VARCHAR(20) NOT NULL,
  industry_major VARCHAR(200) NOT NULL,
  spend_krw_thousand DECIMAL(30,8) NULL,
  source_region_count INT UNSIGNED NOT NULL,
  PRIMARY KEY (canonical_region_id, period_start, visitor_segment, industry_major),
  KEY ix_spend_detail_period (period_start),
  CONSTRAINT fk_spend_detail_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

TRUNCATE TABLE datalab_spend_industry_monthly_canonical;

INSERT INTO datalab_spend_industry_monthly_canonical
  (canonical_region_id, period_start, visitor_segment, industry_major,
   spend_krw_thousand, source_region_count)
WITH extracted AS (
  SELECT
    d.row_key,
    d.source_region_code,
    COALESCE(d.source_region_name, '') AS source_region_name,
    d.observed_month,
    CASE
      WHEN d.data_group = '관광소비 추이_내국인' THEN 'domestic'
      WHEN d.data_group = '관광소비 추이_현지인' THEN 'local'
      WHEN d.data_group = '관광소비 추이_외지인' THEN 'outsider'
    END AS visitor_segment,
    JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."업종대분류명"')) AS category_name,
    CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."소비액(천원)"')), '')
      AS DECIMAL(30,8)) AS metric_value,
    d.source_id,
    d.loaded_at
  FROM datalab_detail_row AS d
  WHERE d.data_group IN (
    '관광소비 추이_내국인', '관광소비 추이_현지인', '관광소비 추이_외지인'
  )
    AND d.observed_month IS NOT NULL
), ranked AS (
  SELECT e.*,
         ROW_NUMBER() OVER (
           PARTITION BY source_region_code, source_region_name,
                        observed_month, visitor_segment, category_name
           ORDER BY loaded_at DESC, source_id DESC, row_key DESC
         ) AS rn
  FROM extracted AS e
  WHERE category_name IS NOT NULL
)
SELECT
  m.canonical_region_id,
  r.observed_month,
  r.visitor_segment,
  r.category_name,
  SUM(r.metric_value),
  COUNT(DISTINCT CONCAT(r.source_region_code, '|', r.source_region_name))
FROM ranked AS r
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = r.source_region_code
 AND m.source_region_name = r.source_region_name
WHERE r.rn = 1
  AND (m.valid_from IS NULL OR r.observed_month >= m.valid_from)
  AND (m.valid_to IS NULL OR r.observed_month <= m.valid_to)
GROUP BY m.canonical_region_id, r.observed_month,
         r.visitor_segment, r.category_name;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_keyword_canonical AS
SELECT
  m.canonical_region_id,
  r.region_name AS canonical_region_name,
  d.query_start_month,
  d.query_end_month,
  d.data_group,
  CAST(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."순위"')) AS UNSIGNED) AS ranking,
  JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."분류"')) AS category_name,
  JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."관련 키워드"')) AS keyword,
  CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(d.row_json, '$."언급건수"')), '')
    AS DECIMAL(30,8)) AS mention_count,
  d.source_region_code,
  d.source_region_name
FROM datalab_detail_row AS d
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = d.source_region_code
 AND m.source_region_name = COALESCE(d.source_region_name, '')
JOIN dim_region AS r
  ON r.region_id = m.canonical_region_id
WHERE d.data_group IN ('동반유형 키워드', '여행유형_트렌드 키워드')
  AND (m.valid_from IS NULL OR d.query_end_month >= m.valid_from)
  AND (m.valid_to IS NULL OR d.query_start_month <= m.valid_to);

CREATE TABLE IF NOT EXISTS attraction_visitors_monthly_canonical (
  canonical_region_id VARCHAR(20) NOT NULL,
  period_start DATE NOT NULL,
  attraction_count INT UNSIGNED NOT NULL,
  total_visitors BIGINT NULL,
  top_attraction_name VARCHAR(500) NULL,
  top_attraction_visitors BIGINT NULL,
  source_district_count INT UNSIGNED NOT NULL,
  PRIMARY KEY (canonical_region_id, period_start),
  KEY ix_attraction_canonical_period (period_start),
  CONSTRAINT fk_attraction_canonical_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

TRUNCATE TABLE attraction_visitors_monthly_canonical;

INSERT INTO attraction_visitors_monthly_canonical
  (canonical_region_id, period_start, attraction_count, total_visitors,
   top_attraction_name, top_attraction_visitors, source_district_count)
WITH by_attraction AS (
  SELECT
    m.canonical_region_id,
    a.observed_month,
    a.attraction_name,
    SUM(a.visitor_count) AS visitors
  FROM major_attraction_visitors_monthly AS a
  JOIN attraction_region_map AS m
    ON m.province_name = a.province_name
   AND m.district_name = a.district_name
  WHERE a.visitor_type = '합계'
  GROUP BY m.canonical_region_id, a.observed_month, a.attraction_name
), ranked AS (
  SELECT b.*,
         ROW_NUMBER() OVER (
           PARTITION BY canonical_region_id, observed_month
           ORDER BY visitors DESC, attraction_name
         ) AS attraction_rank
  FROM by_attraction AS b
), district_summary AS (
  SELECT
    m.canonical_region_id,
    a.observed_month,
    COUNT(DISTINCT CONCAT(a.province_name, '|', a.district_name))
      AS source_district_count
  FROM major_attraction_visitors_monthly AS a
  JOIN attraction_region_map AS m
    ON m.province_name = a.province_name
   AND m.district_name = a.district_name
  WHERE a.visitor_type = '합계'
  GROUP BY m.canonical_region_id, a.observed_month
), summary AS (
  SELECT
    canonical_region_id,
    observed_month,
    COUNT(*) AS attraction_count,
    SUM(visitors) AS total_visitors,
    MAX(CASE WHEN attraction_rank = 1 THEN attraction_name END) AS top_attraction_name,
    MAX(CASE WHEN attraction_rank = 1 THEN visitors END) AS top_attraction_visitors
  FROM ranked
  GROUP BY canonical_region_id, observed_month
)
SELECT s.canonical_region_id, s.observed_month, s.attraction_count, s.total_visitors,
       s.top_attraction_name, s.top_attraction_visitors,
       d.source_district_count
FROM summary AS s
JOIN district_summary AS d
  ON d.canonical_region_id=s.canonical_region_id
 AND d.observed_month=s.observed_month;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_detail_monthly_summary AS
WITH periods AS (
  SELECT canonical_region_id, period_start FROM datalab_sns_companion_monthly_canonical
  UNION
  SELECT canonical_region_id, period_start FROM datalab_sns_travel_monthly_canonical
  UNION
  SELECT canonical_region_id, period_start FROM datalab_navigation_destination_monthly_canonical
  UNION
  SELECT canonical_region_id, period_start FROM datalab_spend_industry_monthly_canonical
), companion_ranked AS (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY canonical_region_id, period_start
           ORDER BY mention_count DESC, companion_type
         ) AS rn
  FROM datalab_sns_companion_monthly_canonical AS c
), companion AS (
  SELECT canonical_region_id, period_start,
         SUM(mention_count) AS companion_mentions,
         COUNT(*) AS companion_type_count,
         MAX(CASE WHEN rn=1 THEN companion_type END) AS top_companion_type,
         MAX(CASE WHEN rn=1 THEN mention_count END) AS top_companion_mentions
  FROM companion_ranked
  GROUP BY canonical_region_id, period_start
), travel_ranked AS (
  SELECT t.*,
         ROW_NUMBER() OVER (
           PARTITION BY canonical_region_id, period_start
           ORDER BY mention_count DESC, travel_type
         ) AS rn
  FROM datalab_sns_travel_monthly_canonical AS t
), travel AS (
  SELECT canonical_region_id, period_start,
         SUM(mention_count) AS travel_mentions,
         COUNT(*) AS travel_type_count,
         MAX(CASE WHEN rn=1 THEN travel_type END) AS top_travel_type,
         MAX(CASE WHEN rn=1 THEN mention_count END) AS top_travel_mentions
  FROM travel_ranked
  GROUP BY canonical_region_id, period_start
), navigation_ranked AS (
  SELECT n.*,
         ROW_NUMBER() OVER (
           PARTITION BY canonical_region_id, period_start
           ORDER BY search_count DESC, destination_type
         ) AS rn
  FROM datalab_navigation_destination_monthly_canonical AS n
  WHERE destination_type <> '전체'
), navigation AS (
  SELECT n.canonical_region_id, n.period_start,
         MAX(CASE WHEN n.destination_type='전체' THEN n.search_count END)
           AS destination_searches,
         COUNT(CASE WHEN n.destination_type <> '전체' THEN 1 END)
           AS destination_type_count,
         MAX(CASE WHEN r.rn=1 THEN r.destination_type END)
           AS top_destination_type,
         MAX(CASE WHEN r.rn=1 THEN r.search_count END)
           AS top_destination_searches
  FROM datalab_navigation_destination_monthly_canonical AS n
  LEFT JOIN navigation_ranked AS r
    ON r.canonical_region_id=n.canonical_region_id
   AND r.period_start=n.period_start
   AND r.destination_type=n.destination_type
  GROUP BY n.canonical_region_id, n.period_start
), spend_ranked AS (
  SELECT s.*,
         ROW_NUMBER() OVER (
           PARTITION BY canonical_region_id, period_start, visitor_segment
           ORDER BY spend_krw_thousand DESC, industry_major
         ) AS rn
  FROM datalab_spend_industry_monthly_canonical AS s
  WHERE industry_major <> '전체'
), spend AS (
  SELECT s.canonical_region_id, s.period_start,
         MAX(CASE WHEN s.visitor_segment='domestic' AND s.industry_major='전체'
                  THEN s.spend_krw_thousand END) AS domestic_spend_krw_thousand,
         MAX(CASE WHEN s.visitor_segment='outsider' AND s.industry_major='전체'
                  THEN s.spend_krw_thousand END) AS outsider_spend_krw_thousand,
         MAX(CASE WHEN s.visitor_segment='local' AND s.industry_major='전체'
                  THEN s.spend_krw_thousand END) AS local_spend_krw_thousand,
         MAX(CASE WHEN r.visitor_segment='domestic' AND r.rn=1
                  THEN r.industry_major END) AS top_domestic_industry,
         MAX(CASE WHEN r.visitor_segment='domestic' AND r.rn=1
                  THEN r.spend_krw_thousand END) AS top_domestic_industry_spend,
         MAX(CASE WHEN r.visitor_segment='outsider' AND r.rn=1
                  THEN r.industry_major END) AS top_outsider_industry,
         MAX(CASE WHEN r.visitor_segment='outsider' AND r.rn=1
                  THEN r.spend_krw_thousand END) AS top_outsider_industry_spend
  FROM datalab_spend_industry_monthly_canonical AS s
  LEFT JOIN spend_ranked AS r
    ON r.canonical_region_id=s.canonical_region_id
   AND r.period_start=s.period_start
   AND r.visitor_segment=s.visitor_segment
   AND r.industry_major=s.industry_major
  GROUP BY s.canonical_region_id, s.period_start
)
SELECT
  p.canonical_region_id,
  r.region_name AS canonical_region_name,
  p.period_start,
  c.companion_mentions,
  c.companion_type_count,
  c.top_companion_type,
  c.top_companion_mentions,
  t.travel_mentions,
  t.travel_type_count,
  t.top_travel_type,
  t.top_travel_mentions,
  n.destination_searches,
  n.destination_type_count,
  n.top_destination_type,
  n.top_destination_searches,
  s.domestic_spend_krw_thousand,
  s.outsider_spend_krw_thousand,
  s.local_spend_krw_thousand,
  s.top_domestic_industry,
  s.top_domestic_industry_spend,
  s.top_outsider_industry,
  s.top_outsider_industry_spend
FROM periods AS p
JOIN dim_region AS r
  ON r.region_id=p.canonical_region_id
LEFT JOIN companion AS c
  ON c.canonical_region_id=p.canonical_region_id
 AND c.period_start=p.period_start
LEFT JOIN travel AS t
  ON t.canonical_region_id=p.canonical_region_id
 AND t.period_start=p.period_start
LEFT JOIN navigation AS n
  ON n.canonical_region_id=p.canonical_region_id
 AND n.period_start=p.period_start
LEFT JOIN spend AS s
  ON s.canonical_region_id=p.canonical_region_id
 AND s.period_start=p.period_start;
