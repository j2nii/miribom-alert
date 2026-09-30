SET NAMES utf8mb4;
USE tour_earlywarning;

SELECT 'raw_panel' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT source_region_name) AS source_regions,
       COUNT(DISTINCT period_start) AS months_actual,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_monthly_panel;

SELECT 'mapping_coverage' AS check_name,
       COUNT(*) AS mapping_rows,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions
FROM datalab_region_mapping;

SELECT 'unmapped_source_names' AS check_name, COUNT(*) AS actual
FROM (
  SELECT DISTINCT p.source_region_name
  FROM datalab_monthly_panel AS p
  LEFT JOIN datalab_region_mapping AS m
    ON m.source_region_name = p.source_region_name
  WHERE m.source_region_name IS NULL
) AS x;

SELECT 'panel_null_canonical' AS check_name, COUNT(*) AS actual
FROM datalab_monthly_panel
WHERE canonical_region_id IS NULL;

SELECT 'canonical_view' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions,
       COUNT(DISTINCT period_start) AS months_actual,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM vw_datalab_canonical_monthly;

SELECT 'canonical_duplicate_keys' AS check_name, COUNT(*) AS actual
FROM (
  SELECT canonical_region_id, period_start
  FROM vw_datalab_canonical_monthly
  GROUP BY canonical_region_id, period_start
  HAVING COUNT(*) > 1
) AS x;

SELECT 'reform_old_new_overlap' AS check_name, COUNT(*) AS actual
FROM (
  SELECT p.period_start, m.canonical_region_id
  FROM datalab_monthly_panel AS p
  JOIN datalab_region_mapping AS m
    ON m.source_region_name = p.source_region_name
  WHERE m.mapping_type IN ('reform_old', 'reform_new')
    AND (m.valid_from IS NULL OR p.period_start >= m.valid_from)
    AND (m.valid_to IS NULL OR p.period_start <= m.valid_to)
  GROUP BY p.period_start, m.canonical_region_id
  HAVING SUM(m.mapping_type = 'reform_old') > 0
     AND SUM(m.mapping_type = 'reform_new') > 0
) AS x;

SELECT YEAR(period_start) AS year,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions,
       COUNT(DISTINCT period_start) AS months_actual
FROM vw_datalab_canonical_monthly
GROUP BY YEAR(period_start)
ORDER BY year;

SELECT 'latest_month' AS check_name,
       period_start,
       COUNT(*) AS rows_actual,
       SUM(visitors IS NULL) AS missing_visitors,
       SUM(sns_mentions IS NULL) AS missing_sns,
       SUM(navigation_searches IS NULL) AS missing_navigation,
       SUM(local_currency_spend_krw_thousand IS NULL) AS missing_local_currency
FROM vw_datalab_canonical_monthly
WHERE period_start = (SELECT MAX(period_start) FROM datalab_monthly_panel)
GROUP BY period_start;

-- Expected with the current DB:
-- raw_panel                 20,720 rows / 259 regions / 80 months
-- mapping_coverage          259 rows / 228 canonical regions
-- unmapped_source_names     0
-- panel_null_canonical      0
-- canonical_view            18,240 rows / 228 regions / 80 months
-- canonical_duplicate_keys  0
-- reform_old_new_overlap    0

