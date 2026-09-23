# Tourism Early-Warning Data Pipeline

## Scope

This directory contains the reproducible collection, loading, mapping, validation, and anomaly-analysis code used for the tourism early-warning project. Raw downloaded data, database credentials, API keys, browser sessions, and large generated outputs are intentionally excluded.

Data freeze date: 2026-09-22 KST

## Current database snapshot

- Canonical regions: 228
- Daily external visitors: 717,744 rows, 2018-01-01 to 2026-08-14
- Daily Naver search index: 305,292 rows, 2023-01-01 to 2026-08-31
- DataLab canonical monthly panel: 18,240 rows, 228 regions, 2020-01 to 2026-08
- DataLab detailed raw records: 2,829,331 rows, no unmapped rows after canonical mapping
- Attraction monthly visits: 847,656 rows, 4,159 attractions, 2004-07 to 2026-06
- ASOS daily weather: 128,535 rows from 96 stations
- Festival events: 2,562 events and 5,124 start/end event points
- Detected anomaly episodes: 450 episodes across 146 regions
- External evidence: 15,590 rows covering 220 episodes

## Recommended repository layout

```text
data_pipeline/
  README.md
  requirements.txt
  .env.example
  collectors/
    datalab/
    naver/
    public_context/
    evidence/
  loaders/
    base_data/
    datalab_detail/
    festivals/
  sql/
    schema/
    mapping/
    anomaly/
    validation/
  analysis/
    final_anomaly/
    human_review/
    viral_keyword_pilot/
  docs/
    DB_HANDOFF.md
    DATA_DICTIONARY.md
```

Historical patch folders should not be uploaded as separate final modules. Keep the final working version of each script and preserve the execution order in the README.

## Main database views

| Object | Purpose |
|---|---|
| `dim_region` | Canonical 228-region dimension |
| `vw_daily_core_signal` | Daily Naver interest and external visitors |
| `vw_datalab_canonical_monthly` | Canonical monthly DataLab indicators |
| `vw_daily_anomaly_features` | Daily z-scores and baseline ratios |
| `vw_anomaly_episode_context` | Consecutive anomaly days grouped into episodes |
| `vw_anomaly_analysis_ready` | Episodes joined with calendar and evidence context |
| `vw_anomaly_analysis_enriched` | DataLab detail and attraction features |
| `vw_anomaly_final_analysis` | Final festival, holiday, weather, and evidence interpretation |

## Safe environment configuration

Create a local `.env` file from `.env.example`. Never commit the real `.env`.

```dotenv
MYSQL_HOST=YOUR_DB_HOST
MYSQL_PORT=3306
MYSQL_DATABASE=tour_earlywarning
MYSQL_USER=YOUR_DB_USER
MYSQL_PASSWORD=YOUR_DB_PASSWORD

NAVER_CLIENT_ID=YOUR_NAVER_CLIENT_ID
NAVER_CLIENT_SECRET=YOUR_NAVER_CLIENT_SECRET
DATA_GO_KR_SERVICE_KEY=YOUR_PUBLIC_DATA_SERVICE_KEY
```

The database host, passwords, API secrets, TLS private keys, and saved login sessions must be shared through a private team channel, not GitHub.

## Reproduction order

1. Create the schema and canonical region dimension.
2. Load daily visitor and Naver search data.
3. Load and canonicalize DataLab monthly and detailed records.
4. Load attraction visits, ASOS weather, and festival events.
5. Build anomaly features and candidate episodes.
6. Join calendar, festival, weather, and external evidence.
7. Run validation SQL.
8. Export analysis-ready summaries.

Each module should provide numbered `.cmd` files for Windows execution and an equivalent direct Python or SQL command in its local README.

## Analysis status

The current pipeline produced 450 anomaly episodes:

| Explanation group | Episodes |
|---|---:|
| Calendar related | 160 |
| Exact festival overlap | 109 |
| Unexplained candidate | 69 |
| Weather context | 29 |
| Festival pre-signal | 26 |
| Possible external cause | 23 |
| External evidence | 22 |
| Nearby festival | 12 |

Festival information matched 147 episodes. The human review of 20 high-priority episodes is only a pilot sample and must not be reported as full-dataset model performance.

## Modeling guidance

The time-series owner should start from `vw_daily_core_signal` and compare models with date-ordered rolling or expanding validation.

- Baseline: visitor lags, weekday, holiday, and seasonal variables
- Model 1: baseline plus regional Naver search index
- Model 2: Model 1 plus weather
- Exploratory extension: curated viral keyword groups

Do not randomly shuffle dates. Fit scalers and thresholds using the training window only.

The Yeongwol and Geoje keyword experiment is retrospective: keywords were selected after the cases were known. It is suitable for hypothesis generation, not unbiased predictive-performance reporting.

## Known limitations

- DataLab SNS mentions are monthly, not daily.
- Naver DataLab values are relative indices; values from separate API calls are not absolute search-volume measurements.
- YouTube coverage is limited to six regions and lacks repeated view-count snapshots.
- Historical weather-warning API records were unavailable; weather interpretation mainly uses ASOS observations.
- A common nationwide daily eup/myeon/dong or point-level visitor panel is unavailable. A general point-concentration Gini metric is therefore not supported by this snapshot.
- Absence of a festival record does not prove that no festival occurred.

## Branch and review policy

- Do not commit directly to `main`.
- Work in a personal feature branch and open a pull request.
- Do not commit raw data or secrets.
- Include validation output and a short change summary in the pull request.
- Treat the 2026-09-22 snapshot as frozen for the submitted analysis.

