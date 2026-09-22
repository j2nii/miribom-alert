from __future__ import annotations
import csv
from pathlib import Path
from common import OUT, connect

LABELS = "true_signal / calendar_effect / weather_or_disruption / false_alarm / uncertain"

def write_csv(path: Path, rows, extra_fields=()):
    rows = list(rows)
    fields = list(rows[0].keys()) if rows else []
    fields.extend(x for x in extra_fields if x not in fields)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            item = dict(row)
            for field in extra_fields:
                item.setdefault(field, "")
            w.writerow(item)
    print(f"[출력] {path.name}: {len(rows):,}행")

def main():
    OUT.mkdir(exist_ok=True)
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT region_id, region_name, episode_no, episode_start, episode_end,
                       search_peak_date, visitor_peak_date, peak_anomaly_score,
                       representative_festival_name, festival_start, festival_end,
                       search_to_festival_lead_days, visitor_to_festival_lead_days,
                       final_explanation_group
                FROM vw_final_anomaly_analysis
                WHERE final_explanation_group = 'festival_pre_signal'
                ORDER BY peak_anomaly_score DESC
            """)
            lead_rows = cur.fetchall()
            write_csv(OUT / "festival_pre_signal_26.csv", lead_rows)

            # MySQL 버전 차이 없이 중앙값을 계산한다.
            search_positive = sorted(int(r["search_to_festival_lead_days"])
                                     for r in lead_rows
                                     if r["search_to_festival_lead_days"] is not None
                                     and int(r["search_to_festival_lead_days"]) > 0)
            visitor_positive = sorted(int(r["visitor_to_festival_lead_days"])
                                      for r in lead_rows
                                      if r["visitor_to_festival_lead_days"] is not None
                                      and int(r["visitor_to_festival_lead_days"]) > 0)
            def median(values):
                n=len(values)
                if not n: return None
                return values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2

            lead_summary = [{
                "pre_signal_episodes": len(lead_rows),
                "regions": len({r["region_id"] for r in lead_rows}),
                "search_positive_episodes": len(search_positive),
                "mean_search_lead_days": round(sum(search_positive)/len(search_positive),2) if search_positive else "",
                "median_search_lead_days": median(search_positive) or "",
                "search_lead_3plus": sum(x>=3 for x in search_positive),
                "search_lead_7plus": sum(x>=7 for x in search_positive),
                "visitor_positive_episodes": len(visitor_positive),
                "mean_visitor_lead_days": round(sum(visitor_positive)/len(visitor_positive),2) if visitor_positive else "",
                "median_visitor_lead_days": median(visitor_positive) or "",
                "visitor_lead_3plus": sum(x>=3 for x in visitor_positive),
                "visitor_lead_7plus": sum(x>=7 for x in visitor_positive),
            }]
            write_csv(OUT / "leadtime_metrics.csv", lead_summary)

            cur.execute("""
                SELECT region_id, region_name, episode_no, episode_start, episode_end,
                       search_peak_date, visitor_peak_date, peak_anomaly_score,
                       peak_naver_ratio, peak_visitor_ratio,
                       matched_calendar_days, calendar_effect_names,
                       weather_context_type,
                       evidence_title, evidence_url, auto_cause_type, auto_confidence,
                       datalab_sns_mentions, datalab_navigation_searches,
                       datalab_outsider_spend_krw_thousand,
                       final_explanation_group
                FROM vw_final_anomaly_analysis
                WHERE final_explanation_group = 'unexplained_candidate'
                ORDER BY peak_anomaly_score DESC
                LIMIT 20
            """)
            review_rows = cur.fetchall()
            write_csv(OUT / "human_review_top20.csv", review_rows,
                      ("human_label", "confirmed_cause", "review_note", "reviewer"))

            cur.execute("""
                SELECT * FROM vw_final_anomaly_analysis
                WHERE region_name IN ('영월군','거제시')
                ORDER BY region_name, visitor_peak_date
            """)
            write_csv(OUT / "yeongwol_geoje_review.csv", cur.fetchall(),
                      ("selected_for_presentation", "case_note"))

        guide = OUT / "검토방법.txt"
        guide.write_text(
            "human_review_top20.csv의 human_label만 우선 입력하세요.\n"
            f"허용값: {LABELS}\n\n"
            "true_signal: 실제 관광 이슈·축제·바이럴 근거 확인\n"
            "calendar_effect: 명절·공휴일·휴가철로 설명\n"
            "weather_or_disruption: 날씨·재난·교통 장애로 설명\n"
            "false_alarm: 관광 이상 현상으로 보기 어려움\n"
            "uncertain: 현재 근거로 판단 불가\n\n"
            "가능하면 confirmed_cause, review_note, reviewer도 입력한 뒤 저장하고 "
            "03_import_review.cmd를 실행하세요.\n",
            encoding="utf-8-sig")
        print(f"[안내] 허용 라벨: {LABELS}")
        print(f"[완료] {OUT}")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
