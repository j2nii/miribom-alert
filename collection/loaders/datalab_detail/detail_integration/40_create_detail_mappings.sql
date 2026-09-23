SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS datalab_detail_region_map (
  source_region_code VARCHAR(30) NOT NULL,
  source_region_name VARCHAR(150) NOT NULL DEFAULT '',
  canonical_region_id VARCHAR(20) NOT NULL,
  mapping_method VARCHAR(40) NOT NULL,
  valid_from DATE NULL,
  valid_to DATE NULL,
  mapping_note VARCHAR(255) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (source_region_code, source_region_name),
  KEY ix_detail_map_canonical (canonical_region_id),
  CONSTRAINT fk_detail_map_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 수동 보정은 보존하고 자동 생성분만 다시 만듭니다.
DELETE FROM datalab_detail_region_map
WHERE mapping_method <> 'manual';

-- 1순위: 원천 코드가 228개 분석 정본 코드와 직접 일치합니다.
INSERT IGNORE INTO datalab_detail_region_map
  (source_region_code, source_region_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  d.source_region_code,
  COALESCE(d.source_region_name, ''),
  r.region_id,
  'direct_code',
  '원천 코드와 분석 정본 코드 일치'
FROM datalab_detail_row AS d
JOIN dim_region AS r
  ON r.region_id = d.source_region_code
WHERE d.source_region_code IS NOT NULL;

-- 2순위: 기존 행정개편 코드 별칭을 사용합니다.
INSERT IGNORE INTO datalab_detail_region_map
  (source_region_code, source_region_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  d.source_region_code,
  COALESCE(d.source_region_name, ''),
  a.canonical_region_id,
  'code_alias',
  a.mapping_reason
FROM datalab_detail_row AS d
JOIN region_alias AS a
  ON a.source_region_key = d.source_region_code
 AND a.source_system IN ('administrative_code', 'canonical')
WHERE d.source_region_code IS NOT NULL;

-- 3순위: 기존 259개 DataLab 지역명 매핑을 재사용합니다.
INSERT IGNORE INTO datalab_detail_region_map
  (source_region_code, source_region_name, canonical_region_id,
   mapping_method, valid_from, valid_to, mapping_note)
SELECT DISTINCT
  d.source_region_code,
  COALESCE(d.source_region_name, ''),
  m.canonical_region_id,
  'datalab_name',
  m.valid_from,
  m.valid_to,
  m.mapping_note
FROM datalab_detail_row AS d
JOIN datalab_region_mapping AS m
  ON m.source_region_name = d.source_region_name
WHERE d.source_region_code IS NOT NULL;

-- 4순위: 전국에서 유일한 지역명은 이름으로 안전하게 연결합니다.
INSERT IGNORE INTO datalab_detail_region_map
  (source_region_code, source_region_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  d.source_region_code,
  COALESCE(d.source_region_name, ''),
  u.region_id,
  'unique_name',
  '228개 정본에서 유일한 지역명'
FROM datalab_detail_row AS d
JOIN (
  SELECT region_name, MIN(region_id) AS region_id
  FROM dim_region
  GROUP BY region_name
  HAVING COUNT(*) = 1
) AS u
  ON u.region_name = d.source_region_name
WHERE d.source_region_code IS NOT NULL;

-- 5순위: 세부 원본의 일반구 표기(예: 수원시_팔달구)를 기존 DataLab
-- 지역명 표기(수원시 팔달구)로 정규화해 상위 시 정본에 연결합니다.
INSERT INTO datalab_detail_region_map
  (source_region_code, source_region_name, canonical_region_id,
   mapping_method, valid_from, valid_to, mapping_note)
SELECT DISTINCT
  d.source_region_code,
  COALESCE(d.source_region_name, ''),
  m.canonical_region_id,
  'normalized_datalab_name',
  m.valid_from,
  m.valid_to,
  CONCAT('밑줄 지역명 정규화: ', m.source_region_name)
FROM datalab_detail_row AS d
JOIN datalab_region_mapping AS m
  ON m.source_region_name = REPLACE(d.source_region_name, '_', ' ')
WHERE d.source_region_code IS NOT NULL
  AND LOCATE('_', d.source_region_name) > 0
ON DUPLICATE KEY UPDATE
  canonical_region_id = VALUES(canonical_region_id),
  mapping_method = VALUES(mapping_method),
  valid_from = VALUES(valid_from),
  valid_to = VALUES(valid_to),
  mapping_note = VALUES(mapping_note);

CREATE TABLE IF NOT EXISTS province_sido_mapping (
  province_name VARCHAR(100) NOT NULL,
  canonical_sido_code VARCHAR(2) NOT NULL,
  PRIMARY KEY (province_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO province_sido_mapping (province_name, canonical_sido_code)
VALUES
  ('서울특별시','11'), ('서울','11'),
  ('부산광역시','26'), ('부산','26'),
  ('대구광역시','27'), ('대구','27'),
  ('인천광역시','28'), ('인천','28'),
  ('광주광역시','12'), ('광주','12'),
  ('전라남도','12'), ('전남','12'),
  ('전남광주통합특별시','12'),
  ('대전광역시','30'), ('대전','30'),
  ('울산광역시','31'), ('울산','31'),
  ('세종특별자치시','36'), ('세종','36'),
  ('경기도','41'), ('경기','41'),
  ('충청북도','43'), ('충북','43'),
  ('충청남도','44'), ('충남','44'),
  ('전라북도','52'), ('전북특별자치도','52'), ('전북','52'),
  ('경상북도','47'), ('경북','47'),
  ('경상남도','48'), ('경남','48'),
  ('강원도','51'), ('강원특별자치도','51'), ('강원','51'),
  ('제주특별자치도','50'), ('제주','50')
ON DUPLICATE KEY UPDATE
  canonical_sido_code = VALUES(canonical_sido_code);

CREATE TABLE IF NOT EXISTS attraction_region_map (
  province_name VARCHAR(100) NOT NULL,
  district_name VARCHAR(150) NOT NULL,
  canonical_region_id VARCHAR(20) NOT NULL,
  mapping_method VARCHAR(40) NOT NULL,
  mapping_note VARCHAR(255) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (province_name, district_name),
  KEY ix_attraction_map_canonical (canonical_region_id),
  CONSTRAINT fk_attraction_map_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELETE FROM attraction_region_map
WHERE mapping_method <> 'manual';

-- 같은 이름이 여러 시도에 있어도 시도코드까지 함께 사용해 구분합니다.
INSERT IGNORE INTO attraction_region_map
  (province_name, district_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  a.province_name,
  a.district_name,
  r.region_id,
  'province_and_name',
  '시도와 시군구 이름 일치'
FROM major_attraction_visitors_monthly AS a
JOIN province_sido_mapping AS p
  ON p.province_name = a.province_name
JOIN dim_region AS r
  ON r.sido_code = p.canonical_sido_code
 AND r.region_name = a.district_name;

-- 일반구는 기존 DataLab의 상위 시 매핑을 재사용합니다.
INSERT IGNORE INTO attraction_region_map
  (province_name, district_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  a.province_name,
  a.district_name,
  m.canonical_region_id,
  'datalab_parent_name',
  m.mapping_note
FROM major_attraction_visitors_monthly AS a
JOIN datalab_region_mapping AS m
  ON m.source_region_name = a.district_name
WHERE m.mapping_type IN ('parent_city', 'reform_old', 'reform_new', 'direct');

-- 인천 행정개편 합산그룹은 짧은 구 이름을 명시적으로 연결합니다.
INSERT IGNORE INTO attraction_region_map
  (province_name, district_name, canonical_region_id,
   mapping_method, mapping_note)
SELECT DISTINCT
  a.province_name,
  a.district_name,
  CASE
    WHEN a.district_name IN ('중구','동구','제물포구','영종구') THEN 'IC_MID'
    WHEN a.district_name IN ('서구','검단구','서해구') THEN 'INCHEON_WEST'
  END,
  'incheon_reform',
  '인천 2026 행정개편 전후 합산그룹'
FROM major_attraction_visitors_monthly AS a
JOIN province_sido_mapping AS p
  ON p.province_name = a.province_name
 AND p.canonical_sido_code = '28'
WHERE a.district_name IN ('중구','동구','제물포구','영종구','서구','검단구','서해구');

-- 특례시 표기와 행정구역 개편 전 시군명을 현재 228개 분석 정본에 연결합니다.
INSERT INTO attraction_region_map
  (province_name, district_name, canonical_region_id,
   mapping_method, mapping_note)
VALUES
  ('경상남도','창원특례시','48120','manual','특례시 표기를 창원시 정본으로 연결'),
  ('충청북도','청원군','43110','manual','2014년 통합 전 청원군을 청주시 정본으로 연결'),
  ('경상남도','마산시','48120','manual','2010년 통합 전 마산시를 창원시 정본으로 연결'),
  ('경상남도','진해시','48120','manual','2010년 통합 전 진해시를 창원시 정본으로 연결'),
  ('경기도','용인특례시','41460','manual','특례시 표기를 용인시 정본으로 연결'),
  ('충청남도','당진군','44270','manual','2012년 승격 전 당진군을 당진시 정본으로 연결'),
  ('경기도','수원특례시','41110','manual','특례시 표기를 수원시 정본으로 연결'),
  ('경기도','고양특례시','41280','manual','특례시 표기를 고양시 정본으로 연결'),
  ('경기도','화성특례시','41590','manual','특례시 표기를 화성시 정본으로 연결')
ON DUPLICATE KEY UPDATE
  canonical_region_id = VALUES(canonical_region_id),
  mapping_method = VALUES(mapping_method),
  mapping_note = VALUES(mapping_note);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_detail_mapped_raw AS
SELECT
  d.*,
  m.canonical_region_id,
  r.region_name AS canonical_region_name,
  m.mapping_method,
  m.mapping_note
FROM datalab_detail_row AS d
JOIN datalab_detail_region_map AS m
  ON m.source_region_code = d.source_region_code
 AND m.source_region_name = COALESCE(d.source_region_name, '')
JOIN dim_region AS r
  ON r.region_id = m.canonical_region_id
WHERE (m.valid_from IS NULL
       OR COALESCE(d.observed_month, d.query_end_month, d.query_start_month) >= m.valid_from)
  AND (m.valid_to IS NULL
       OR COALESCE(d.observed_month, d.query_end_month, d.query_start_month) <= m.valid_to);

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_datalab_detail_unmapped AS
SELECT
  d.source_region_code,
  COALESCE(d.source_region_name, '') AS source_region_name,
  COUNT(*) AS rows_actual,
  MIN(COALESCE(d.observed_month, d.query_start_month)) AS date_min,
  MAX(COALESCE(d.observed_month, d.query_end_month)) AS date_max
FROM datalab_detail_row AS d
LEFT JOIN datalab_detail_region_map AS m
  ON m.source_region_code = d.source_region_code
 AND m.source_region_name = COALESCE(d.source_region_name, '')
WHERE m.source_region_code IS NULL
GROUP BY d.source_region_code, COALESCE(d.source_region_name, '');

CREATE OR REPLACE ALGORITHM=UNDEFINED SQL SECURITY INVOKER
VIEW vw_attraction_region_unmapped AS
SELECT
  a.province_name,
  a.district_name,
  COUNT(*) AS rows_actual,
  COUNT(DISTINCT a.attraction_name) AS attractions,
  MIN(a.observed_month) AS date_min,
  MAX(a.observed_month) AS date_max
FROM major_attraction_visitors_monthly AS a
LEFT JOIN attraction_region_map AS m
  ON m.province_name = a.province_name
 AND m.district_name = a.district_name
WHERE m.province_name IS NULL
GROUP BY a.province_name, a.district_name;
