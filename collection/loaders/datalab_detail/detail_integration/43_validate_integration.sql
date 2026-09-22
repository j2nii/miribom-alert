SET NAMES utf8mb4;
USE tour_earlywarning;

SELECT 'datalab_detail_mapping' AS check_name,
       COUNT(DISTINCT CONCAT(d.source_region_code,'|',COALESCE(d.source_region_name,'')))
         AS source_region_pairs,
       (SELECT COUNT(*) FROM datalab_detail_region_map) AS mapped_pairs,
       (SELECT COUNT(DISTINCT canonical_region_id)
          FROM datalab_detail_region_map) AS canonical_regions,
       (SELECT COUNT(*) FROM vw_datalab_detail_unmapped) AS unmapped_pairs
FROM datalab_detail_row AS d;

SELECT 'datalab_detail_row_coverage' AS check_name,
       COUNT(*) AS raw_rows,
       SUM(m.source_region_code IS NOT NULL) AS mapped_rows,
       SUM(m.source_region_code IS NULL) AS unmapped_rows
FROM datalab_detail_row AS d
LEFT JOIN datalab_detail_region_map AS m
  ON m.source_region_code=d.source_region_code
 AND m.source_region_name=COALESCE(d.source_region_name,'');

SELECT 'companion_features' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions,
       COUNT(DISTINCT period_start) AS months,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_sns_companion_monthly_canonical;

SELECT 'travel_features' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions,
       COUNT(DISTINCT period_start) AS months,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_sns_travel_monthly_canonical;

SELECT 'navigation_features' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions,
       COUNT(DISTINCT period_start) AS months,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_navigation_destination_monthly_canonical;

SELECT 'spend_features' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions,
       COUNT(DISTINCT period_start) AS months,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_spend_industry_monthly_canonical;

SELECT 'attraction_mapping' AS check_name,
       COUNT(DISTINCT CONCAT(province_name,'|',district_name)) AS source_districts,
       (SELECT COUNT(*) FROM attraction_region_map) AS mapped_districts,
       (SELECT COUNT(*) FROM vw_attraction_region_unmapped) AS unmapped_districts
FROM major_attraction_visitors_monthly;

SELECT 'attraction_features' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT canonical_region_id) AS regions,
       COUNT(DISTINCT period_start) AS months,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM attraction_visitors_monthly_canonical;

SELECT 'enriched_episodes' AS check_name,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       SUM(enriched_data_status='datalab_and_attraction') AS datalab_and_attraction,
       SUM(enriched_data_status='datalab_detail_only') AS datalab_detail_only,
       SUM(enriched_data_status='attraction_only') AS attraction_only,
       SUM(enriched_data_status='no_new_detail') AS no_new_detail
FROM vw_anomaly_analysis_enriched;

SELECT 'duplicate_episode_keys' AS check_name, COUNT(*) AS actual
FROM (
  SELECT region_id, episode_no
  FROM vw_anomaly_analysis_enriched
  GROUP BY region_id, episode_no
  HAVING COUNT(*) > 1
) AS d;

SELECT collection_priority,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       ROUND(AVG(collection_priority_score),2) AS avg_priority_score
FROM vw_additional_collection_priority
GROUP BY collection_priority
ORDER BY FIELD(collection_priority,'P1','P2','P3');

SELECT
  region_name,
  visitor_peak_date,
  ROUND(peak_anomaly_score,3) AS anomaly_score,
  explanation_status,
  enriched_data_status,
  detail_top_travel_type,
  top_attraction_name,
  collection_priority,
  collection_priority_score,
  recommended_action
FROM vw_additional_collection_priority
ORDER BY collection_priority_score DESC, visitor_peak_date DESC
LIMIT 20;
