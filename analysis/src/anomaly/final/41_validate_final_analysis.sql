SET NAMES utf8mb4;
USE tour_earlywarning;

SELECT 'final_analysis' AS check_name,COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,MIN(episode_start) AS date_min,
       MAX(episode_end) AS date_max
FROM vw_final_anomaly_analysis;

SELECT final_explanation_group,COUNT(*) AS episodes,COUNT(DISTINCT region_id) AS regions
FROM vw_final_anomaly_analysis
GROUP BY final_explanation_group
ORDER BY episodes DESC;

SELECT * FROM vw_final_anomaly_metrics;

SELECT 'weather_coverage' AS check_name,
       SUM(weather_station_id IS NOT NULL) AS station_mapped,
       SUM(weather_context_type IS NOT NULL) AS weather_matched,
       COUNT(*) AS episodes
FROM vw_final_anomaly_analysis;

SELECT 'duplicate_keys' AS check_name,COUNT(*) AS actual
FROM (
  SELECT region_id,episode_no FROM vw_final_anomaly_analysis
  GROUP BY region_id,episode_no HAVING COUNT(*)>1
) AS d;

SELECT region_name,search_peak_date,visitor_peak_date,
       representative_festival_name,festival_start,
       search_to_festival_lead_days,visitor_to_festival_lead_days,
       ROUND(peak_anomaly_score,3) AS anomaly_score
FROM vw_final_anomaly_analysis
WHERE festival_match_count>0
ORDER BY peak_anomaly_score DESC
LIMIT 20;

