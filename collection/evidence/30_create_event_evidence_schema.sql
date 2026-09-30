SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS event_evidence_run (
  evidence_run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  status ENUM('running','success','partial','failed') NOT NULL DEFAULT 'running',
  target_episodes INT UNSIGNED NOT NULL DEFAULT 0,
  api_calls INT UNSIGNED NOT NULL DEFAULT 0,
  stored_results INT UNSIGNED NOT NULL DEFAULT 0,
  failure_count INT UNSIGNED NOT NULL DEFAULT 0,
  error_summary TEXT NULL,
  PRIMARY KEY (evidence_run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS event_evidence_checkpoint (
  region_id VARCHAR(20) NOT NULL,
  episode_no BIGINT NOT NULL,
  search_type ENUM('news','blog','webkr') NOT NULL,
  status ENUM('success','failed') NOT NULL,
  attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
  result_count INT UNSIGNED NOT NULL DEFAULT 0,
  last_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_error TEXT NULL,
  PRIMARY KEY (region_id, episode_no, search_type)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS event_evidence_candidate (
  evidence_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  evidence_run_id BIGINT UNSIGNED NOT NULL,
  region_id VARCHAR(20) NOT NULL,
  episode_no BIGINT NOT NULL,
  peak_date DATE NOT NULL,
  search_type ENUM('news','blog','webkr') NOT NULL,
  query_text VARCHAR(500) NOT NULL,
  result_rank SMALLINT UNSIGNED NOT NULL,
  title VARCHAR(1000) NOT NULL,
  description TEXT NULL,
  result_url VARCHAR(2000) NOT NULL,
  original_url VARCHAR(2000) NULL,
  source_domain VARCHAR(255) NULL,
  published_date DATE NULL,
  days_from_peak INT NULL,
  is_official_domain TINYINT(1) NOT NULL DEFAULT 0,
  relevance_score DECIMAL(10,3) NOT NULL DEFAULT 0,
  result_hash CHAR(64) NOT NULL,
  raw_json JSON NULL,
  collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (evidence_id),
  UNIQUE KEY uq_event_evidence_result
    (region_id, episode_no, search_type, result_hash),
  KEY ix_event_evidence_episode (region_id, episode_no, relevance_score),
  KEY ix_event_evidence_domain (is_official_domain, relevance_score),
  CONSTRAINT fk_event_evidence_run FOREIGN KEY (evidence_run_id)
    REFERENCES event_evidence_run(evidence_run_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS event_evidence_decision (
  evidence_id BIGINT UNSIGNED NOT NULL,
  decision ENUM('pending','accepted','rejected','duplicate') NOT NULL
    DEFAULT 'pending',
  event_name VARCHAR(255) NULL,
  event_type VARCHAR(50) NULL,
  event_start DATE NULL,
  event_end DATE NULL,
  review_note TEXT NULL,
  reviewed_at DATETIME NULL,
  PRIMARY KEY (evidence_id),
  CONSTRAINT fk_event_evidence_decision FOREIGN KEY (evidence_id)
    REFERENCES event_evidence_candidate(evidence_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_event_research_priority AS
WITH date_cluster AS (
  SELECT peak_date,
         COUNT(*) AS same_peak_date_episodes,
         COUNT(DISTINCT region_id) AS same_peak_date_regions
  FROM vw_event_research_queue
  GROUP BY peak_date
),
week_cluster AS (
  SELECT YEARWEEK(peak_date, 3) AS peak_yearweek,
         COUNT(*) AS same_peak_week_episodes,
         COUNT(DISTINCT region_id) AS same_peak_week_regions
  FROM vw_event_research_queue
  GROUP BY YEARWEEK(peak_date, 3)
),
recurrence AS (
  SELECT region_id,
         MONTH(peak_date) AS peak_month,
         COUNT(*) AS same_region_month_episodes,
         COUNT(DISTINCT YEAR(peak_date)) AS same_region_month_years
  FROM vw_event_research_queue
  GROUP BY region_id, MONTH(peak_date)
),
features AS (
  SELECT
    q.*,
    d.same_peak_date_episodes,
    d.same_peak_date_regions,
    w.same_peak_week_episodes,
    w.same_peak_week_regions,
    r.same_region_month_episodes,
    r.same_region_month_years,
    CASE
      WHEN d.same_peak_date_regions >= 5
       AND r.same_region_month_years >= 2 THEN 'common_and_seasonal'
      WHEN d.same_peak_date_regions >= 5 THEN 'common_date_cluster'
      WHEN r.same_region_month_years >= 2 THEN 'seasonal_recurrence'
      ELSE 'local_specific'
    END AS pattern_hint
  FROM vw_event_research_queue AS q
  JOIN date_cluster AS d ON d.peak_date = q.peak_date
  JOIN week_cluster AS w
    ON w.peak_yearweek = YEARWEEK(q.peak_date, 3)
  JOIN recurrence AS r
    ON r.region_id = q.region_id
   AND r.peak_month = MONTH(q.peak_date)
),
scored AS (
  SELECT
    f.*,
    f.peak_anomaly_score
      + CASE WHEN f.pattern_hint = 'local_specific' THEN 2.0 ELSE 0 END
      + CASE WHEN f.peak_naver_ratio >= 5.0 THEN 1.0 ELSE 0 END
      + CASE WHEN f.peak_visitor_ratio >= 2.0 THEN 0.5 ELSE 0 END
      - CASE WHEN f.same_peak_date_regions >= 5 THEN 1.5 ELSE 0 END
      AS research_priority_score
  FROM features AS f
)
SELECT
  s.*,
  CASE
    WHEN s.pattern_hint = 'local_specific'
     AND (s.peak_anomaly_score >= 6.5 OR s.peak_naver_ratio >= 5.0)
      THEN 'P1'
    WHEN s.pattern_hint <> 'common_date_cluster'
      OR s.peak_anomaly_score >= 6.0
      THEN 'P2'
    ELSE 'P3'
  END AS research_priority
FROM scored AS s;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_event_evidence_review_queue AS
WITH ranked AS (
  SELECT
    e.*,
    COALESCE(d.decision, 'pending') AS decision,
    d.event_name,
    d.event_type,
    d.event_start,
    d.event_end,
    d.review_note,
    ROW_NUMBER() OVER (
      PARTITION BY e.region_id, e.episode_no
      ORDER BY e.relevance_score DESC,
               e.is_official_domain DESC,
               e.result_rank,
               e.evidence_id
    ) AS evidence_rank_in_episode
  FROM event_evidence_candidate AS e
  LEFT JOIN event_evidence_decision AS d
    ON d.evidence_id = e.evidence_id
)
SELECT
  r.*,
  p.region_name,
  p.episode_start,
  p.episode_end,
  p.search_peak_date,
  p.search_to_visit_lag_days,
  p.pattern_hint,
  p.research_priority,
  p.research_priority_score
FROM ranked AS r
JOIN vw_event_research_priority AS p
  ON p.region_id = r.region_id
 AND p.episode_no = r.episode_no;

SELECT research_priority,
       pattern_hint,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions
FROM vw_event_research_priority
GROUP BY research_priority, pattern_hint
ORDER BY research_priority, episodes DESC;

