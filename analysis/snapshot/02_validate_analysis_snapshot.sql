USE tour_earlywarning;

SELECT 'daily_core' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT region_id) AS regions_actual,
       MIN(observed_date) AS date_min,
       MAX(observed_date) AS date_max
FROM snap_20260922_daily_core;

SELECT 'daily_core_duplicate_keys' AS check_name,
       COUNT(*) AS duplicate_groups
FROM (
  SELECT region_id, observed_date
  FROM snap_20260922_daily_core
  GROUP BY region_id, observed_date
  HAVING COUNT(*) > 1
) d;

SELECT 'datalab_monthly' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions_actual,
       COUNT(DISTINCT period_start) AS months_actual,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM snap_20260922_datalab_monthly;

SELECT 'anomaly_final' AS check_name,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions_actual
FROM snap_20260922_anomaly_final;

SELECT 'festival' AS check_name,
       (SELECT COUNT(*) FROM snap_20260922_event) AS events,
       (SELECT COUNT(*) FROM snap_20260922_event_point) AS event_points;

SELECT 'evidence_top3' AS check_name,
       COUNT(*) AS evidence_rows
FROM snap_20260922_evidence_top3;

SELECT 'asos_daily' AS check_name,
       COUNT(*) AS rows_actual
FROM snap_20260922_asos_daily;

SELECT *
FROM analysis_snapshot_manifest_20260922
ORDER BY snapshot_name;
