SET NAMES utf8mb4;
USE tour_earlywarning;

-- 팀 분석용 최종 뷰: 이상 에피소드, 달력/기존 이벤트, 외부 검색 근거,
-- 데이터랩 월별 맥락과 전월 대비 변화를 에피소드 한 행으로 통합합니다.
CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_analysis_ready AS
SELECT
  a.region_id,
  a.region_name,
  a.episode_no,
  a.episode_start,
  a.episode_end,
  a.candidate_days,
  a.search_peak_date,
  a.peak_date AS visitor_peak_date,
  a.search_to_visit_lag_days,

  a.peak_anomaly_score,
  a.peak_naver_z,
  a.peak_visitor_z,
  a.peak_naver_ratio,
  a.peak_visitor_ratio,

  a.matched_event_count,
  a.matched_event_names,
  a.matched_calendar_days,
  a.calendar_effect_names,
  a.calendar_effect_types,
  a.review_status AS original_review_status,

  CASE WHEN e.evidence_id IS NULL THEN 0 ELSE 1 END
    AS external_evidence_collected,
  e.evidence_id,
  e.search_type AS evidence_search_type,
  e.auto_cause_type,
  e.auto_confidence,
  e.evidence_status,
  e.analysis_rank_score AS evidence_rank_score,
  e.evidence_title,
  e.evidence_description,
  e.source_domain AS evidence_source_domain,
  e.evidence_url,
  e.published_date AS evidence_published_date,
  e.days_from_peak AS evidence_days_from_visitor_peak,
  e.is_official_domain AS evidence_is_official_domain,

  CASE
    WHEN a.review_status = 'event_matched' THEN 'verified_event'
    WHEN a.review_status = 'calendar_related' THEN 'calendar_related'
    WHEN e.evidence_status = 'verified' THEN 'verified_external_evidence'
    WHEN e.auto_confidence = 'high' THEN 'strong_external_candidate'
    WHEN e.auto_confidence = 'medium' THEN 'possible_external_candidate'
    WHEN e.evidence_id IS NOT NULL THEN 'researched_unresolved'
    ELSE 'not_researched'
  END AS explanation_status,

  d.period_start AS datalab_period_start,
  d.visitors AS datalab_visitors,
  d.visitors_prev_year AS datalab_visitors_prev_year,
  d.visitors_yoy_pct AS datalab_visitors_yoy_pct,
  d.unique_visitors AS datalab_unique_visitors,
  d.overnight_guest_pct AS datalab_overnight_guest_pct,
  d.sns_mentions AS datalab_sns_mentions,
  d.avg_nights AS datalab_avg_nights,
  d.stay_minutes AS datalab_stay_minutes,
  d.overnight_visit_pct AS datalab_overnight_visit_pct,
  d.lodging_searches AS datalab_lodging_searches,
  d.lodging_searches_yoy_pct AS datalab_lodging_searches_yoy_pct,
  d.navigation_searches AS datalab_navigation_searches,
  d.tourism_spend_domestic_krw_thousand
    AS datalab_domestic_spend_krw_thousand,
  d.tourism_spend_outsider_krw_thousand
    AS datalab_outsider_spend_krw_thousand,
  d.tourism_spend_local_krw_thousand
    AS datalab_local_spend_krw_thousand,
  d.local_currency_spend_krw_thousand
    AS datalab_local_currency_spend_krw_thousand,
  d.is_aggregated_region AS datalab_is_aggregated_region,
  d.unique_visitors_available AS datalab_unique_visitors_available,

  CASE
    WHEN d_prev.visitors IS NULL OR d_prev.visitors = 0
      OR d.visitors IS NULL THEN NULL
    ELSE (d.visitors - d_prev.visitors) / d_prev.visitors * 100
  END AS datalab_visitors_mom_pct,
  CASE
    WHEN d_prev.sns_mentions IS NULL OR d_prev.sns_mentions = 0
      OR d.sns_mentions IS NULL THEN NULL
    ELSE (d.sns_mentions - d_prev.sns_mentions)
         / d_prev.sns_mentions * 100
  END AS datalab_sns_mentions_mom_pct,
  CASE
    WHEN d_prev.navigation_searches IS NULL
      OR d_prev.navigation_searches = 0
      OR d.navigation_searches IS NULL THEN NULL
    ELSE (d.navigation_searches - d_prev.navigation_searches)
         / d_prev.navigation_searches * 100
  END AS datalab_navigation_searches_mom_pct,
  CASE
    WHEN d_prev.lodging_searches IS NULL OR d_prev.lodging_searches = 0
      OR d.lodging_searches IS NULL THEN NULL
    ELSE (d.lodging_searches - d_prev.lodging_searches)
         / d_prev.lodging_searches * 100
  END AS datalab_lodging_searches_mom_pct,
  CASE
    WHEN d_prev.tourism_spend_outsider_krw_thousand IS NULL
      OR d_prev.tourism_spend_outsider_krw_thousand = 0
      OR d.tourism_spend_outsider_krw_thousand IS NULL THEN NULL
    ELSE (d.tourism_spend_outsider_krw_thousand
          - d_prev.tourism_spend_outsider_krw_thousand)
         / d_prev.tourism_spend_outsider_krw_thousand * 100
  END AS datalab_outsider_spend_mom_pct
FROM vw_anomaly_episode_review AS a
LEFT JOIN vw_anomaly_episode_top_evidence AS e
  ON e.region_id = a.region_id
 AND e.episode_no = a.episode_no
LEFT JOIN vw_datalab_canonical_monthly AS d
  ON d.canonical_region_id = a.region_id
 AND d.period_start = STR_TO_DATE(
       DATE_FORMAT(a.peak_date, '%Y-%m-01'), '%Y-%m-%d')
LEFT JOIN vw_datalab_canonical_monthly AS d_prev
  ON d_prev.canonical_region_id = a.region_id
 AND d_prev.period_start = DATE_SUB(
       STR_TO_DATE(DATE_FORMAT(a.peak_date, '%Y-%m-01'), '%Y-%m-%d'),
       INTERVAL 1 MONTH);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_analysis_explained AS
SELECT *
FROM vw_anomaly_analysis_ready
WHERE explanation_status IN (
  'verified_event',
  'calendar_related',
  'verified_external_evidence',
  'strong_external_candidate',
  'possible_external_candidate'
);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_analysis_unresolved AS
SELECT *
FROM vw_anomaly_analysis_ready
WHERE explanation_status IN ('researched_unresolved', 'not_researched');

SELECT 'analysis_ready' AS check_name,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       MIN(episode_start) AS date_min,
       MAX(episode_end) AS date_max
FROM vw_anomaly_analysis_ready;

SELECT explanation_status, COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions
FROM vw_anomaly_analysis_ready
GROUP BY explanation_status
ORDER BY FIELD(
  explanation_status,
  'verified_event', 'calendar_related', 'verified_external_evidence',
  'strong_external_candidate', 'possible_external_candidate',
  'researched_unresolved', 'not_researched'
);

SELECT 'duplicate_episode_keys' AS check_name, COUNT(*) AS actual
FROM (
  SELECT region_id, episode_no
  FROM vw_anomaly_analysis_ready
  GROUP BY region_id, episode_no
  HAVING COUNT(*) > 1
) AS duplicated;

SELECT 'datalab_coverage' AS check_name,
       SUM(datalab_period_start IS NOT NULL) AS matched_episodes,
       SUM(datalab_period_start IS NULL) AS missing_episodes,
       SUM(datalab_sns_mentions IS NULL) AS missing_sns,
       SUM(datalab_navigation_searches IS NULL) AS missing_navigation,
       SUM(datalab_outsider_spend_krw_thousand IS NULL) AS missing_spend
FROM vw_anomaly_analysis_ready;

SELECT region_name, search_peak_date, visitor_peak_date,
       ROUND(peak_anomaly_score, 3) AS anomaly_score,
       ROUND(peak_naver_ratio, 3) AS naver_ratio,
       ROUND(peak_visitor_ratio, 3) AS visitor_ratio,
       explanation_status, auto_cause_type, auto_confidence,
       evidence_title
FROM vw_anomaly_analysis_ready
WHERE explanation_status IN (
  'strong_external_candidate', 'possible_external_candidate'
)
ORDER BY peak_anomaly_score DESC
LIMIT 20;
