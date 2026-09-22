-- Base tables for daily tourism anomaly detection.
-- Existing fact tables are not modified.

SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS analysis_calendar (
  calendar_date DATE NOT NULL,
  calendar_year SMALLINT NOT NULL,
  calendar_month TINYINT NOT NULL,
  day_of_month TINYINT NOT NULL,
  day_of_week TINYINT NOT NULL COMMENT '1=Monday, 7=Sunday',
  iso_year_week INT NOT NULL,
  is_weekend TINYINT(1) NOT NULL,
  is_public_holiday TINYINT(1) NOT NULL DEFAULT 0,
  holiday_name VARCHAR(100) NULL,
  PRIMARY KEY (calendar_date),
  KEY ix_calendar_year_month (calendar_year, calendar_month),
  CONSTRAINT ck_calendar_day_of_week CHECK (day_of_week BETWEEN 1 AND 7)
) ENGINE=InnoDB;

-- fact_signal already contains a complete daily date spine. Derived calendar
-- fields are refreshed while manually supplied holiday fields are preserved.
INSERT INTO analysis_calendar
  (calendar_date, calendar_year, calendar_month, day_of_month,
   day_of_week, iso_year_week, is_weekend)
SELECT DISTINCT
       observed_date,
       YEAR(observed_date),
       MONTH(observed_date),
       DAY(observed_date),
       WEEKDAY(observed_date) + 1,
       YEARWEEK(observed_date, 3),
       WEEKDAY(observed_date) IN (5, 6)
FROM fact_signal
ON DUPLICATE KEY UPDATE
  calendar_year = VALUES(calendar_year),
  calendar_month = VALUES(calendar_month),
  day_of_month = VALUES(day_of_month),
  day_of_week = VALUES(day_of_week),
  iso_year_week = VALUES(iso_year_week),
  is_weekend = VALUES(is_weekend);

CREATE TABLE IF NOT EXISTS anomaly_detection_config (
  config_id TINYINT UNSIGNED NOT NULL,
  naver_z_threshold DECIMAL(8,4) NOT NULL,
  visitor_z_threshold DECIMAL(8,4) NOT NULL,
  min_baseline_observations TINYINT UNSIGNED NOT NULL,
  naver_score_weight DECIMAL(8,4) NOT NULL,
  visitor_score_weight DECIMAL(8,4) NOT NULL,
  config_note VARCHAR(500) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (config_id),
  CONSTRAINT ck_anomaly_config_singleton CHECK (config_id = 1),
  CONSTRAINT ck_anomaly_config_weights
    CHECK (naver_score_weight >= 0 AND visitor_score_weight >= 0)
) ENGINE=InnoDB;

INSERT INTO anomaly_detection_config
  (config_id, naver_z_threshold, visitor_z_threshold,
   min_baseline_observations, naver_score_weight,
   visitor_score_weight, config_note)
VALUES
  (1, 3.0, 2.0, 6, 0.45, 0.55,
   '로그 변환 후 같은 요일 직전 8주 기준. 검색 선행창은 현재일 포함 직전 14일로 고정.')
ON DUPLICATE KEY UPDATE
  config_note = VALUES(config_note);

SELECT 'calendar' AS check_name,
       COUNT(*) AS days_actual,
       MIN(calendar_date) AS date_min,
       MAX(calendar_date) AS date_max
FROM analysis_calendar;

