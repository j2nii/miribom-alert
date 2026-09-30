-- 반드시 비밀번호와 팀원의 접속 원본 공인 IP를 수정한 뒤 root 계정으로 실행한다.
USE yaho_radar;

CREATE USER IF NOT EXISTS 'yaho_loader'@'localhost'
  IDENTIFIED BY '비번';
CREATE USER IF NOT EXISTS 'yaho_loader'@'127.0.0.1'
  IDENTIFIED BY '비번';
GRANT ALL PRIVILEGES ON yaho_radar.* TO 'yaho_loader'@'localhost';
GRANT ALL PRIVILEGES ON yaho_radar.* TO 'yaho_loader'@'127.0.0.1';

CREATE ROLE IF NOT EXISTS 'yaho_readonly';
GRANT SELECT, SHOW VIEW ON yaho_radar.* TO 'yaho_readonly';

-- 아래 세 줄의 계정명/IP/비밀번호를 팀원마다 복제한다.
-- 203.0.113.10은 예시이므로 팀원이 접속하는 장소의 실제 공인 IP로 바꾼다.
CREATE USER IF NOT EXISTS 'teammate1'@'203.0.113.10'
  IDENTIFIED BY 'CHANGE_TEAMMATE_PASSWORD' REQUIRE SSL;
GRANT 'yaho_readonly' TO 'teammate1'@'203.0.113.10';
SET DEFAULT ROLE 'yaho_readonly' TO 'teammate1'@'203.0.113.10';

-- 쓰기 담당 팀원이 꼭 필요할 때만 별도 역할을 부여한다.
CREATE ROLE IF NOT EXISTS 'yaho_crawler_writer';
GRANT SELECT ON yaho_radar.* TO 'yaho_crawler_writer';
GRANT INSERT, UPDATE ON yaho_radar.crawl_run TO 'yaho_crawler_writer';
GRANT INSERT, UPDATE ON yaho_radar.crawl_checkpoint TO 'yaho_crawler_writer';
GRANT INSERT ON yaho_radar.raw_payload TO 'yaho_crawler_writer';

-- 예: 필요한 팀원에게만 다음 두 줄의 주석을 풀어 실행
-- GRANT 'yaho_crawler_writer' TO 'teammate1'@'203.0.113.10';
-- SET DEFAULT ROLE 'yaho_readonly','yaho_crawler_writer' TO 'teammate1'@'203.0.113.10';

-- 팀원 공인 IP가 자주 바뀌어 정말 제한할 수 없을 때만 아래 형태를 사용한다.
-- 이 경우 강한 비밀번호, REQUIRE SSL, Windows 방화벽 제한을 반드시 유지한다.
-- CREATE USER 'teammate_dynamic'@'%' IDENTIFIED BY 'CHANGE_PASSWORD' REQUIRE SSL;
-- GRANT 'yaho_readonly' TO 'teammate_dynamic'@'%';
-- SET DEFAULT ROLE 'yaho_readonly' TO 'teammate_dynamic'@'%';
