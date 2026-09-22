-- Daily feature, anomaly score, candidate, and interpretation views.

SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_daily_core_signal AS
WITH signal_pivot AS (
  SELECT
    region_id,
    observed_date,
    MAX(CASE
          WHEN metric = 'interest_naver'
           AND source_system = 'naver_search_trend'
          THEN value
        END) AS naver_interest,
    MAX(CASE
          WHEN metric = 'realization_visitors'
           AND segment = 'external'
          THEN value
        END) AS visitors_external,
    MAX(CASE
          WHEN metric = 'realization_visitors'
           AND segment = 'local'
          THEN value
        END) AS visitors_local,
    MAX(CASE
          WHEN metric = 'realization_visitors'
           AND segment = 'foreign'
          THEN value
        END) AS visitors_foreign
  FROM fact_signal
  WHERE metric IN ('interest_naver', 'realization_visitors')
  GROUP BY region_id, observed_date
),
youtube_daily AS (
  SELECT
    region_id,
    DATE(published_at) AS observed_date,
    COUNT(*) AS youtube_sample_videos,
    SUM(view_count) AS youtube_sample_views
  FROM youtube_video
  GROUP BY region_id, DATE(published_at)
)
SELECT
  s.region_id,
  r.region_name,
  s.observed_date,
  c.calendar_year,
  c.calendar_month,
  c.day_of_week,
  c.is_weekend,
  c.is_public_holiday,
  c.holiday_name,
  s.naver_interest,
  s.visitors_external,
  s.visitors_local,
  s.visitors_foreign,
  COALESCE(y.youtube_sample_videos, 0) AS youtube_sample_videos,
  y.youtube_sample_views
FROM signal_pivot AS s
JOIN dim_region AS r
  ON r.region_id = s.region_id
JOIN analysis_calendar AS c
  ON c.calendar_date = s.observed_date
LEFT JOIN youtube_daily AS y
  ON y.region_id = s.region_id
 AND y.observed_date = s.observed_date
WHERE s.naver_interest IS NOT NULL
  AND s.visitors_external IS NOT NULL;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_daily_anomaly_features AS
WITH log_signal AS (
  SELECT
    s.*,
    LN(1 + s.naver_interest) AS log_naver_interest,
    LN(1 + s.visitors_external) AS log_visitors_external
  FROM vw_daily_core_signal AS s
),
baseline AS (
  SELECT
    l.*,
    COUNT(log_naver_interest) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS naver_baseline_n,
    AVG(log_naver_interest) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS naver_baseline_mean,
    STDDEV_SAMP(log_naver_interest) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS naver_baseline_sd,
    COUNT(log_visitors_external) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS visitor_baseline_n,
    AVG(log_visitors_external) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS visitor_baseline_mean,
    STDDEV_SAMP(log_visitors_external) OVER (
      PARTITION BY region_id, day_of_week
      ORDER BY observed_date
      ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS visitor_baseline_sd
  FROM log_signal AS l
)
SELECT
  b.*,
  CASE
    WHEN naver_baseline_sd IS NULL OR naver_baseline_sd = 0 THEN NULL
    ELSE (log_naver_interest - naver_baseline_mean) / naver_baseline_sd
  END AS naver_z,
  CASE
    WHEN visitor_baseline_sd IS NULL OR visitor_baseline_sd = 0 THEN NULL
    ELSE (log_visitors_external - visitor_baseline_mean) / visitor_baseline_sd
  END AS visitor_z
FROM baseline AS b;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_daily_anomaly_scored AS
WITH lead_signal AS (
  SELECT
    f.*,
    MAX(f.naver_z) OVER (
      PARTITION BY f.region_id
      ORDER BY f.observed_date
      ROWS BETWEEN 14 PRECEDING AND CURRENT ROW
    ) AS naver_z_max_prior_14d
  FROM vw_daily_anomaly_features AS f
)
SELECT
  l.*,
  CASE
    WHEN l.naver_baseline_n >= c.min_baseline_observations
     AND l.naver_z >= c.naver_z_threshold THEN 1 ELSE 0
  END AS is_interest_spike,
  CASE
    WHEN l.visitor_baseline_n >= c.min_baseline_observations
     AND l.visitor_z >= c.visitor_z_threshold THEN 1 ELSE 0
  END AS is_demand_spike,
  CASE
    WHEN l.visitor_baseline_n >= c.min_baseline_observations
     AND l.visitor_z >= c.visitor_z_threshold
     AND l.naver_z_max_prior_14d >= c.naver_z_threshold
    THEN 1 ELSE 0
  END AS is_viral_candidate,
  CASE
    WHEN l.visitor_baseline_n < c.min_baseline_observations
      OR l.naver_baseline_n < c.min_baseline_observations
    THEN NULL
    ELSE
      GREATEST(COALESCE(l.naver_z_max_prior_14d, 0), 0)
        * c.naver_score_weight
      + GREATEST(COALESCE(l.visitor_z, 0), 0)
        * c.visitor_score_weight
  END AS anomaly_score,
  c.naver_z_threshold,
  c.visitor_z_threshold
FROM lead_signal AS l
CROSS JOIN anomaly_detection_config AS c
WHERE c.config_id = 1;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_daily_anomaly_candidates AS
SELECT
  s.*,
  CASE
    WHEN is_viral_candidate = 1 THEN 'viral_candidate'
    WHEN is_interest_spike = 1 AND is_demand_spike = 1 THEN 'same_day_joint_spike'
    WHEN is_interest_spike = 1 THEN 'interest_only'
    WHEN is_demand_spike = 1 THEN 'demand_only'
  END AS candidate_type
FROM vw_daily_anomaly_scored AS s
WHERE is_interest_spike = 1 OR is_demand_spike = 1;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_event_window AS
SELECT
  e.event_id,
  e.event_key,
  e.region_id,
  e.event_name,
  e.event_type,
  e.evidence_url,
  e.evidence_note,
  MAX(CASE WHEN p.point_type = 'T0' THEN p.point_date END) AS t0_date,
  MAX(CASE WHEN p.point_type = 'Ta' THEN p.point_date END) AS ta_date,
  MAX(CASE WHEN p.point_type = 'Tb' THEN p.point_date END) AS tb_date,
  MAX(CASE WHEN p.point_type = 'end' THEN p.point_date END) AS end_date,
  COALESCE(
    MAX(CASE WHEN p.point_type = 'T0' THEN p.point_date END),
    MIN(p.point_date)
  ) AS window_start,
  COALESCE(
    MAX(CASE WHEN p.point_type = 'end' THEN p.point_date END),
    MAX(CASE WHEN p.point_type = 'Tb' THEN p.point_date END),
    MAX(CASE WHEN p.point_type = 'Ta' THEN p.point_date END),
    MAX(CASE WHEN p.point_type = 'T0' THEN p.point_date END),
    MAX(p.point_date)
  ) AS window_end
FROM event AS e
LEFT JOIN event_point AS p
  ON p.event_id = e.event_id
GROUP BY e.event_id, e.event_key, e.region_id, e.event_name, e.event_type,
         e.evidence_url, e.evidence_note;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_candidate_context AS
WITH event_match AS (
  SELECT
    c.region_id,
    c.observed_date,
    COUNT(w.event_id) AS matched_event_count,
    GROUP_CONCAT(DISTINCT w.event_name ORDER BY w.event_name SEPARATOR ' | ')
      AS matched_event_names
  FROM vw_daily_anomaly_candidates AS c
  LEFT JOIN vw_event_window AS w
    ON w.region_id = c.region_id
   AND w.window_start IS NOT NULL
   AND c.observed_date BETWEEN DATE_SUB(w.window_start, INTERVAL 7 DAY)
                           AND DATE_ADD(w.window_end, INTERVAL 14 DAY)
  GROUP BY c.region_id, c.observed_date
)
SELECT
  c.*,
  COALESCE(e.matched_event_count, 0) AS matched_event_count,
  e.matched_event_names,
  d.sns_mentions AS datalab_monthly_sns_mentions,
  d.navigation_searches AS datalab_monthly_navigation_searches,
  d.tourism_spend_outsider_krw_thousand
    AS datalab_monthly_outsider_spend_krw_thousand,
  d.avg_nights AS datalab_monthly_avg_nights
FROM vw_daily_anomaly_candidates AS c
LEFT JOIN event_match AS e
  ON e.region_id = c.region_id
 AND e.observed_date = c.observed_date
LEFT JOIN vw_datalab_canonical_monthly AS d
  ON d.canonical_region_id = c.region_id
 AND d.period_start = STR_TO_DATE(
      DATE_FORMAT(c.observed_date, '%Y-%m-01'), '%Y-%m-%d');
