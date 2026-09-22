USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS ingest_source_file (
    source_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_kind VARCHAR(50) NOT NULL,
    source_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    byte_size BIGINT UNSIGNED NOT NULL,
    load_status VARCHAR(30) NOT NULL DEFAULT 'registered',
    first_loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id),
    UNIQUE KEY uq_ingest_source_sha256 (sha256),
    KEY ix_ingest_source_kind (source_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ingest_archive_member (
    member_key CHAR(64) NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    member_name VARCHAR(1000) NOT NULL,
    member_extension VARCHAR(20) NULL,
    row_count BIGINT UNSIGNED NULL,
    structured_target VARCHAR(100) NULL,
    load_status VARCHAR(30) NOT NULL,
    error_message TEXT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (member_key),
    KEY ix_archive_member_source (source_id),
    KEY ix_archive_member_status (load_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS datalab_detail_row (
    row_key CHAR(64) NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    member_name VARCHAR(1000) NOT NULL,
    tab_no TINYINT UNSIGNED NULL,
    source_region_code VARCHAR(30) NULL,
    source_region_name VARCHAR(150) NULL,
    query_start_month DATE NULL,
    query_end_month DATE NULL,
    observed_month DATE NULL,
    data_group VARCHAR(200) NOT NULL,
    source_row_no INT UNSIGNED NOT NULL,
    row_json JSON NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (row_key),
    KEY ix_datalab_detail_region_month (source_region_code, observed_month),
    KEY ix_datalab_detail_group_month (data_group, observed_month),
    KEY ix_datalab_detail_query_period (query_start_month, query_end_month),
    KEY ix_datalab_detail_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS jeju_attraction_visitors_daily (
    observed_date DATE NOT NULL,
    attraction_name VARCHAR(300) NOT NULL,
    visitor_count BIGINT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (observed_date, attraction_name),
    KEY ix_jeju_attraction_name (attraction_name),
    KEY ix_jeju_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS domestic_tourist_residence_annual (
    reference_year SMALLINT UNSIGNED NOT NULL,
    residence_name VARCHAR(200) NOT NULL,
    respondent_count BIGINT NULL,
    share_pct DECIMAL(12,6) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (reference_year, residence_name),
    KEY ix_residence_annual_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS external_collection_catalog (
    catalog_key CHAR(64) NOT NULL,
    source_name VARCHAR(200) NULL,
    category_name VARCHAR(200) NULL,
    title VARCHAR(1000) NOT NULL,
    registered_date DATE NULL,
    registered_date_raw VARCHAR(100) NULL,
    stored_file_name VARCHAR(1000) NULL,
    note TEXT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (catalog_key),
    KEY ix_external_catalog_date (registered_date),
    KEY ix_external_catalog_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS reference_document_catalog (
    document_key CHAR(64) NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    member_name VARCHAR(1000) NOT NULL,
    document_type VARCHAR(30) NOT NULL,
    title VARCHAR(1000) NOT NULL,
    region_hint VARCHAR(200) NULL,
    byte_size BIGINT UNSIGNED NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (document_key),
    KEY ix_reference_document_type (document_type),
    KEY ix_reference_document_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS observed_visitors_case (
    case_key CHAR(64) NOT NULL,
    region_name VARCHAR(200) NOT NULL,
    announced_date DATE NULL,
    survey_period VARCHAR(300) NULL,
    visitor_count BIGINT NULL,
    visitor_count_text VARCHAR(1000) NULL,
    yoy_change_text VARCHAR(200) NULL,
    source_url TEXT NULL,
    note TEXT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (case_key),
    KEY ix_observed_case_region (region_name),
    KEY ix_observed_case_date (announced_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS domestic_interest_attraction_rank (
    region_name VARCHAR(200) NOT NULL,
    ranking INT UNSIGNED NOT NULL,
    attraction_name VARCHAR(500) NOT NULL,
    total_registration_count BIGINT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (region_name, ranking, attraction_name),
    KEY ix_interest_rank_attraction (attraction_name),
    KEY ix_interest_rank_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS major_attraction_visitors_monthly (
    attraction_month_key CHAR(64) NOT NULL,
    province_name VARCHAR(100) NOT NULL,
    district_name VARCHAR(150) NOT NULL,
    attraction_name VARCHAR(500) NOT NULL,
    visitor_type VARCHAR(30) NOT NULL,
    observed_month DATE NOT NULL,
    visitor_count BIGINT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    source_member_name VARCHAR(1000) NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (attraction_month_key),
    KEY ix_major_attraction_month (observed_month),
    KEY ix_major_attraction_region (province_name, district_name),
    KEY ix_major_attraction_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE OR REPLACE VIEW vw_datalab_sns_companion_monthly AS
SELECT
    source_region_code,
    source_region_name,
    observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."동반유형명"')) AS companion_type,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."언급건수"')) AS DECIMAL(30,8)) AS mention_count
FROM datalab_detail_row
WHERE data_group = '동반유형 언급량';

CREATE OR REPLACE VIEW vw_datalab_sns_travel_type_monthly AS
SELECT
    source_region_code,
    source_region_name,
    observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."여행유형/트렌드명"')) AS travel_type,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."언급건수"')) AS DECIMAL(30,8)) AS mention_count
FROM datalab_detail_row
WHERE data_group = '여행유형_트렌드 언급량';

CREATE OR REPLACE VIEW vw_datalab_navigation_destination_monthly AS
SELECT
    source_region_code,
    source_region_name,
    observed_month,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."목적지 유형"')) AS destination_type,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."목적지 검색량"')) AS DECIMAL(30,8)) AS search_count
FROM datalab_detail_row
WHERE data_group = '내비게이션 목적지 유형별 검색량';

CREATE OR REPLACE VIEW vw_datalab_spend_industry_monthly AS
SELECT
    source_region_code,
    source_region_name,
    observed_month,
    CASE
        WHEN data_group LIKE '%내국인' THEN 'domestic'
        WHEN data_group LIKE '%현지인' THEN 'local'
        WHEN data_group LIKE '%외지인' THEN 'outsider'
        ELSE 'unknown'
    END AS visitor_segment,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."업종대분류명"')) AS industry_major,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."소비액(천원)"')) AS DECIMAL(30,8)) AS spend_krw_thousand
FROM datalab_detail_row
WHERE data_group IN ('관광소비 추이_내국인', '관광소비 추이_현지인', '관광소비 추이_외지인');

CREATE OR REPLACE VIEW vw_datalab_keyword_snapshot AS
SELECT
    source_region_code,
    source_region_name,
    query_start_month,
    query_end_month,
    data_group,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."순위"')) AS UNSIGNED) AS ranking,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."분류"')) AS category_name,
    JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."관련 키워드"')) AS keyword,
    CAST(JSON_UNQUOTE(JSON_EXTRACT(row_json, '$."언급건수"')) AS DECIMAL(30,8)) AS mention_count
FROM datalab_detail_row
WHERE data_group IN ('동반유형 키워드', '여행유형_트렌드 키워드');
