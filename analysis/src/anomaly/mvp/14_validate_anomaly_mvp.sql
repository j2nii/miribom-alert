SET NAMES utf8mb4;
USE tour_earlywarning;

SELECT 'core_daily' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT region_id) AS regions_actual,
       COUNT(DISTINCT observed_date) AS days_actual,
       MIN(observed_date) AS date_min,
       MAX(observed_date) AS date_max
FROM vw_daily_core_signal;

SELECT 'duplicate_region_dates' AS check_name, COUNT(*) AS actual
FROM (
  SELECT region_id, observed_date
  FROM vw_daily_core_signal
  GROUP BY region_id, observed_date
  HAVING COUNT(*) > 1
) AS x;

SELECT 'baseline_ready' AS check_name,
       COUNT(*) AS rows_actual,
       SUM(naver_baseline_n >= 6 AND visitor_baseline_n >= 6) AS ready_rows,
       SUM(naver_z IS NULL) AS missing_naver_z,
       SUM(visitor_z IS NULL) AS missing_visitor_z
FROM vw_daily_anomaly_features;

SELECT candidate_type,
       COUNT(*) AS candidates,
       COUNT(DISTINCT region_id) AS regions
FROM vw_daily_anomaly_candidates
GROUP BY candidate_type
ORDER BY candidates DESC;

SELECT 'viral_candidates' AS check_name,
       COUNT(*) AS candidates,
       COUNT(DISTINCT region_id) AS regions,
       MIN(observed_date) AS date_min,
       MAX(observed_date) AS date_max
FROM vw_daily_anomaly_candidates
WHERE is_viral_candidate = 1;

SELECT region_id,
       region_name,
       observed_date,
       ROUND(naver_z_max_prior_14d, 3) AS naver_z_14d,
       ROUND(visitor_z, 3) AS visitor_z,
       ROUND(anomaly_score, 3) AS anomaly_score,
       candidate_type
FROM vw_daily_anomaly_candidates
WHERE is_viral_candidate = 1
ORDER BY anomaly_score DESC
LIMIT 20;

SELECT 'event_data' AS check_name,
       (SELECT COUNT(*) FROM event) AS events,
       (SELECT COUNT(*) FROM event_point) AS event_points,
       (SELECT COUNT(*)
          FROM vw_anomaly_candidate_context
         WHERE matched_event_count > 0) AS matched_candidate_days;

SELECT 'calendar_holidays' AS check_name,
       SUM(is_public_holiday = 1) AS registered_holidays,
       SUM(is_weekend = 1) AS weekend_days
FROM analysis_calendar
WHERE calendar_date BETWEEN
      (SELECT MIN(observed_date) FROM vw_daily_core_signal)
  AND (SELECT MAX(observed_date) FROM vw_daily_core_signal);

