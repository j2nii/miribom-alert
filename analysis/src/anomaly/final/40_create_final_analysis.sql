SET NAMES utf8mb4;
USE tour_earlywarning;

DROP VIEW IF EXISTS vw_final_anomaly_analysis;
DROP VIEW IF EXISTS vw_final_anomaly_metrics;
DROP TABLE IF EXISTS final_anomaly_analysis_snapshot;
DROP TABLE IF EXISTS festival_episode_match_snapshot;
DROP TABLE IF EXISTS episode_weather_context_snapshot;
DROP TABLE IF EXISTS region_asos_station_map;
DROP TABLE IF EXISTS final_analysis_base_snapshot;

-- 축제 적재 이후의 라이브 뷰를 450개 에피소드 정본으로 다시 고정합니다.
CREATE TABLE final_analysis_base_snapshot ENGINE=InnoDB AS
SELECT * FROM vw_anomaly_analysis_ready;

ALTER TABLE final_analysis_base_snapshot
  ADD UNIQUE KEY uq_final_base_episode(region_id, episode_no),
  ADD KEY ix_final_base_peak(visitor_peak_date);

-- 에피소드별 축제 후보를 생성하고 가장 가까운 대표 축제 한 건을 선택합니다.
CREATE TABLE festival_episode_match_snapshot ENGINE=InnoDB AS
WITH candidates AS (
  SELECT
    a.region_id,
    a.episode_no,
    w.event_id,
    w.event_name,
    w.window_start AS festival_start,
    w.window_end AS festival_end,
    (a.visitor_peak_date BETWEEN w.window_start AND w.window_end) AS exact_overlap,
    DATEDIFF(w.window_start, a.search_peak_date) AS search_lead_days,
    DATEDIFF(w.window_start, a.visitor_peak_date) AS visitor_lead_days,
    ABS(DATEDIFF(w.window_start, a.visitor_peak_date)) AS distance_days,
    ROW_NUMBER() OVER (
      PARTITION BY a.region_id, a.episode_no
      ORDER BY
        (a.visitor_peak_date BETWEEN w.window_start AND w.window_end) DESC,
        ABS(DATEDIFF(w.window_start, a.visitor_peak_date)),
        w.window_start,
        w.event_id
    ) AS rn,
    COUNT(*) OVER (PARTITION BY a.region_id, a.episode_no) AS festival_match_count
  FROM final_analysis_base_snapshot AS a
  JOIN vw_event_window AS w
    ON w.region_id=a.region_id
   AND w.event_type='festival'
   AND a.visitor_peak_date BETWEEN DATE_SUB(w.window_start, INTERVAL 7 DAY)
                               AND DATE_ADD(w.window_end, INTERVAL 14 DAY)
)
SELECT region_id,episode_no,event_id,event_name,festival_start,festival_end,
       exact_overlap,search_lead_days,visitor_lead_days,distance_days,
       festival_match_count
FROM candidates
WHERE rn=1;

ALTER TABLE festival_episode_match_snapshot
  ADD PRIMARY KEY(region_id, episode_no),
  ADD KEY ix_festival_match_start(festival_start);

-- ASOS 지점 연결: 광역시는 대표지점, 그 밖은 지역명과 지점명이 유일하게
-- 일치하는 경우에만 자동 연결합니다.
CREATE TABLE region_asos_station_map (
  region_id VARCHAR(20) NOT NULL,
  station_id VARCHAR(10) NOT NULL,
  mapping_method VARCHAR(30) NOT NULL,
  PRIMARY KEY(region_id),
  KEY ix_station(station_id)
) ENGINE=InnoDB;

INSERT IGNORE INTO region_asos_station_map(region_id,station_id,mapping_method)
SELECT region_id,
       CASE sido_code
         WHEN '11' THEN '108' WHEN '26' THEN '159' WHEN '27' THEN '143'
         WHEN '28' THEN '112' WHEN '30' THEN '133'
         WHEN '31' THEN '152' WHEN '36' THEN '239' ELSE NULL END,
       'metro_representative'
FROM dim_region
WHERE sido_code IN ('11','26','27','28','30','31','36');

-- 광주·전남 통합 정본(시도코드 12) 중 기존 광주 5개 자치구만 광주 지점을 사용합니다.
INSERT IGNORE INTO region_asos_station_map(region_id,station_id,mapping_method)
SELECT region_id,'156','metro_representative'
FROM dim_region
WHERE region_id IN ('12110','12210','12240','12270','12300');

INSERT IGNORE INTO region_asos_station_map(region_id,station_id,mapping_method)
SELECT r.region_id, MIN(w.station_id), 'unique_name_match'
FROM dim_region AS r
JOIN (SELECT DISTINCT station_id,station_name FROM raw_kma_asos_daily) AS w
  ON REPLACE(REPLACE(REPLACE(r.region_name,'시',''),'군',''),'구','')
   = REPLACE(REPLACE(REPLACE(w.station_name,'시',''),'군',''),'구','')
WHERE r.sido_code NOT IN ('11','26','27','28','30','31','36')
GROUP BY r.region_id
HAVING COUNT(DISTINCT w.station_id)=1;

CREATE TABLE episode_weather_context_snapshot ENGINE=InnoDB AS
SELECT
  a.region_id,
  a.episode_no,
  m.station_id,
  m.mapping_method AS weather_mapping_method,
  w.station_name,
  w.avg_temperature_c,
  w.min_temperature_c,
  w.max_temperature_c,
  w.precipitation_mm,
  w.avg_humidity_pct,
  w.max_wind_speed_ms,
  w.snow_depth_cm,
  CASE
    WHEN w.precipitation_mm >= 30 THEN 'heavy_rain'
    WHEN w.snow_depth_cm > 0 THEN 'snow'
    WHEN w.max_wind_speed_ms >= 14 THEN 'strong_wind'
    WHEN w.min_temperature_c <= -10 THEN 'cold_wave_context'
    WHEN w.max_temperature_c >= 33 THEN 'heat_wave_context'
    WHEN w.observed_date IS NOT NULL THEN 'ordinary_weather'
    ELSE NULL
  END AS weather_context_type
FROM final_analysis_base_snapshot AS a
LEFT JOIN region_asos_station_map AS m ON m.region_id=a.region_id
LEFT JOIN raw_kma_asos_daily AS w
  ON w.station_id=m.station_id AND w.observed_date=a.visitor_peak_date;

ALTER TABLE episode_weather_context_snapshot
  ADD PRIMARY KEY(region_id, episode_no);

CREATE TABLE final_anomaly_analysis_snapshot ENGINE=InnoDB AS
SELECT
  a.*,
  f.event_id AS representative_festival_event_id,
  f.event_name AS representative_festival_name,
  f.festival_start,
  f.festival_end,
  COALESCE(f.festival_match_count,0) AS festival_match_count,
  COALESCE(f.exact_overlap,0) AS festival_exact_overlap,
  f.search_lead_days AS search_to_festival_lead_days,
  f.visitor_lead_days AS visitor_to_festival_lead_days,
  w.station_id AS weather_station_id,
  w.station_name AS weather_station_name,
  w.weather_mapping_method,
  w.avg_temperature_c,
  w.min_temperature_c,
  w.max_temperature_c,
  w.precipitation_mm,
  w.max_wind_speed_ms,
  w.snow_depth_cm,
  w.weather_context_type,
  CASE
    WHEN f.exact_overlap=1 THEN 'festival_exact_overlap'
    WHEN f.event_id IS NOT NULL AND f.search_lead_days BETWEEN 0 AND 30
      THEN 'festival_pre_signal'
    WHEN f.event_id IS NOT NULL THEN 'festival_nearby'
    WHEN a.matched_calendar_days > 0 THEN 'calendar_related'
    WHEN w.weather_context_type IN ('heavy_rain','snow','strong_wind','cold_wave_context','heat_wave_context')
      THEN 'weather_context'
    WHEN a.explanation_status IN ('verified_external_evidence','strong_external_candidate')
      THEN 'external_evidence'
    WHEN a.explanation_status='possible_external_candidate'
      THEN 'possible_external'
    ELSE 'unexplained_candidate'
  END AS final_explanation_group,
  CASE
    WHEN f.event_id IS NOT NULL
      OR a.matched_calendar_days > 0
      OR a.explanation_status IN ('verified_external_evidence','strong_external_candidate')
      THEN 1 ELSE 0
  END AS conservative_explained_flag
FROM final_analysis_base_snapshot AS a
LEFT JOIN festival_episode_match_snapshot AS f
  ON f.region_id=a.region_id AND f.episode_no=a.episode_no
LEFT JOIN episode_weather_context_snapshot AS w
  ON w.region_id=a.region_id AND w.episode_no=a.episode_no;

ALTER TABLE final_anomaly_analysis_snapshot
  ADD UNIQUE KEY uq_final_analysis_episode(region_id, episode_no),
  ADD KEY ix_final_analysis_group(final_explanation_group),
  ADD KEY ix_final_analysis_score(peak_anomaly_score),
  ADD KEY ix_final_analysis_festival(festival_start);

CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY INVOKER
VIEW vw_final_anomaly_analysis AS
SELECT * FROM final_anomaly_analysis_snapshot;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_final_anomaly_metrics AS
SELECT
  COUNT(*) AS total_episodes,
  SUM(festival_match_count>0) AS festival_matched_episodes,
  SUM(festival_exact_overlap=1) AS festival_exact_episodes,
  SUM(final_explanation_group='festival_pre_signal') AS festival_pre_signal_episodes,
  SUM(matched_calendar_days>0) AS calendar_matched_episodes,
  SUM(weather_context_type IN ('heavy_rain','snow','strong_wind','cold_wave_context','heat_wave_context'))
    AS adverse_weather_context_episodes,
  SUM(conservative_explained_flag=1) AS conservatively_explained_episodes,
  SUM(final_explanation_group='unexplained_candidate') AS unexplained_episodes,
  ROUND(SUM(festival_match_count>0)/COUNT(*)*100,2) AS festival_match_pct,
  ROUND(SUM(conservative_explained_flag=1)/COUNT(*)*100,2) AS conservative_explained_pct,
  ROUND(SUM(final_explanation_group='unexplained_candidate')/COUNT(*)*100,2) AS unresolved_pct,
  ROUND(AVG(CASE WHEN festival_match_count>0 THEN search_to_festival_lead_days END),2)
    AS mean_search_to_festival_lead_days,
  ROUND(AVG(CASE WHEN festival_match_count>0 THEN visitor_to_festival_lead_days END),2)
    AS mean_visitor_to_festival_lead_days
FROM final_anomaly_analysis_snapshot;
