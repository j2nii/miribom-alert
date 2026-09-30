USE tour_earlywarning;

-- Frozen analysis snapshot: 2026-09-22 KST

DROP TABLE IF EXISTS snap_20260922_daily_core;
CREATE TABLE snap_20260922_daily_core AS
SELECT *
FROM vw_daily_core_signal
WHERE observed_date <= '2026-08-14';
ALTER TABLE snap_20260922_daily_core
  ADD PRIMARY KEY (region_id, observed_date);

DROP TABLE IF EXISTS snap_20260922_datalab_monthly;
CREATE TABLE snap_20260922_datalab_monthly AS
SELECT *
FROM vw_datalab_canonical_monthly
WHERE period_start <= '2026-08-01';
ALTER TABLE snap_20260922_datalab_monthly
  ADD PRIMARY KEY (canonical_region_id, period_start);

-- Locate the final anomaly-analysis object. Fall back to the known
-- analysis-ready/enriched view when a separate final view was not persisted.
SET @anomaly_source := (
  SELECT table_name
  FROM information_schema.tables
  WHERE table_schema = DATABASE()
    AND table_name IN (
      'vw_anomaly_final_analysis',
      'vw_anomaly_analysis_final',
      'vw_anomaly_analysis_ready',
      'vw_anomaly_analysis_enriched'
    )
  ORDER BY FIELD(
    table_name,
    'vw_anomaly_final_analysis',
    'vw_anomaly_analysis_final',
    'vw_anomaly_analysis_ready',
    'vw_anomaly_analysis_enriched'
  )
  LIMIT 1
);

DROP TABLE IF EXISTS snap_20260922_anomaly_final;
SET @anomaly_sql := IF(
  @anomaly_source IS NULL,
  'CREATE TABLE snap_20260922_anomaly_final (snapshot_error VARCHAR(255))',
  CONCAT(
    'CREATE TABLE snap_20260922_anomaly_final AS SELECT * FROM `',
    REPLACE(@anomaly_source, '`', '``'),
    '`'
  )
);
PREPARE anomaly_stmt FROM @anomaly_sql;
EXECUTE anomaly_stmt;
DEALLOCATE PREPARE anomaly_stmt;

DROP TABLE IF EXISTS snap_20260922_event;
CREATE TABLE snap_20260922_event AS
SELECT * FROM event;

DROP TABLE IF EXISTS snap_20260922_event_point;
CREATE TABLE snap_20260922_event_point AS
SELECT * FROM event_point;

DROP TABLE IF EXISTS snap_20260922_evidence_top3;
CREATE TABLE snap_20260922_evidence_top3 AS
SELECT * FROM vw_anomaly_episode_evidence_top3;

-- Locate and materialize the ASOS base table without hard-coding its name.
SET @asos_source := (
  SELECT table_name
  FROM information_schema.tables
  WHERE table_schema = DATABASE()
    AND table_type = 'BASE TABLE'
    AND table_name LIKE '%asos%'
    AND table_name NOT LIKE 'snap\_%'
  ORDER BY
    CASE
      WHEN table_name = 'kma_asos_daily' THEN 0
      WHEN table_name LIKE '%asos%daily%' THEN 1
      ELSE 2
    END,
    table_name
  LIMIT 1
);

DROP TABLE IF EXISTS snap_20260922_asos_daily;
SET @asos_sql := IF(
  @asos_source IS NULL,
  'CREATE TABLE snap_20260922_asos_daily (snapshot_error VARCHAR(255))',
  CONCAT(
    'CREATE TABLE snap_20260922_asos_daily AS SELECT * FROM `',
    REPLACE(@asos_source, '`', '``'),
    '`'
  )
);
PREPARE asos_stmt FROM @asos_sql;
EXECUTE asos_stmt;
DEALLOCATE PREPARE asos_stmt;

DROP TABLE IF EXISTS analysis_snapshot_manifest_20260922;
CREATE TABLE analysis_snapshot_manifest_20260922 (
  snapshot_name VARCHAR(100) NOT NULL PRIMARY KEY,
  source_object VARCHAR(255) NOT NULL,
  rows_actual BIGINT NOT NULL,
  frozen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note VARCHAR(500) NULL
);

INSERT INTO analysis_snapshot_manifest_20260922
  (snapshot_name, source_object, rows_actual, note)
VALUES
  ('daily_core', 'vw_daily_core_signal',
   (SELECT COUNT(*) FROM snap_20260922_daily_core),
   'Daily modeling panel; capped at visitor coverage end date'),
  ('datalab_monthly', 'vw_datalab_canonical_monthly',
   (SELECT COUNT(*) FROM snap_20260922_datalab_monthly),
   'Canonical 228-region monthly panel'),
  ('anomaly_final', COALESCE(@anomaly_source, 'NOT_FOUND'),
   (SELECT COUNT(*) FROM snap_20260922_anomaly_final),
   IF(@anomaly_source IS NULL,
      'Anomaly analysis source object was not found',
      'Frozen anomaly episode analysis')), 
  ('event', 'event',
   (SELECT COUNT(*) FROM snap_20260922_event),
   'Festival events'),
  ('event_point', 'event_point',
   (SELECT COUNT(*) FROM snap_20260922_event_point),
   'Festival start/end points'),
  ('evidence_top3', 'vw_anomaly_episode_evidence_top3',
   (SELECT COUNT(*) FROM snap_20260922_evidence_top3),
   'Top three external evidence rows per researched episode'),
  ('asos_daily', COALESCE(@asos_source, 'NOT_FOUND'),
   (SELECT COUNT(*) FROM snap_20260922_asos_daily),
   IF(@asos_source IS NULL, 'ASOS source table was not found', 'Daily ASOS observations'));

SELECT *
FROM analysis_snapshot_manifest_20260922
ORDER BY snapshot_name;
