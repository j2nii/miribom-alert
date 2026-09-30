SET NAMES utf8mb4;
USE tour_earlywarning;

-- DataLab 세부 원본의 밑줄 일반구 표기를 기존 259→228 지역 매핑과 연결합니다.
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

-- 특례시 표기와 행정구역 개편 전 시군명을 현재 분석 정본에 연결합니다.
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

SELECT 'detail_mapping_after_fix' AS check_name,
       COUNT(*) AS mapped_pairs,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions,
       (SELECT COUNT(*) FROM vw_datalab_detail_unmapped) AS unmapped_pairs
FROM datalab_detail_region_map;

SELECT 'attraction_mapping_after_fix' AS check_name,
       COUNT(*) AS mapped_districts,
       COUNT(DISTINCT canonical_region_id) AS canonical_regions,
       (SELECT COUNT(*) FROM vw_attraction_region_unmapped) AS unmapped_districts
FROM attraction_region_map;
