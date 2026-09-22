SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_observed_visitors_case_canonical AS
SELECT
  r.region_id AS canonical_region_id,
  r.region_name AS canonical_region_name,
  o.*
FROM observed_visitors_case AS o
JOIN province_sido_mapping AS p
  ON p.province_name = SUBSTRING_INDEX(o.region_name, ' ', 1)
JOIN dim_region AS r
  ON r.sido_code = p.canonical_sido_code
 AND r.region_name = TRIM(
       SUBSTRING(o.region_name, LOCATE(' ', o.region_name) + 1)
     );

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_interest_attraction_rank_canonical AS
SELECT
  r.region_id AS canonical_region_id,
  r.region_name AS canonical_region_name,
  a.*
FROM domestic_interest_attraction_rank AS a
JOIN province_sido_mapping AS p
  ON p.province_name = SUBSTRING_INDEX(a.region_name, ' ', 1)
JOIN dim_region AS r
  ON r.sido_code = p.canonical_sido_code
 AND r.region_name = TRIM(
       SUBSTRING(a.region_name, LOCATE(' ', a.region_name) + 1)
     );

-- 기존 분석 뷰가 여러 단계에서 반복 확장되지 않도록 450개 에피소드를
-- 먼저 물리화합니다. 아래 스냅샷은 스크립트를 다시 실행할 때 갱신됩니다.
DROP VIEW IF EXISTS vw_additional_collection_priority;
DROP VIEW IF EXISTS vw_anomaly_analysis_enriched;
DROP VIEW IF EXISTS vw_anomaly_analysis_enriched_build;
DROP VIEW IF EXISTS vw_anomaly_youtube_context;

DROP TABLE IF EXISTS anomaly_analysis_enriched_snapshot;
DROP TABLE IF EXISTS anomaly_youtube_context_snapshot;
DROP TABLE IF EXISTS anomaly_analysis_ready_snapshot;

CREATE TABLE anomaly_analysis_ready_snapshot
ENGINE=InnoDB
AS
SELECT *
FROM vw_anomaly_analysis_ready;

ALTER TABLE anomaly_analysis_ready_snapshot
  ADD UNIQUE KEY uq_analysis_ready_episode (region_id, episode_no),
  ADD KEY ix_analysis_ready_visitor_peak (visitor_peak_date);

CREATE TABLE anomaly_youtube_context_snapshot
ENGINE=InnoDB
AS
SELECT
  e.region_id,
  e.episode_no,
  COUNT(DISTINCT y.video_id) AS youtube_nearby_video_count,
  MAX(y.view_count) AS youtube_max_view_count,
  MAX(y.like_count) AS youtube_max_like_count,
  MAX(y.comment_count) AS youtube_max_comment_count
FROM anomaly_analysis_ready_snapshot AS e
LEFT JOIN youtube_video AS y
  ON y.region_id = e.region_id
 AND DATE(y.published_at) BETWEEN DATE_SUB(e.visitor_peak_date, INTERVAL 30 DAY)
                              AND DATE_ADD(e.visitor_peak_date, INTERVAL 30 DAY)
GROUP BY e.region_id, e.episode_no;

ALTER TABLE anomaly_youtube_context_snapshot
  ADD UNIQUE KEY uq_youtube_context_episode (region_id, episode_no);

CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY INVOKER
VIEW vw_anomaly_youtube_context AS
SELECT *
FROM anomaly_youtube_context_snapshot;

-- 복합 CTE 뷰를 현재월/전월로 두 번 펼칠 때 발생할 수 있는 MySQL 8.0의
-- 내부 임시 테이블 오류를 피하기 위해 월별 요약을 먼저 물리화합니다.
DROP TABLE IF EXISTS datalab_detail_monthly_summary_snapshot;

CREATE TABLE datalab_detail_monthly_summary_snapshot
ENGINE=InnoDB
AS
SELECT *
FROM vw_datalab_detail_monthly_summary;

ALTER TABLE datalab_detail_monthly_summary_snapshot
  ADD PRIMARY KEY (canonical_region_id, period_start),
  ADD KEY ix_detail_summary_snapshot_period (period_start);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_analysis_enriched_build AS
SELECT
  a.*,

  d.companion_mentions AS detail_companion_mentions,
  d.companion_type_count AS detail_companion_type_count,
  d.top_companion_type AS detail_top_companion_type,
  d.top_companion_mentions AS detail_top_companion_mentions,
  d.travel_mentions AS detail_travel_mentions,
  d.travel_type_count AS detail_travel_type_count,
  d.top_travel_type AS detail_top_travel_type,
  d.top_travel_mentions AS detail_top_travel_mentions,
  d.destination_searches AS detail_destination_searches,
  d.destination_type_count AS detail_destination_type_count,
  d.top_destination_type AS detail_top_destination_type,
  d.top_destination_searches AS detail_top_destination_searches,
  d.top_domestic_industry AS detail_top_domestic_industry,
  d.top_domestic_industry_spend AS detail_top_domestic_industry_spend,
  d.top_outsider_industry AS detail_top_outsider_industry,
  d.top_outsider_industry_spend AS detail_top_outsider_industry_spend,

  CASE
    WHEN d_prev.companion_mentions IS NULL OR d_prev.companion_mentions=0
      OR d.companion_mentions IS NULL THEN NULL
    ELSE (d.companion_mentions-d_prev.companion_mentions)
         / d_prev.companion_mentions*100
  END AS detail_companion_mentions_mom_pct,
  CASE
    WHEN d_prev.travel_mentions IS NULL OR d_prev.travel_mentions=0
      OR d.travel_mentions IS NULL THEN NULL
    ELSE (d.travel_mentions-d_prev.travel_mentions)
         / d_prev.travel_mentions*100
  END AS detail_travel_mentions_mom_pct,
  CASE
    WHEN d_prev.destination_searches IS NULL OR d_prev.destination_searches=0
      OR d.destination_searches IS NULL THEN NULL
    ELSE (d.destination_searches-d_prev.destination_searches)
         / d_prev.destination_searches*100
  END AS detail_destination_searches_mom_pct,

  av.attraction_count,
  av.total_visitors AS attraction_total_visitors,
  av.top_attraction_name,
  av.top_attraction_visitors,
  CASE
    WHEN av_prev.total_visitors IS NULL OR av_prev.total_visitors=0
      OR av.total_visitors IS NULL THEN NULL
    ELSE (av.total_visitors-av_prev.total_visitors)
         / av_prev.total_visitors*100
  END AS attraction_visitors_mom_pct,

  COALESCE(y.youtube_nearby_video_count, 0) AS youtube_nearby_video_count,
  y.youtube_max_view_count,
  y.youtube_max_like_count,
  y.youtube_max_comment_count,
  COALESCE(c.observed_case_count, 0) AS observed_case_count,

  ((d.companion_mentions IS NOT NULL)
   + (d.travel_mentions IS NOT NULL)
   + (d.destination_searches IS NOT NULL)
   + (d.outsider_spend_krw_thousand IS NOT NULL)
   + (av.total_visitors IS NOT NULL)
   + (COALESCE(y.youtube_nearby_video_count,0) > 0))
    AS enriched_feature_count,
  CASE
    WHEN d.canonical_region_id IS NOT NULL AND av.canonical_region_id IS NOT NULL
      THEN 'datalab_and_attraction'
    WHEN d.canonical_region_id IS NOT NULL THEN 'datalab_detail_only'
    WHEN av.canonical_region_id IS NOT NULL THEN 'attraction_only'
    ELSE 'no_new_detail'
  END AS enriched_data_status
FROM anomaly_analysis_ready_snapshot AS a
LEFT JOIN datalab_detail_monthly_summary_snapshot AS d
  ON d.canonical_region_id = a.region_id
 AND d.period_start = STR_TO_DATE(
       DATE_FORMAT(a.visitor_peak_date, '%Y-%m-01'), '%Y-%m-%d')
LEFT JOIN datalab_detail_monthly_summary_snapshot AS d_prev
  ON d_prev.canonical_region_id = a.region_id
 AND d_prev.period_start = DATE_SUB(
       STR_TO_DATE(DATE_FORMAT(a.visitor_peak_date, '%Y-%m-01'), '%Y-%m-%d'),
       INTERVAL 1 MONTH)
LEFT JOIN attraction_visitors_monthly_canonical AS av
  ON av.canonical_region_id = a.region_id
 AND av.period_start = STR_TO_DATE(
       DATE_FORMAT(a.visitor_peak_date, '%Y-%m-01'), '%Y-%m-%d')
LEFT JOIN attraction_visitors_monthly_canonical AS av_prev
  ON av_prev.canonical_region_id = a.region_id
 AND av_prev.period_start = DATE_SUB(
       STR_TO_DATE(DATE_FORMAT(a.visitor_peak_date, '%Y-%m-01'), '%Y-%m-%d'),
       INTERVAL 1 MONTH)
LEFT JOIN anomaly_youtube_context_snapshot AS y
  ON y.region_id = a.region_id
 AND y.episode_no = a.episode_no
LEFT JOIN (
  SELECT canonical_region_id, COUNT(*) AS observed_case_count
  FROM vw_observed_visitors_case_canonical
  GROUP BY canonical_region_id
) AS c
  ON c.canonical_region_id = a.region_id;

CREATE TABLE anomaly_analysis_enriched_snapshot
ENGINE=InnoDB
AS
SELECT *
FROM vw_anomaly_analysis_enriched_build;

ALTER TABLE anomaly_analysis_enriched_snapshot
  ADD UNIQUE KEY uq_analysis_enriched_episode (region_id, episode_no),
  ADD KEY ix_analysis_enriched_visitor_peak (visitor_peak_date),
  ADD KEY ix_analysis_enriched_status (explanation_status);

CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY INVOKER
VIEW vw_anomaly_analysis_enriched AS
SELECT *
FROM anomaly_analysis_enriched_snapshot;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_additional_collection_priority AS
SELECT
  e.region_id,
  e.region_name,
  e.episode_no,
  e.episode_start,
  e.episode_end,
  e.search_peak_date,
  e.visitor_peak_date,
  e.peak_anomaly_score,
  e.peak_naver_ratio,
  e.peak_visitor_ratio,
  e.explanation_status,
  e.auto_cause_type,
  e.auto_confidence,
  e.evidence_title,
  e.enriched_feature_count,
  e.enriched_data_status,
  e.detail_top_companion_type,
  e.detail_top_travel_type,
  e.detail_top_destination_type,
  e.detail_top_outsider_industry,
  e.top_attraction_name,
  e.attraction_visitors_mom_pct,
  e.youtube_nearby_video_count,
  CASE
    WHEN e.explanation_status='not_researched'
         AND e.peak_anomaly_score >= 6 THEN 'P1'
    WHEN e.explanation_status='researched_unresolved'
         AND e.peak_anomaly_score >= 7 THEN 'P1'
    WHEN e.explanation_status IN ('not_researched','researched_unresolved') THEN 'P2'
    ELSE 'P3'
  END AS collection_priority,
  ROUND(
    COALESCE(e.peak_anomaly_score,0)*10
    + CASE e.explanation_status
        WHEN 'not_researched' THEN 40
        WHEN 'researched_unresolved' THEN 30
        WHEN 'strong_external_candidate' THEN 18
        WHEN 'possible_external_candidate' THEN 12
        ELSE 0
      END
    + CASE WHEN e.enriched_data_status='no_new_detail' THEN 10 ELSE 0 END
    + CASE WHEN e.youtube_nearby_video_count=0 THEN 3 ELSE 0 END,
    2
  ) AS collection_priority_score,
  CASE
    WHEN e.explanation_status='not_researched'
      THEN '뉴스·블로그·지자체 공식자료 신규 수집'
    WHEN e.explanation_status='researched_unresolved'
      THEN '행사명·재난·교통·촬영지 키워드로 검색 확장'
    WHEN e.explanation_status IN ('strong_external_candidate','possible_external_candidate')
      THEN '기존 상위 근거의 날짜·지역·원인 수동 검증'
    ELSE '추가 수집 보류'
  END AS recommended_action,
  NULLIF(CONCAT_WS(', ',
    CASE WHEN e.enriched_data_status='no_new_detail' THEN 'DataLab 세부지표 없음' END,
    CASE WHEN e.attraction_total_visitors IS NULL THEN '관광지 입장객 없음' END,
    CASE WHEN e.youtube_nearby_video_count=0 THEN 'YouTube 근거 없음' END
  ), '') AS data_gap_hint,
  CONCAT(
    e.region_name, ' ', DATE_FORMAT(e.visitor_peak_date, '%Y년 %m월'),
    ' 축제 행사 관광 재난 교통 촬영지'
  ) AS suggested_search_query
FROM vw_anomaly_analysis_enriched AS e
WHERE e.explanation_status IN (
  'not_researched', 'researched_unresolved',
  'strong_external_candidate', 'possible_external_candidate'
);
