SELECT
    COUNT(*) AS rows_actual,
    COUNT(DISTINCT region_id) AS primary_regions,
    MIN(published_at) AS date_min,
    MAX(published_at) AS date_max,
    SUM(description IS NOT NULL AND description <> '') AS has_description,
    SUM(tags IS NOT NULL AND JSON_LENGTH(tags) > 0) AS has_source_tags,
    SUM(derived_tags IS NOT NULL AND JSON_LENGTH(derived_tags) > 0) AS has_derived_tags,
    SUM(metadata_fetched_at IS NOT NULL) AS metadata_refreshed
FROM youtube_video;

SELECT
    COUNT(*) AS region_links,
    COUNT(DISTINCT video_id) AS linked_videos,
    COUNT(DISTINCT region_id) AS linked_regions
FROM youtube_video_region_match;

SELECT
    COUNT(*) AS videos_linked_to_multiple_regions
FROM (
    SELECT video_id
    FROM youtube_video_region_match
    GROUP BY video_id
    HAVING COUNT(DISTINCT region_id) > 1
) AS x;

SELECT
    source_region_name,
    COUNT(*) AS video_links,
    SUM(JSON_LENGTH(collected_queries) > 0) AS links_with_queries
FROM youtube_video_region_match
WHERE region_id IN ('51210', '12130', '51750', '47940', '51810')
GROUP BY source_region_name
ORDER BY source_region_name;

SELECT
    COUNT(*) AS duplicate_video_ids
FROM (
    SELECT video_id
    FROM youtube_video
    GROUP BY video_id
    HAVING COUNT(*) > 1
) AS x;
