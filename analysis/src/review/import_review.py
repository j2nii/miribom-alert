from __future__ import annotations
import csv
from common import OUT, connect

ALLOWED = {"true_signal", "calendar_effect", "weather_or_disruption", "false_alarm", "uncertain"}

def main():
    path = OUT / "human_review_top20.csv"
    if not path.exists():
        raise SystemExit("먼저 02_prepare_review.cmd를 실행하세요.")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    invalid = [(i+2, r.get("human_label", "")) for i,r in enumerate(rows)
               if r.get("human_label", "").strip() not in ALLOWED]
    if invalid:
        sample = ", ".join(f"{line}행={value or '빈칸'}" for line,value in invalid[:10])
        raise SystemExit(f"human_label을 20건 모두 입력하세요. 오류: {sample}")

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS anomaly_human_review (
                  region_id VARCHAR(20) NOT NULL,
                  episode_no DECIMAL(32,0) NOT NULL,
                  human_label VARCHAR(32) NOT NULL,
                  confirmed_cause VARCHAR(500) NULL,
                  review_note TEXT NULL,
                  reviewer VARCHAR(100) NULL,
                  reviewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY(region_id, episode_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            sql = """
                INSERT INTO anomaly_human_review
                  (region_id,episode_no,human_label,confirmed_cause,review_note,reviewer)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  human_label=VALUES(human_label), confirmed_cause=VALUES(confirmed_cause),
                  review_note=VALUES(review_note), reviewer=VALUES(reviewer),
                  reviewed_at=CURRENT_TIMESTAMP
            """
            for r in rows:
                cur.execute(sql, (r["region_id"], r["episode_no"], r["human_label"].strip(),
                                  r.get("confirmed_cause") or None, r.get("review_note") or None,
                                  r.get("reviewer") or None))
            cur.execute("DROP VIEW IF EXISTS vw_anomaly_human_review_metrics")
            cur.execute("""
                CREATE VIEW vw_anomaly_human_review_metrics AS
                SELECT COUNT(*) AS reviewed_episodes,
                       SUM(human_label='true_signal') AS true_signals,
                       SUM(human_label='false_alarm') AS false_alarms,
                       SUM(human_label='calendar_effect') AS calendar_effects,
                       SUM(human_label='weather_or_disruption') AS weather_or_disruptions,
                       SUM(human_label='uncertain') AS uncertain,
                       ROUND(100*SUM(human_label='true_signal') /
                         NULLIF(SUM(human_label IN ('true_signal','false_alarm')),0),2) AS reviewed_precision_pct,
                       ROUND(100*SUM(human_label='false_alarm') /
                         NULLIF(SUM(human_label IN ('true_signal','false_alarm')),0),2) AS reviewed_false_alarm_pct
                FROM anomaly_human_review
            """)
            cur.execute("SELECT * FROM vw_anomaly_human_review_metrics")
            result = cur.fetchone()
            conn.commit()
        print("\n[검토 지표]")
        for k,v in result.items(): print(f"{k}: {v}")
        print("\n주의: 이 값은 상위 20건 표본의 검토 결과이며 450건 전체 성능이 아닙니다.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())

