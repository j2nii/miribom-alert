-- DataLab 259 source regions -> 228 canonical analysis regions.
-- Idempotent: this file can be executed repeatedly.

SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS datalab_region_mapping (
  source_region_name VARCHAR(100) NOT NULL,
  canonical_region_id VARCHAR(20) NOT NULL,
  mapping_type VARCHAR(30) NOT NULL,
  valid_from DATE NULL,
  valid_to DATE NULL,
  mapping_note VARCHAR(255) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (source_region_name),
  KEY ix_datalab_mapping_canonical (canonical_region_id),
  CONSTRAINT fk_datalab_mapping_region
    FOREIGN KEY (canonical_region_id) REFERENCES dim_region(region_id),
  CONSTRAINT ck_datalab_mapping_dates
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
) ENGINE=InnoDB;

-- Preserve the 211 source names that were already mapped safely.
INSERT INTO datalab_region_mapping
  (source_region_name, canonical_region_id, mapping_type,
   valid_from, valid_to, mapping_note)
SELECT source_region_name,
       MAX(canonical_region_id),
       'direct',
       NULL,
       NULL,
       '기존 1:1 자동 매핑'
FROM datalab_monthly_panel
WHERE canonical_region_id IS NOT NULL
GROUP BY source_region_name
ON DUPLICATE KEY UPDATE
  canonical_region_id = VALUES(canonical_region_id),
  mapping_type = VALUES(mapping_type),
  valid_from = VALUES(valid_from),
  valid_to = VALUES(valid_to),
  mapping_note = VALUES(mapping_note);

-- The remaining 48 source names.
-- General districts map to the canonical parent city. Aggregation is done only
-- in vw_datalab_canonical_monthly; do not SUM the raw table directly.
INSERT INTO datalab_region_mapping
  (source_region_name, canonical_region_id, mapping_type,
   valid_from, valid_to, mapping_note)
VALUES
  ('강서구',                 '26440', 'disambiguated', NULL, NULL, '서울특별시 강서구가 별도로 존재하므로 부산광역시 강서구'),
  ('고성군',                 '48820', 'disambiguated', NULL, NULL, '강원특별자치도 고성군이 별도로 존재하므로 경상남도 고성군'),

  ('고양시 덕양구',          '41280', 'parent_city', NULL, NULL, '고양시 일반구'),
  ('고양시 일산동구',        '41280', 'parent_city', NULL, NULL, '고양시 일반구'),
  ('고양시 일산서구',        '41280', 'parent_city', NULL, NULL, '고양시 일반구'),
  ('부천시 소사구',          '41190', 'parent_city', NULL, NULL, '부천시 일반구'),
  ('부천시 오정구',          '41190', 'parent_city', NULL, NULL, '부천시 일반구'),
  ('부천시 원미구',          '41190', 'parent_city', NULL, NULL, '부천시 일반구'),
  ('성남시 분당구',          '41130', 'parent_city', NULL, NULL, '성남시 일반구'),
  ('성남시 수정구',          '41130', 'parent_city', NULL, NULL, '성남시 일반구'),
  ('성남시 중원구',          '41130', 'parent_city', NULL, NULL, '성남시 일반구'),
  ('수원시 권선구',          '41110', 'parent_city', NULL, NULL, '수원시 일반구'),
  ('수원시 영통구',          '41110', 'parent_city', NULL, NULL, '수원시 일반구'),
  ('수원시 장안구',          '41110', 'parent_city', NULL, NULL, '수원시 일반구'),
  ('수원시 팔달구',          '41110', 'parent_city', NULL, NULL, '수원시 일반구'),
  ('안산시 단원구',          '41270', 'parent_city', NULL, NULL, '안산시 일반구'),
  ('안산시 상록구',          '41270', 'parent_city', NULL, NULL, '안산시 일반구'),
  ('안양시 동안구',          '41170', 'parent_city', NULL, NULL, '안양시 일반구'),
  ('안양시 만안구',          '41170', 'parent_city', NULL, NULL, '안양시 일반구'),
  ('용인시 기흥구',          '41460', 'parent_city', NULL, NULL, '용인시 일반구'),
  ('용인시 수지구',          '41460', 'parent_city', NULL, NULL, '용인시 일반구'),
  ('용인시 처인구',          '41460', 'parent_city', NULL, NULL, '용인시 일반구'),
  ('전주시 덕진구',          '52110', 'parent_city', NULL, NULL, '전주시 일반구'),
  ('전주시 완산구',          '52110', 'parent_city', NULL, NULL, '전주시 일반구'),
  ('창원시 마산합포구',      '48120', 'parent_city', NULL, NULL, '창원시 일반구'),
  ('창원시 마산회원구',      '48120', 'parent_city', NULL, NULL, '창원시 일반구'),
  ('창원시 성산구',          '48120', 'parent_city', NULL, NULL, '창원시 일반구'),
  ('창원시 의창구',          '48120', 'parent_city', NULL, NULL, '창원시 일반구'),
  ('창원시 진해구',          '48120', 'parent_city', NULL, NULL, '창원시 일반구'),
  ('천안시 동남구',          '44130', 'parent_city', NULL, NULL, '천안시 일반구'),
  ('천안시 서북구',          '44130', 'parent_city', NULL, NULL, '천안시 일반구'),
  ('청주시 상당구',          '43110', 'parent_city', NULL, NULL, '청주시 일반구'),
  ('청주시 서원구',          '43110', 'parent_city', NULL, NULL, '청주시 일반구'),
  ('청주시 청원구',          '43110', 'parent_city', NULL, NULL, '청주시 일반구'),
  ('청주시 흥덕구',          '43110', 'parent_city', NULL, NULL, '청주시 일반구'),
  ('포항시 남구',            '47110', 'parent_city', NULL, NULL, '포항시 일반구'),
  ('포항시 북구',            '47110', 'parent_city', NULL, NULL, '포항시 일반구'),

  ('인천광역시 동구',        'IC_MID',       'reform_old', NULL,         '2026-06-01', '인천 중구권 개편 전'),
  ('인천광역시 중구',        'IC_MID',       'reform_old', NULL,         '2026-06-01', '인천 중구권 개편 전'),
  ('인천광역시 서구',        'INCHEON_WEST', 'reform_old', NULL,         '2026-06-01', '인천 서구권 개편 전'),
  ('제물포구',               'IC_MID',       'reform_new', '2026-07-01', NULL,         '인천 중구권 개편 후'),
  ('영종구',                 'IC_MID',       'reform_new', '2026-07-01', NULL,         '인천 중구권 개편 후'),
  ('서해구',                 'INCHEON_WEST', 'reform_new', '2026-07-01', NULL,         '인천 서구권 개편 후'),
  ('검단구',                 'INCHEON_WEST', 'reform_new', '2026-07-01', NULL,         '인천 서구권 개편 후'),

  ('화성시 동탄구',          '41590', 'reform_new', '2026-02-01', NULL, '화성시 개편 후 일반구'),
  ('화성시 만세구',          '41590', 'reform_new', '2026-02-01', NULL, '화성시 개편 후 일반구'),
  ('화성시 병점구',          '41590', 'reform_new', '2026-02-01', NULL, '화성시 개편 후 일반구'),
  ('화성시 효행구',          '41590', 'reform_new', '2026-02-01', NULL, '화성시 개편 후 일반구')
ON DUPLICATE KEY UPDATE
  canonical_region_id = VALUES(canonical_region_id),
  mapping_type = VALUES(mapping_type),
  valid_from = VALUES(valid_from),
  valid_to = VALUES(valid_to),
  mapping_note = VALUES(mapping_note);

-- Remove mappings for names that are no longer present in the source table.
DELETE m
FROM datalab_region_mapping AS m
LEFT JOIN (
  SELECT DISTINCT source_region_name
  FROM datalab_monthly_panel
) AS p ON p.source_region_name = m.source_region_name
WHERE p.source_region_name IS NULL;

-- Keep the convenience FK column in the raw panel synchronized.
UPDATE datalab_monthly_panel AS p
JOIN datalab_region_mapping AS m
  ON m.source_region_name = p.source_region_name
SET p.canonical_region_id = m.canonical_region_id
WHERE NOT (p.canonical_region_id <=> m.canonical_region_id);

SELECT 'mapping_created' AS check_name,
       COUNT(*) AS source_regions,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions
FROM datalab_region_mapping;

