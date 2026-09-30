SET NAMES utf8mb4;
USE tour_earlywarning;

CREATE TABLE IF NOT EXISTS event_evidence_targeted_checkpoint (
  region_id VARCHAR(20) NOT NULL,
  episode_no BIGINT NOT NULL,
  query_category VARCHAR(30) NOT NULL,
  search_type ENUM('news','blog','webkr') NOT NULL,
  status ENUM('success','failed') NOT NULL,
  attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
  result_count INT UNSIGNED NOT NULL DEFAULT 0,
  last_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_error TEXT NULL,
  PRIMARY KEY (region_id, episode_no, query_category, search_type)
) ENGINE=InnoDB;

SELECT 'targeted_checkpoint' AS check_name,
       COUNT(*) AS checkpoint_rows,
       SUM(status = 'success') AS success_rows,
       SUM(status = 'failed') AS failed_rows
FROM event_evidence_targeted_checkpoint;
