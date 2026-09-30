SET NAMES utf8mb4;
USE tour_earlywarning;

-- 검색 API의 원래 relevance_score만 사용하면 날짜가 없는 공식 문서가 과대평가될
-- 수 있으므로, 행사성·지역성·시간 근접성·문서 유형을 분석용으로 다시 계산합니다.
CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_event_evidence_analysis_scored AS
WITH signals AS (
  SELECT
    q.*,
    CONCAT(q.title, ' ', COALESCE(q.description, '')) AS evidence_text,
    CASE
      WHEN q.title REGEXP
        '(축제|페스티벌|대회|공연|박람회|문화제|체전|콘서트|마라톤|불꽃|캠핑|물놀이|걷기|트레킹|폭우|호우|산불|태풍|재난|사고|통제|폐쇄|휴장|개장|개통|방송|촬영|유튜브|SNS|핫플|맛집|무료|할인)'
      THEN 1 ELSE 0
    END AS has_cause_term,
    CASE
      WHEN q.title REGEXP
        '(폭우|호우|산불|태풍|재난|사고|통제|폐쇄|휴장)'
        THEN 'disruption'
      WHEN q.title REGEXP
        '(방송|촬영|유튜브|SNS|핫플|맛집)'
        THEN 'viral_media'
      WHEN q.title REGEXP
        '(개장|개통|무료|할인)'
        THEN 'access_offer'
      WHEN q.title REGEXP
        '(축제|페스티벌|대회|공연|박람회|문화제|체전|콘서트|마라톤|불꽃|캠핑|물놀이|걷기|트레킹)'
        THEN 'tourism_event'
      ELSE 'other'
    END AS auto_cause_type,
    CASE WHEN LOCATE(q.region_name, q.title) > 0
      THEN 1 ELSE 0 END AS has_region_in_title,
    CASE WHEN LOCATE(q.region_name, COALESCE(q.description, '')) > 0
      THEN 1 ELSE 0 END AS has_region_in_description,
    CAST(REGEXP_SUBSTR(q.title, '20[0-9]{2}') AS UNSIGNED) AS title_year,
    CASE
      WHEN q.title REGEXP
        '(공[[:space:]]*보|게시물[[:space:]]*보기|결과보고서|연구[[:space:]]*용역|정[[:space:]]*기[[:space:]]*간[[:space:]]*담[[:space:]]*회|보도자료[[:space:]]*제공[[:space:]]*현황|가이드북|관광홍보물[[:space:]]*다운로드|지도[[:space:]]*<|모집|축제[[:space:]]*일정|주요[[:space:]]*행사|행사·일정)'
      THEN 1 ELSE 0
    END AS is_generic_document,
    CASE
      WHEN q.title REGEXP
        '(기념식|보고회|협의회|우호교류|도시브랜드|군정뉴스|동영상[[:space:]]*뉴스|패트롤|운영[[:space:]]*마무리|간담회|업무협약)'
      THEN 1 ELSE 0
    END AS is_administrative,
    CASE
      WHEN q.title REGEXP
        '((시|군|구)-[^ ]*(시|군|구)-|(시|군|구)[·,][^ ]*(시|군|구)[·,])'
      THEN 1 ELSE 0
    END AS is_multi_region_title,
    CASE
      WHEN COALESCE(q.original_url, q.result_url) REGEXP
        '(download|filedown|filedownlaod|fileupload|\\.pdf([?&#]|$))'
      THEN 1 ELSE 0
    END AS is_file_document,
    CASE
      WHEN q.source_domain LIKE '%visitkorea.or.kr'
        OR q.source_domain LIKE 'tour.%'
        OR q.source_domain LIKE '%festival%'
      THEN 1 ELSE 0
    END AS is_tourism_source
  FROM vw_event_evidence_review_queue AS q
),
scored AS (
  SELECT
    s.*,
    ROUND(
        LEAST(s.relevance_score, 20) * 0.10
      + CASE WHEN s.has_cause_term = 1 THEN 9 ELSE 0 END
      + CASE WHEN s.has_region_in_title = 1 THEN 8 ELSE 0 END
      + CASE WHEN s.has_region_in_description = 1 THEN 1 ELSE 0 END
      + CASE WHEN s.is_official_domain = 1 THEN 2 ELSE 0 END
      + CASE WHEN s.is_tourism_source = 1 THEN 3 ELSE 0 END
      + CASE s.search_type WHEN 'news' THEN 3 WHEN 'blog' THEN 2 ELSE 0 END
      + CASE
          WHEN s.published_date IS NULL THEN 0
          WHEN ABS(s.days_from_peak) <= 14 THEN 8
          WHEN ABS(s.days_from_peak) <= 30 THEN 6
          WHEN ABS(s.days_from_peak) <= 60 THEN 3
          WHEN ABS(s.days_from_peak) <= 90 THEN 1
          ELSE -18
        END
      - CASE WHEN s.is_generic_document = 1 THEN 16 ELSE 0 END
      - CASE WHEN s.is_administrative = 1 THEN 12 ELSE 0 END
      - CASE WHEN s.is_multi_region_title = 1 THEN 12 ELSE 0 END
      - CASE
          WHEN s.title_year IS NOT NULL
           AND s.title_year <> YEAR(s.peak_date) THEN 30
          ELSE 0
        END
      - CASE
          WHEN s.is_file_document = 1 AND s.has_cause_term = 0 THEN 6
          ELSE 0
        END,
      3
    ) AS analysis_rank_score
  FROM signals AS s
)
SELECT
  x.*,
  CASE
    WHEN x.decision = 'accepted' THEN 'verified'
    WHEN x.has_cause_term = 1
     AND x.has_region_in_title = 1
     AND x.is_generic_document = 0
     AND x.is_administrative = 0
     AND x.is_multi_region_title = 0
     AND x.published_date IS NOT NULL
     AND ABS(x.days_from_peak) <= 30
     THEN 'high'
    WHEN x.has_cause_term = 1
     AND x.has_region_in_title = 1
     AND x.is_generic_document = 0
     AND x.is_administrative = 0
     AND x.is_multi_region_title = 0
     AND (
       (x.published_date IS NOT NULL AND ABS(x.days_from_peak) <= 90)
       OR (x.search_type = 'webkr'
           AND (x.is_official_domain = 1 OR x.is_tourism_source = 1)
           AND (x.title_year IS NULL OR x.title_year = YEAR(x.peak_date)))
     ) THEN 'medium'
    ELSE 'low'
  END AS auto_confidence
FROM scored AS x;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_episode_evidence_top3 AS
WITH ranked AS (
  SELECT
    s.*,
    ROW_NUMBER() OVER (
      PARTITION BY s.region_id, s.episode_no
      ORDER BY
        CASE WHEN s.decision = 'accepted' THEN 0 ELSE 1 END,
        s.analysis_rank_score DESC,
        s.is_official_domain DESC,
        s.evidence_id
    ) AS analysis_evidence_rank
  FROM vw_event_evidence_analysis_scored AS s
  WHERE s.decision NOT IN ('rejected', 'duplicate')
)
SELECT
  r.region_id,
  r.region_name,
  r.episode_no,
  r.episode_start,
  r.episode_end,
  r.search_peak_date,
  r.peak_date AS visitor_peak_date,
  r.pattern_hint,
  r.research_priority,
  r.research_priority_score,
  r.analysis_evidence_rank AS evidence_rank,
  r.evidence_id,
  r.search_type,
  r.title AS evidence_title,
  r.description AS evidence_description,
  r.source_domain,
  COALESCE(r.original_url, r.result_url) AS evidence_url,
  r.published_date,
  r.days_from_peak,
  r.is_official_domain,
  r.analysis_rank_score,
  r.auto_cause_type,
  r.auto_confidence,
  r.decision,
  CASE
    WHEN r.decision = 'accepted' THEN 'verified'
    ELSE 'unverified'
  END AS evidence_status,
  r.event_name,
  r.event_type,
  r.event_start,
  r.event_end
FROM ranked AS r
WHERE r.analysis_evidence_rank <= 3;

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_anomaly_episode_top_evidence AS
SELECT t.*
FROM vw_anomaly_episode_evidence_top3 AS t
WHERE t.evidence_rank = 1;

SELECT 'top_evidence' AS check_name,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       SUM(evidence_status = 'verified') AS verified,
       SUM(auto_confidence = 'high') AS high_confidence,
       SUM(auto_confidence = 'medium') AS medium_confidence,
       SUM(auto_confidence = 'low') AS low_confidence
FROM vw_anomaly_episode_top_evidence;

SELECT 'top3_evidence' AS check_name,
       COUNT(*) AS evidence_rows,
       COUNT(DISTINCT region_id, episode_no) AS episodes,
       SUM(is_official_domain = 1) AS official_rows
FROM vw_anomaly_episode_evidence_top3;

SELECT region_name, search_peak_date, research_priority,
       search_type, auto_cause_type, auto_confidence,
       visitor_peak_date, published_date, days_from_peak,
       analysis_rank_score,
       evidence_title, evidence_url
FROM vw_anomaly_episode_top_evidence
ORDER BY FIELD(research_priority, 'P1', 'P2', 'P3'),
         research_priority_score DESC
LIMIT 10;
