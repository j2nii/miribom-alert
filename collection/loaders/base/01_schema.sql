-- 야호레이더 MySQL 8.0+/8.4 스키마
-- 실행: mysql -u root -p < 01_schema.sql

CREATE DATABASE IF NOT EXISTS yaho_radar
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE yaho_radar;

CREATE TABLE IF NOT EXISTS source_file (
  source_file_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  file_name VARCHAR(255) NOT NULL,
  sha256 CHAR(64) NOT NULL,
  byte_size BIGINT UNSIGNED NOT NULL,
  row_count BIGINT UNSIGNED NULL,
  loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note VARCHAR(500) NULL,
  PRIMARY KEY (source_file_id),
  UNIQUE KEY uq_source_file_hash (sha256)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS source_archive_entry (
  source_file_id BIGINT UNSIGNED NOT NULL,
  entry_name VARCHAR(500) NOT NULL,
  byte_size BIGINT UNSIGNED NOT NULL,
  compressed_size BIGINT UNSIGNED NULL,
  crc32 CHAR(8) NULL,
  PRIMARY KEY (source_file_id, entry_name),
  CONSTRAINT fk_archive_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_region (
  region_id VARCHAR(20) NOT NULL,
  region_name VARCHAR(100) NOT NULL,
  sido_code VARCHAR(2) NULL,
  region_type VARCHAR(30) NOT NULL DEFAULT 'basic',
  is_synthetic TINYINT(1) NOT NULL DEFAULT 0,
  active_from DATE NULL,
  active_to DATE NULL,
  PRIMARY KEY (region_id),
  KEY ix_region_name (region_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS region_alias (
  source_system VARCHAR(50) NOT NULL,
  source_region_key VARCHAR(100) NOT NULL,
  canonical_region_id VARCHAR(20) NOT NULL,
  valid_from DATE NOT NULL DEFAULT '1900-01-01',
  valid_to DATE NULL,
  mapping_reason VARCHAR(255) NULL,
  PRIMARY KEY (source_system, source_region_key, valid_from),
  KEY ix_alias_canonical (canonical_region_id),
  CONSTRAINT fk_alias_region FOREIGN KEY (canonical_region_id)
    REFERENCES dim_region(region_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stg_region_master (
  source_region_id VARCHAR(20) NOT NULL,
  source_region_name VARCHAR(100) NOT NULL,
  sido_code VARCHAR(2) NULL,
  reform_note VARCHAR(255) NULL,
  source_file_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (source_region_id),
  CONSTRAINT fk_master_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stg_region_scope (
  source_region_id VARCHAR(20) NOT NULL,
  keep_flag TINYINT(1) NOT NULL,
  region_level VARCHAR(50) NULL,
  exclusion_reason VARCHAR(255) NULL,
  source_file_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (source_region_id),
  CONSTRAINT fk_scope_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fact_signal (
  region_id VARCHAR(20) NOT NULL,
  source_region_id VARCHAR(20) NOT NULL,
  observed_date DATE NOT NULL,
  metric VARCHAR(50) NOT NULL,
  segment VARCHAR(30) NOT NULL DEFAULT '',
  value DECIMAL(24,8) NOT NULL,
  source_system VARCHAR(50) NOT NULL,
  granularity ENUM('day','week','month') NOT NULL,
  source_file_id BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (region_id, observed_date, metric, segment, source_system),
  KEY ix_signal_metric_date (metric, observed_date),
  KEY ix_signal_source_region (source_region_id),
  CONSTRAINT fk_signal_region FOREIGN KEY (region_id)
    REFERENCES dim_region(region_id),
  CONSTRAINT fk_signal_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS youtube_video (
  video_id VARCHAR(32) NOT NULL,
  region_id VARCHAR(20) NOT NULL,
  source_region_name VARCHAR(100) NOT NULL,
  keyword_text VARCHAR(255) NULL,
  published_at DATETIME NOT NULL,
  title TEXT NOT NULL,
  channel_name VARCHAR(255) NULL,
  view_rank INT NULL,
  window_month CHAR(7) NULL,
  view_count BIGINT UNSIGNED NULL,
  like_count BIGINT UNSIGNED NULL,
  comment_count BIGINT UNSIGNED NULL,
  source_file_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (video_id),
  KEY ix_youtube_region_time (region_id, published_at),
  CONSTRAINT fk_youtube_region FOREIGN KEY (region_id)
    REFERENCES dim_region(region_id),
  CONSTRAINT fk_youtube_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS datalab_monthly_panel (
  source_region_name VARCHAR(100) NOT NULL,
  period_start DATE NOT NULL,
  canonical_region_id VARCHAR(20) NULL,
  visitors DECIMAL(24,8) NULL,
  visitors_prev_year DECIMAL(24,8) NULL,
  visitors_yoy_pct DECIMAL(24,8) NULL,
  unique_visitors DECIMAL(24,8) NULL,
  overnight_guest_pct DECIMAL(24,8) NULL,
  sns_mentions DECIMAL(24,8) NULL,
  avg_nights DECIMAL(24,8) NULL,
  stay_minutes DECIMAL(24,8) NULL,
  stay_minutes_national DECIMAL(24,8) NULL,
  overnight_visit_pct DECIMAL(24,8) NULL,
  overnight_visit_pct_national DECIMAL(24,8) NULL,
  lodging_searches DECIMAL(24,8) NULL,
  lodging_searches_prev DECIMAL(24,8) NULL,
  lodging_searches_yoy_pct DECIMAL(24,8) NULL,
  navigation_searches DECIMAL(24,8) NULL,
  tourism_spend_domestic_krw_thousand DECIMAL(24,8) NULL,
  tourism_spend_outsider_krw_thousand DECIMAL(24,8) NULL,
  tourism_spend_local_krw_thousand DECIMAL(24,8) NULL,
  spend_share_domestic_pct DECIMAL(24,8) NULL,
  spend_share_outsider_pct DECIMAL(24,8) NULL,
  spend_share_local_pct DECIMAL(24,8) NULL,
  local_currency_spend_krw_thousand DECIMAL(24,8) NULL,
  stay_1night_pct DECIMAL(24,8) NULL,
  stay_2nights_pct DECIMAL(24,8) NULL,
  stay_3nights_pct DECIMAL(24,8) NULL,
  stay_4nights_pct DECIMAL(24,8) NULL,
  stay_5nights_pct DECIMAL(24,8) NULL,
  stay_6nights_pct DECIMAL(24,8) NULL,
  stay_7plus_nights_pct DECIMAL(24,8) NULL,
  stay_type_total_pct DECIMAL(24,8) NULL,
  source_file_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (source_region_name, period_start),
  KEY ix_datalab_canonical_period (canonical_region_id, period_start),
  CONSTRAINT fk_datalab_region FOREIGN KEY (canonical_region_id)
    REFERENCES dim_region(region_id),
  CONSTRAINT fk_datalab_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

-- events.json은 현재 없으므로 테이블만 만들고 비워 둔다.
CREATE TABLE IF NOT EXISTS event (
  event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  event_key VARCHAR(100) NOT NULL,
  region_id VARCHAR(20) NOT NULL,
  event_name VARCHAR(255) NOT NULL,
  event_type VARCHAR(50) NULL,
  evidence_url TEXT NULL,
  evidence_note TEXT NULL,
  source_file_id BIGINT UNSIGNED NULL,
  PRIMARY KEY (event_id),
  UNIQUE KEY uq_event_key (event_key),
  CONSTRAINT fk_event_region FOREIGN KEY (region_id)
    REFERENCES dim_region(region_id),
  CONSTRAINT fk_event_file FOREIGN KEY (source_file_id)
    REFERENCES source_file(source_file_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS event_point (
  event_id BIGINT UNSIGNED NOT NULL,
  point_type ENUM('T0','Ta','Tb','end') NOT NULL,
  point_date DATE NOT NULL,
  definition_note VARCHAR(500) NULL,
  PRIMARY KEY (event_id, point_type),
  CONSTRAINT fk_event_point_event FOREIGN KEY (event_id)
    REFERENCES event(event_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS crawl_run (
  crawl_run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  crawler_name VARCHAR(100) NOT NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  status ENUM('running','success','partial','failed') NOT NULL DEFAULT 'running',
  target_count INT UNSIGNED NOT NULL DEFAULT 0,
  success_count INT UNSIGNED NOT NULL DEFAULT 0,
  failure_count INT UNSIGNED NOT NULL DEFAULT 0,
  error_summary TEXT NULL,
  PRIMARY KEY (crawl_run_id),
  KEY ix_crawl_run_name_time (crawler_name, started_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS crawl_checkpoint (
  crawler_name VARCHAR(100) NOT NULL,
  target_key VARCHAR(255) NOT NULL,
  period_key VARCHAR(50) NOT NULL DEFAULT '',
  status ENUM('pending','success','failed','source_unavailable') NOT NULL,
  attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
  last_attempt_at DATETIME NULL,
  last_error TEXT NULL,
  payload_sha256 CHAR(64) NULL,
  PRIMARY KEY (crawler_name, target_key, period_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS raw_payload (
  raw_payload_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  crawl_run_id BIGINT UNSIGNED NOT NULL,
  crawler_name VARCHAR(100) NOT NULL,
  target_key VARCHAR(255) NOT NULL,
  period_key VARCHAR(50) NOT NULL DEFAULT '',
  request_url TEXT NULL,
  fetched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  http_status SMALLINT UNSIGNED NULL,
  payload_json JSON NULL,
  payload_text LONGTEXT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  PRIMARY KEY (raw_payload_id),
  UNIQUE KEY uq_payload_hash (payload_sha256),
  KEY ix_payload_target (crawler_name, target_key, period_key),
  CONSTRAINT fk_payload_run FOREIGN KEY (crawl_run_id)
    REFERENCES crawl_run(crawl_run_id)
) ENGINE=InnoDB;
