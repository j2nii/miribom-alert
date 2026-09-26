-- One-time migration for the current database state.
-- The earlier migration failed before changing any column, so these columns do not exist yet.
ALTER TABLE youtube_video
    ADD COLUMN description MEDIUMTEXT NULL AFTER title,
    ADD COLUMN tags JSON NULL AFTER description,
    ADD COLUMN derived_tags JSON NULL AFTER tags,
    ADD COLUMN duration_iso VARCHAR(32) NULL AFTER derived_tags,
    ADD COLUMN metadata_fetched_at DATETIME NULL AFTER duration_iso;

CREATE TABLE IF NOT EXISTS youtube_video_region_match (
    video_id VARCHAR(32) NOT NULL,
    region_id VARCHAR(20) NOT NULL,
    source_region_name VARCHAR(100) NOT NULL,
    collected_queries JSON NULL,
    source_file_id BIGINT UNSIGNED NOT NULL,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (video_id, region_id),
    KEY ix_youtube_region_match_region (region_id, video_id),
    KEY fk_youtube_region_match_file (source_file_id),
    CONSTRAINT fk_youtube_region_match_video
        FOREIGN KEY (video_id) REFERENCES youtube_video (video_id) ON DELETE CASCADE,
    CONSTRAINT fk_youtube_region_match_region
        FOREIGN KEY (region_id) REFERENCES dim_region (region_id),
    CONSTRAINT fk_youtube_region_match_file
        FOREIGN KEY (source_file_id) REFERENCES source_file (source_file_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO youtube_video_region_match (
    video_id,
    region_id,
    source_region_name,
    collected_queries,
    source_file_id
)
SELECT
    video_id,
    region_id,
    source_region_name,
    CASE
        WHEN keyword_text IS NULL OR keyword_text = '' THEN JSON_ARRAY()
        ELSE JSON_ARRAY(keyword_text)
    END,
    source_file_id
FROM youtube_video;

SELECT
    COUNT(*) AS videos,
    SUM(description IS NOT NULL AND description <> '') AS has_description,
    SUM(tags IS NOT NULL AND JSON_LENGTH(tags) > 0) AS has_source_tags,
    SUM(derived_tags IS NOT NULL AND JSON_LENGTH(derived_tags) > 0) AS has_derived_tags
FROM youtube_video;
