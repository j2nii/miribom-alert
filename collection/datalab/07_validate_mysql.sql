USE tour_earlywarning;

SELECT 'datalab_total' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT source_region_name) AS regions_actual,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_monthly_panel;

SELECT YEAR(period_start) AS year,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT source_region_name) AS regions_actual,
       COUNT(DISTINCT period_start) AS months_actual
FROM datalab_monthly_panel
GROUP BY YEAR(period_start)
ORDER BY year;

SELECT 'datalab_202608' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT source_region_name) AS regions_actual,
       SUM(visitors IS NULL) AS missing_visitors,
       SUM(sns_mentions IS NULL) AS missing_sns,
       SUM(navigation_searches IS NULL) AS missing_navigation,
       SUM(local_currency_spend_krw_thousand IS NULL) AS missing_local_currency
FROM datalab_monthly_panel
WHERE period_start = '2026-08-01';

SELECT 'duplicate_keys' AS check_name, COUNT(*) AS groups_actual
FROM (
  SELECT source_region_name, period_start
  FROM datalab_monthly_panel
  GROUP BY source_region_name, period_start
  HAVING COUNT(*) > 1
) AS d;
