-- Analysis-safe DataLab views.
-- Raw 20,720 rows remain unchanged. The canonical view returns one row per
-- canonical region and month (228 regions x 80 months for the current data).

SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_mapped_raw AS
SELECT p.*,
       m.mapping_type,
       m.valid_from AS mapping_valid_from,
       m.valid_to AS mapping_valid_to,
       m.mapping_note
FROM datalab_monthly_panel AS p
JOIN datalab_region_mapping AS m
  ON m.source_region_name = p.source_region_name
WHERE (m.valid_from IS NULL OR p.period_start >= m.valid_from)
  AND (m.valid_to IS NULL OR p.period_start <= m.valid_to);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_canonical_monthly AS
WITH
periods AS (
  SELECT DISTINCT period_start
  FROM datalab_monthly_panel
),
active_raw AS (
  SELECT *
  FROM vw_datalab_mapped_raw
),
agg AS (
  SELECT
    canonical_region_id,
    period_start,
    COUNT(*) AS source_region_count,
    COUNT(visitors) AS visitors_source_count,

    SUM(visitors) AS visitors,
    SUM(visitors_prev_year) AS visitors_prev_year,
    CASE
      WHEN SUM(visitors_prev_year) IS NULL OR SUM(visitors_prev_year) = 0
        OR SUM(visitors) IS NULL THEN NULL
      ELSE (SUM(visitors) - SUM(visitors_prev_year))
           / SUM(visitors_prev_year) * 100
    END AS visitors_yoy_pct,

    -- Unique visitors cannot be added safely across multiple districts.
    CASE WHEN COUNT(*) = 1 THEN MAX(unique_visitors) ELSE NULL END
      AS unique_visitors,

    SUM(overnight_guest_pct * visitors)
      / NULLIF(SUM(CASE WHEN overnight_guest_pct IS NOT NULL THEN visitors END), 0)
      AS overnight_guest_pct,
    SUM(sns_mentions) AS sns_mentions,
    SUM(avg_nights * visitors)
      / NULLIF(SUM(CASE WHEN avg_nights IS NOT NULL THEN visitors END), 0)
      AS avg_nights,
    SUM(stay_minutes * visitors)
      / NULLIF(SUM(CASE WHEN stay_minutes IS NOT NULL THEN visitors END), 0)
      AS stay_minutes,
    SUM(stay_minutes_national * visitors)
      / NULLIF(SUM(CASE WHEN stay_minutes_national IS NOT NULL THEN visitors END), 0)
      AS stay_minutes_national,
    SUM(overnight_visit_pct * visitors)
      / NULLIF(SUM(CASE WHEN overnight_visit_pct IS NOT NULL THEN visitors END), 0)
      AS overnight_visit_pct,
    SUM(overnight_visit_pct_national * visitors)
      / NULLIF(SUM(CASE WHEN overnight_visit_pct_national IS NOT NULL THEN visitors END), 0)
      AS overnight_visit_pct_national,

    SUM(lodging_searches) AS lodging_searches,
    SUM(lodging_searches_prev) AS lodging_searches_prev,
    CASE
      WHEN SUM(lodging_searches_prev) IS NULL OR SUM(lodging_searches_prev) = 0
        OR SUM(lodging_searches) IS NULL THEN NULL
      ELSE (SUM(lodging_searches) - SUM(lodging_searches_prev))
           / SUM(lodging_searches_prev) * 100
    END AS lodging_searches_yoy_pct,
    SUM(navigation_searches) AS navigation_searches,

    SUM(tourism_spend_domestic_krw_thousand)
      AS tourism_spend_domestic_krw_thousand,
    SUM(tourism_spend_outsider_krw_thousand)
      AS tourism_spend_outsider_krw_thousand,
    SUM(tourism_spend_local_krw_thousand)
      AS tourism_spend_local_krw_thousand,

    -- These are shares of the national total, so district shares are additive.
    SUM(spend_share_domestic_pct) AS spend_share_domestic_pct,
    SUM(spend_share_outsider_pct) AS spend_share_outsider_pct,
    SUM(spend_share_local_pct) AS spend_share_local_pct,
    SUM(local_currency_spend_krw_thousand)
      AS local_currency_spend_krw_thousand,

    SUM(stay_1night_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_1night_pct IS NOT NULL THEN visitors END), 0)
      AS stay_1night_pct,
    SUM(stay_2nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_2nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_2nights_pct,
    SUM(stay_3nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_3nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_3nights_pct,
    SUM(stay_4nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_4nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_4nights_pct,
    SUM(stay_5nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_5nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_5nights_pct,
    SUM(stay_6nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_6nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_6nights_pct,
    SUM(stay_7plus_nights_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_7plus_nights_pct IS NOT NULL THEN visitors END), 0)
      AS stay_7plus_nights_pct,
    SUM(stay_type_total_pct * visitors)
      / NULLIF(SUM(CASE WHEN stay_type_total_pct IS NOT NULL THEN visitors END), 0)
      AS stay_type_total_pct
  FROM active_raw
  GROUP BY canonical_region_id, period_start
)
SELECT
  r.region_id AS canonical_region_id,
  r.region_name AS canonical_region_name,
  p.period_start,
  COALESCE(a.source_region_count, 0) AS source_region_count,
  COALESCE(a.visitors_source_count, 0) AS visitors_source_count,
  a.visitors,
  a.visitors_prev_year,
  a.visitors_yoy_pct,
  a.unique_visitors,
  a.overnight_guest_pct,
  a.sns_mentions,
  a.avg_nights,
  a.stay_minutes,
  a.stay_minutes_national,
  a.overnight_visit_pct,
  a.overnight_visit_pct_national,
  a.lodging_searches,
  a.lodging_searches_prev,
  a.lodging_searches_yoy_pct,
  a.navigation_searches,
  a.tourism_spend_domestic_krw_thousand,
  a.tourism_spend_outsider_krw_thousand,
  a.tourism_spend_local_krw_thousand,
  a.spend_share_domestic_pct,
  a.spend_share_outsider_pct,
  a.spend_share_local_pct,
  a.local_currency_spend_krw_thousand,
  a.stay_1night_pct,
  a.stay_2nights_pct,
  a.stay_3nights_pct,
  a.stay_4nights_pct,
  a.stay_5nights_pct,
  a.stay_6nights_pct,
  a.stay_7plus_nights_pct,
  a.stay_type_total_pct,
  CASE
    WHEN a.source_region_count > 1 THEN 1 ELSE 0
  END AS is_aggregated_region,
  CASE
    WHEN a.source_region_count > 1 THEN 0 ELSE 1
  END AS unique_visitors_available
FROM periods AS p
CROSS JOIN dim_region AS r
LEFT JOIN agg AS a
  ON a.canonical_region_id = r.region_id
 AND a.period_start = p.period_start;

