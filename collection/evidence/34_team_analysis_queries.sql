SET NAMES utf8mb4;
USE tour_earlywarning;

-- 1. 설명 상태별 규모와 평균 이상 강도
SELECT explanation_status,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       ROUND(AVG(peak_anomaly_score), 3) AS avg_anomaly_score,
       ROUND(AVG(peak_naver_ratio), 3) AS avg_naver_ratio,
       ROUND(AVG(peak_visitor_ratio), 3) AS avg_visitor_ratio
FROM vw_anomaly_analysis_ready
GROUP BY explanation_status
ORDER BY episodes DESC;

-- 2. 외부 원인 유형별 후보 수
SELECT auto_cause_type, auto_confidence,
       COUNT(*) AS episodes,
       COUNT(DISTINCT region_id) AS regions,
       ROUND(AVG(search_to_visit_lag_days), 2) AS avg_lag_days
FROM vw_anomaly_analysis_ready
WHERE explanation_status IN (
  'strong_external_candidate', 'possible_external_candidate'
)
GROUP BY auto_cause_type, auto_confidence
ORDER BY auto_confidence, episodes DESC;

-- 3. 우선 검토할 강한 외부 원인 후보
SELECT region_name, search_peak_date, visitor_peak_date,
       peak_anomaly_score, peak_naver_ratio, peak_visitor_ratio,
       auto_cause_type, evidence_title, evidence_url
FROM vw_anomaly_analysis_ready
WHERE explanation_status = 'strong_external_candidate'
ORDER BY peak_anomaly_score DESC;

-- 4. 월별 맥락까지 포함한 후보 비교
SELECT region_name, visitor_peak_date, explanation_status,
       auto_cause_type, peak_anomaly_score,
       datalab_visitors_mom_pct,
       datalab_sns_mentions_mom_pct,
       datalab_navigation_searches_mom_pct,
       datalab_lodging_searches_mom_pct,
       datalab_outsider_spend_mom_pct,
       evidence_title
FROM vw_anomaly_analysis_ready
WHERE explanation_status IN (
  'strong_external_candidate', 'possible_external_candidate'
)
ORDER BY peak_anomaly_score DESC;

-- 5. 다음 수집·검토 우선순위: 점수가 높은 미설명 에피소드
SELECT region_name, episode_start, episode_end,
       search_peak_date, visitor_peak_date,
       peak_anomaly_score, peak_naver_ratio, peak_visitor_ratio,
       explanation_status
FROM vw_anomaly_analysis_unresolved
ORDER BY peak_anomaly_score DESC
LIMIT 100;
