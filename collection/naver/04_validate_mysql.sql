USE tour_earlywarning;

SELECT
  'naver_extended' AS check_name,
  COUNT(*) AS rows_actual,
  COUNT(DISTINCT region_id) AS regions_actual,
  COUNT(DISTINCT observed_date) AS days_actual,
  MIN(observed_date) AS date_min,
  MAX(observed_date) AS date_max,
  SUM(value < 0) AS negative_values
FROM fact_signal
WHERE metric = 'interest_naver'
  AND source_system = 'naver_search_trend';

SELECT
  'region_day_count_mismatch' AS check_name,
  COUNT(*) AS bad_regions
FROM (
  SELECT region_id
  FROM fact_signal
  WHERE metric = 'interest_naver'
    AND source_system = 'naver_search_trend'
  GROUP BY region_id
  HAVING COUNT(DISTINCT observed_date) <> 1339
) AS x;
