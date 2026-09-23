USE tour_earlywarning;

-- 1. 세부지표가 결합된 450개 이상 에피소드
SELECT
  region_name,
  episode_start,
  visitor_peak_date,
  peak_anomaly_score,
  explanation_status,
  detail_top_companion_type,
  detail_top_travel_type,
  detail_top_destination_type,
  detail_top_outsider_industry,
  top_attraction_name,
  attraction_visitors_mom_pct,
  enriched_data_status
FROM vw_anomaly_analysis_enriched
ORDER BY peak_anomaly_score DESC
LIMIT 30;

-- 2. 화요일 전 추가수집 우선순위
SELECT *
FROM vw_additional_collection_priority
ORDER BY FIELD(collection_priority,'P1','P2','P3'),
         collection_priority_score DESC;

-- 3. 특정 지역의 월별 SNS·내비·소비 세부지표
SELECT *
FROM vw_datalab_detail_monthly_summary
WHERE canonical_region_id='47280'
ORDER BY period_start;

-- 4. 특정 지역의 관광지 입장객 추이
SELECT *
FROM attraction_visitors_monthly_canonical
WHERE canonical_region_id='51750'
ORDER BY period_start;

-- 5. 원인 해석용 기간별 키워드
SELECT *
FROM vw_datalab_keyword_canonical
WHERE canonical_region_id='51750'
ORDER BY query_start_month, data_group, ranking;

-- 6. 매핑되지 않은 DataLab 및 관광지 지역
SELECT * FROM vw_datalab_detail_unmapped ORDER BY rows_actual DESC;
SELECT * FROM vw_attraction_region_unmapped ORDER BY rows_actual DESC;

-- 7. 수동 매핑 예시: 실제 미매핑 결과를 확인한 뒤에만 사용
-- INSERT INTO datalab_detail_region_map
--   (source_region_code, source_region_name, canonical_region_id,
--    mapping_method, mapping_note)
-- VALUES
--   ('원천코드', '원천지역명', '정본지역ID', 'manual', '수동 확인');
