CREATE TABLE IF NOT EXISTS final_collection_run (
    run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_name VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    status ENUM('running','success','failed') NOT NULL,
    rows_received BIGINT NOT NULL DEFAULT 0,
    rows_upserted BIGINT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    PRIMARY KEY (run_id),
    KEY idx_final_run_source_time (source_name, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS raw_tourapi_festival (
    festival_key CHAR(64) NOT NULL,
    content_id VARCHAR(50) NOT NULL,
    title VARCHAR(500) NULL,
    event_start_date DATE NULL,
    event_end_date DATE NULL,
    address1 VARCHAR(500) NULL,
    address2 VARCHAR(500) NULL,
    area_code VARCHAR(20) NULL,
    sigungu_code VARCHAR(20) NULL,
    map_x DECIMAL(15,10) NULL,
    map_y DECIMAL(15,10) NULL,
    telephone VARCHAR(500) NULL,
    first_image TEXT NULL,
    modified_time VARCHAR(30) NULL,
    source_api VARCHAR(50) NOT NULL,
    raw_json JSON NOT NULL,
    collected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (festival_key),
    KEY idx_festival_dates (event_start_date, event_end_date),
    KEY idx_festival_area (area_code, sigungu_code),
    KEY idx_festival_content (content_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS raw_kma_asos_daily (
    station_id VARCHAR(10) NOT NULL,
    observed_date DATE NOT NULL,
    station_name VARCHAR(100) NULL,
    avg_temperature_c DOUBLE NULL,
    min_temperature_c DOUBLE NULL,
    max_temperature_c DOUBLE NULL,
    precipitation_mm DOUBLE NULL,
    avg_humidity_pct DOUBLE NULL,
    max_wind_speed_ms DOUBLE NULL,
    max_instant_wind_speed_ms DOUBLE NULL,
    snow_depth_cm DOUBLE NULL,
    weather_summary TEXT NULL,
    raw_json JSON NOT NULL,
    collected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (station_id, observed_date),
    KEY idx_asos_observed_date (observed_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS raw_kma_warning (
    warning_key CHAR(64) NOT NULL,
    station_id VARCHAR(10) NULL,
    announcement_sequence VARCHAR(20) NULL,
    announcement_at DATETIME NULL,
    title VARCHAR(1000) NULL,
    raw_json JSON NOT NULL,
    collected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (warning_key),
    KEY idx_warning_announcement (announcement_at),
    KEY idx_warning_station (station_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS collection_freeze_snapshot (
    snapshot_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    frozen_at_kst DATETIME NOT NULL,
    cutoff_at_kst DATETIME NOT NULL,
    manifest_sha256 CHAR(64) NOT NULL,
    note VARCHAR(500) NULL,
    PRIMARY KEY (snapshot_id),
    KEY idx_freeze_time (frozen_at_kst)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

