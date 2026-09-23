USE tour_earlywarning;

-- 1. 이번에 추가 적재된 테이블별 행 수
SELECT 'datalab_detail_row' table_name, COUNT(*) rows_actual FROM datalab_detail_row
UNION ALL SELECT 'jeju_attraction_visitors_daily', COUNT(*) FROM jeju_attraction_visitors_daily
UNION ALL SELECT 'domestic_tourist_residence_annual', COUNT(*) FROM domestic_tourist_residence_annual
UNION ALL SELECT 'external_collection_catalog', COUNT(*) FROM external_collection_catalog
UNION ALL SELECT 'observed_visitors_case', COUNT(*) FROM observed_visitors_case
UNION ALL SELECT 'domestic_interest_attraction_rank', COUNT(*) FROM domestic_interest_attraction_rank
UNION ALL SELECT 'major_attraction_visitors_monthly', COUNT(*) FROM major_attraction_visitors_monthly
UNION ALL SELECT 'reference_document_catalog', COUNT(*) FROM reference_document_catalog;

-- 2. DataLab SNS 동반유형 월별 언급량
SELECT *
FROM vw_datalab_sns_companion_monthly
WHERE source_region_code = '11110'
ORDER BY observed_month, mention_count DESC;

-- 3. DataLab 여행유형/트렌드 월별 언급량
SELECT *
FROM vw_datalab_sns_travel_type_monthly
WHERE source_region_code = '11110'
ORDER BY observed_month, mention_count DESC;

-- 4. DataLab 내비게이션 목적지 유형별 검색량
SELECT *
FROM vw_datalab_navigation_destination_monthly
WHERE source_region_code = '11110'
ORDER BY observed_month, search_count DESC;

-- 5. DataLab 업종별 관광소비
SELECT *
FROM vw_datalab_spend_industry_monthly
WHERE source_region_code = '11110'
ORDER BY observed_month, visitor_segment, spend_krw_thousand DESC;

-- 6. DataLab 기간 전체 키워드 스냅샷
SELECT *
FROM vw_datalab_keyword_snapshot
WHERE source_region_code = '11110'
ORDER BY query_start_month, data_group, ranking;

-- 7. 특정 지역 주요 관광지 월별 입장객
SELECT province_name, district_name, attraction_name, visitor_type,
       observed_month, visitor_count
FROM major_attraction_visitors_monthly
WHERE district_name LIKE '%영월%'
ORDER BY attraction_name, visitor_type, observed_month;

-- 8. 제주 관광지 일별 입장객
SELECT observed_date, attraction_name, visitor_count
FROM jeju_attraction_visitors_daily
ORDER BY observed_date, attraction_name;

-- 9. 수집 파일 누락·실패 여부
SELECT load_status, COUNT(*) members
FROM ingest_archive_member
GROUP BY load_status;

-- 10. 아직 전용 뷰가 없는 DataLab 파일 유형도 row_json으로 전부 조회 가능
SELECT source_region_code, observed_month, data_group, row_json
FROM datalab_detail_row
WHERE data_group = '방문자 거주지 분포'
LIMIT 20;
