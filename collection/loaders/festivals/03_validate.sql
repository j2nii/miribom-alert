SET NAMES utf8mb4;
USE tour_earlywarning;

SELECT 'festival_events' AS check_name,
       COUNT(*) AS events,
       COUNT(DISTINCT region_id) AS regions
FROM event
WHERE event_key LIKE 'culture_festival:%';

SELECT YEAR(p.point_date) AS event_year,
       COUNT(*) AS events,
       COUNT(DISTINCT e.region_id) AS regions
FROM event AS e
JOIN event_point AS p
  ON p.event_id=e.event_id AND p.point_type='T0'
WHERE e.event_key LIKE 'culture_festival:%'
GROUP BY YEAR(p.point_date)
ORDER BY event_year;

SELECT 'festival_points' AS check_name,
       COUNT(*) AS points,
       SUM(point_type='T0') AS starts,
       SUM(point_type='end') AS ends
FROM event_point AS p
JOIN event AS e ON e.event_id=p.event_id
WHERE e.event_key LIKE 'culture_festival:%';

SELECT 'episode_match' AS check_name,
       COUNT(*) AS episodes,
       SUM(matched_event_count > 0) AS matched_episodes
FROM vw_anomaly_episode_context;

