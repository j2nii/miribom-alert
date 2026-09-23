USE tour_earlywarning;

-- 1) 분석용 정본 지역: 228
SELECT 'dim_region' AS check_name, COUNT(*) AS actual, 228 AS expected
FROM dim_region;

-- 2) 외지인 방문자수: 717,744행, 228지역, 3,148일, 2018-01-01~2026-08-14
SELECT 'visitors_external' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT region_id) AS regions_actual,
       COUNT(DISTINCT observed_date) AS days_actual,
       MIN(observed_date) AS date_min,
       MAX(observed_date) AS date_max
FROM fact_signal
WHERE metric='realization_visitors' AND segment='external';

-- 3) 네이버: 138,624행, 228지역, 608일, 2025-01-01~2026-08-31
SELECT 'naver' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT region_id) AS regions_actual,
       COUNT(DISTINCT observed_date) AS days_actual,
       MIN(observed_date) AS date_min,
       MAX(observed_date) AS date_max,
       MAX(value) AS value_max
FROM fact_signal
WHERE metric='interest_naver';

-- 4) YouTube: 고유 영상 6,338건, 사례지역 6곳
SELECT 'youtube' AS check_name,
       COUNT(*) AS videos_actual,
       COUNT(DISTINCT region_id) AS regions_actual,
       SUM(view_count IS NULL) AS missing_views,
       SUM(like_count IS NULL) AS missing_likes,
       SUM(comment_count IS NULL) AS missing_comments
FROM youtube_video;

-- 5) 데이터랩 월별: 3,108행, 원천 259지역, 12개월
SELECT 'datalab_panel' AS check_name,
       COUNT(*) AS rows_actual,
       COUNT(DISTINCT source_region_name) AS source_regions_actual,
       COUNT(DISTINCT period_start) AS months_actual,
       MIN(period_start) AS date_min,
       MAX(period_start) AS date_max
FROM datalab_monthly_panel;

-- 6) 자동 매핑 211지역, 보류 48지역
SELECT 'datalab_mapping' AS check_name,
       COUNT(DISTINCT CASE WHEN canonical_region_id IS NOT NULL THEN source_region_name END) AS mapped_regions,
       COUNT(DISTINCT CASE WHEN canonical_region_id IS NULL THEN source_region_name END) AS unmapped_regions
FROM datalab_monthly_panel;

-- 7) 핵심 결측: 방문자수 71, SNS 770, 내비 79
SELECT 'datalab_missing' AS check_name,
       SUM(visitors IS NULL) AS missing_visitors,
       SUM(sns_mentions IS NULL) AS missing_sns,
       SUM(navigation_searches IS NULL) AS missing_navigation,
       SUM(lodging_searches IS NULL) AS missing_lodging_search
FROM datalab_monthly_panel;

-- 8) 네이버 원천 28260은 정본 INCHEON_WEST로 저장되어야 한다.
SELECT 'naver_incheon_mapping' AS check_name,
       SUM(region_id='28260') AS wrong_28260,
       SUM(region_id='INCHEON_WEST') AS canonical_west_rows
FROM fact_signal
WHERE metric='interest_naver';

-- 9) events.json이 없으므로 둘 다 0이 정상이다.
SELECT 'empty_events' AS check_name,
       (SELECT COUNT(*) FROM event) AS events,
       (SELECT COUNT(*) FROM event_point) AS event_points;

-- 10) 크롤러 시작 전에는 0이 정상이다.
SELECT 'empty_crawler' AS check_name,
       (SELECT COUNT(*) FROM crawl_run) AS runs,
       (SELECT COUNT(*) FROM raw_payload) AS payloads;
