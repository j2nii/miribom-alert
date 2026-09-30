# Analysis snapshot — 2026-09-22

This directory contains only the code and metadata required to materialize and validate the frozen analysis snapshot. Raw CSV files, database dumps, credentials, and API keys are intentionally excluded from Git.

## Run

```cmd
mysql -u yaho_loader -p tour_earlywarning < 01_create_analysis_snapshot.sql
mysql -u yaho_loader -p tour_earlywarning < 02_validate_analysis_snapshot.sql
```

## Snapshot objects

- `snap_20260922_daily_core`: daily Naver interest and external visitors
- `snap_20260922_datalab_monthly`: canonical monthly DataLab indicators (`canonical_region_id` key)
- `snap_20260922_anomaly_final`: final 450 anomaly episodes
- `snap_20260922_event`: festival events
- `snap_20260922_event_point`: festival start/end points
- `snap_20260922_evidence_top3`: external evidence for review
- `snap_20260922_asos_daily`: daily ASOS observations
- `analysis_snapshot_manifest_20260922`: source and row-count manifest

The snapshot tables are materialized inside `tour_earlywarning`, so existing read-only team accounts can query them without receiving access to another database.

## Modeling entry point

```sql
SELECT *
FROM snap_20260922_daily_core
ORDER BY region_id, observed_date;
```

Do not train directly from the live views after the snapshot is created. Use date-ordered rolling or expanding validation and fit all preprocessing steps on the training window only.

## Expected validation

- Daily core: about 301,416 rows, 228 regions, no duplicate region-date keys
- DataLab monthly: 18,240 rows, 228 regions, 80 months
- Final anomaly episodes: 450 rows, 146 regions
- Festival events: 2,562 rows
- Festival points: 5,124 rows
- ASOS daily: 128,535 rows from 96 stations

If ASOS validation returns one row containing only `snapshot_error`, the source table was not discovered. Check the base-table name before using the weather snapshot.
