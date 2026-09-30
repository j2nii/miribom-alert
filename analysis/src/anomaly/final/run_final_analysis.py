#!/usr/bin/env python3
from __future__ import annotations
import csv
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'analysis_output'

def connect():
    import pymysql

    load_dotenv(ROOT/'.env')
    if not os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQL_PASSWORD')=='CHANGE_ME':
        raise SystemExit('.env의 MYSQL_PASSWORD를 실제 비밀번호로 변경하세요.')
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST','127.0.0.1'),port=int(os.getenv('MYSQL_PORT','3306')),
        user=os.getenv('MYSQL_USER','yaho_loader'),password=os.environ['MYSQL_PASSWORD'],
        database=os.getenv('MYSQL_DATABASE','tour_earlywarning'),charset='utf8mb4',
        autocommit=False,cursorclass=pymysql.cursors.DictCursor)

def statements(path):
    text=path.read_text(encoding='utf-8-sig')
    result=[]; buf=[]; quote=None
    i=0
    while i<len(text):
        c=text[i]; nxt=text[i+1] if i+1<len(text) else ''
        if quote:
            buf.append(c)
            if c==quote and (i==0 or text[i-1]!='\\'): quote=None
            i+=1; continue
        if c in "'\"`": quote=c; buf.append(c); i+=1; continue
        if c=='-' and nxt=='-':
            i+=2
            while i<len(text) and text[i] not in '\r\n': i+=1
            continue
        if c=='#':
            while i<len(text) and text[i] not in '\r\n': i+=1
            continue
        if c==';':
            sql=''.join(buf).strip()
            if sql: result.append(sql)
            buf=[]
        else: buf.append(c)
        i+=1
    sql=''.join(buf).strip()
    if sql: result.append(sql)
    return result

def export(cur,name,query):
    cur.execute(query); rows=cur.fetchall(); path=OUT/name
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        if rows:
            w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print(f'[출력] {name}: {len(rows):,}행')

def main():
    OUT.mkdir(exist_ok=True)
    conn=connect()
    try:
        with conn.cursor() as cur:
            sqls=statements(ROOT/'40_create_final_analysis.sql')
            print(f'[분석 뷰] {len(sqls)}개 SQL 실행')
            for i,sql in enumerate(sqls,1):
                try: cur.execute(sql)
                except Exception as e: raise RuntimeError(f'{i}번째 SQL 실패: {sql[:100]}') from e
            conn.commit()

            for sql in statements(ROOT/'41_validate_final_analysis.sql'):
                cur.execute(sql)
                if cur.description:
                    rows=cur.fetchall()
                    print('\n'+'\t'.join(x[0] for x in cur.description))
                    for r in rows: print('\t'.join('NULL' if v is None else str(v) for v in r.values()))

            export(cur,'anomaly_final_450.csv','SELECT * FROM vw_final_anomaly_analysis ORDER BY peak_anomaly_score DESC')
            export(cur,'festival_matched_episodes.csv',"SELECT * FROM vw_final_anomaly_analysis WHERE festival_match_count>0 ORDER BY peak_anomaly_score DESC")
            export(cur,'festival_leadtime.csv',"""SELECT region_id,region_name,episode_no,search_peak_date,visitor_peak_date,
                representative_festival_name,festival_start,festival_end,festival_exact_overlap,
                search_to_festival_lead_days,visitor_to_festival_lead_days,peak_anomaly_score
                FROM vw_final_anomaly_analysis WHERE festival_match_count>0
                ORDER BY search_to_festival_lead_days DESC""")
            export(cur,'unexplained_candidates.csv',"SELECT * FROM vw_final_anomaly_analysis WHERE final_explanation_group='unexplained_candidate' ORDER BY peak_anomaly_score DESC")
            export(cur,'final_metrics.csv','SELECT * FROM vw_final_anomaly_metrics')
            export(cur,'explanation_group_summary.csv',"""SELECT final_explanation_group,COUNT(*) episodes,
                COUNT(DISTINCT region_id) regions,ROUND(AVG(peak_anomaly_score),3) avg_anomaly_score
                FROM vw_final_anomaly_analysis GROUP BY final_explanation_group ORDER BY episodes DESC""")
            export(cur,'yeongwol_geoje_cases.csv',"""SELECT * FROM vw_final_anomaly_analysis
                WHERE region_name IN ('영월군','거제시') ORDER BY region_name,visitor_peak_date""")
        print(f'\n[완료] {OUT}')
        return 0
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

if __name__=='__main__': raise SystemExit(main())
