from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import pymysql
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "pilot_output"
REVIEW = OUT / "keyword_review.csv"
DAILY = OUT / "pilot_search_daily.csv"

CASES = {
    "51750": {"region_name": "영월군", "start": "2025-12-01", "end": "2026-04-30",
              "case_start": "2026-02-01", "case_end": "2026-03-31"},
    "48310": {"region_name": "거제시", "start": "2025-12-01", "end": "2026-06-30",
              "case_start": "2026-02-01", "case_end": "2026-05-31"},
}

MANUAL = {
    "51750": {
        "region": ["영월", "영월군"],
        "intent": ["영월 여행", "영월 가볼만한곳", "영월 맛집", "영월 축제"],
    },
    "48310": {
        "region": ["거제", "거제시", "거제도"],
        "intent": ["거제 여행", "거제도 여행", "거제 가볼만한곳", "거제 맛집"],
        "content": ["리센느", "원이", "미나미", "갸루와 거제"],
        "poi": ["덕포해수욕장", "매미성", "외도 보타니아", "구조라해수욕장", "윤돌섬",
                "순대리아", "모래성분식포차"],
    },
}

STOP = {
    "그리고","하지만","대한","관련","지역","관광","여행","축제","행사","소식","공연","개최","모집",
    "영상","뉴스","공식","이번","주요","오늘","올해","정말","추천","정보","대한민국","강원","경남",
    "영월","영월군","거제","거제시","거제도","2023","2024","2025","2026",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS viral_keyword_dictionary (
  region_id VARCHAR(20) NOT NULL,
  keyword_text VARCHAR(255) NOT NULL,
  keyword_type ENUM('region','poi','event','content','intent','other') NOT NULL,
  source_system VARCHAR(50) NOT NULL,
  evidence_count INT NOT NULL DEFAULT 1,
  relevance_score DECIMAL(10,4) NULL,
  valid_from DATE NULL,
  valid_to DATE NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  discovered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY(region_id,keyword_text),
  KEY ix_viral_keyword_active(region_id,active,keyword_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS viral_keyword_signal_daily (
  region_id VARCHAR(20) NOT NULL,
  observed_date DATE NOT NULL,
  keyword_group VARCHAR(30) NOT NULL,
  ratio DECIMAL(18,8) NOT NULL,
  keywords_json JSON NOT NULL,
  collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(region_id,observed_date,keyword_group),
  KEY ix_viral_signal_group_date(keyword_group,observed_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def config():
    load_dotenv(ROOT / ".env")
    required = ["MYSQL_PASSWORD"]
    for key in required:
        if not os.getenv(key) or os.getenv(key) == "CHANGE_ME":
            raise SystemExit(f".env의 {key}를 실제 값으로 변경하세요.")


def conn():
    config()
    return pymysql.connect(host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")), user=os.getenv("MYSQL_USER", "yaho_loader"),
        password=os.getenv("MYSQL_PASSWORD"), database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4", autocommit=False, cursorclass=pymysql.cursors.DictCursor)


def table_exists(cur, name):
    cur.execute("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s", (name,))
    return cur.fetchone()["n"] > 0


def query_df(db, sql, params=None):
    """DictCursor 결과를 pandas가 오해하지 않도록 명시적으로 변환한다."""
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        columns = [item[0] for item in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def create_tables():
    db = conn()
    try:
        with db.cursor() as cur:
            for stmt in [x.strip() for x in SCHEMA.split(";") if x.strip()]: cur.execute(stmt)
        db.commit(); print("[OK] 검색어 사전 및 일별 신호 테이블 생성")
    finally: db.close()


def clean_text(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(s or "")))).strip()


def add(rows, seen, rid, kind, keyword, source, count=1, include=1, note=""):
    keyword = clean_text(keyword).strip("-_/|·,.'\"[]()")
    if len(keyword) < 2 or len(keyword) > 40: return
    key = (rid, keyword)
    if key in seen: return
    seen.add(key)
    rows.append({"region_id":rid,"region_name":CASES[rid]["region_name"],"keyword_type":kind,
                 "keyword":keyword,"source":source,"evidence_count":count,"include":include,"review_note":note})


def prepare():
    OUT.mkdir(exist_ok=True)
    db = conn(); rows=[]; seen=set()
    try:
        with db.cursor() as cur:
            for rid, case in CASES.items():
                for kind, words in MANUAL.get(rid, {}).items():
                    for word in words: add(rows,seen,rid,kind,word,"manual_seed",1,1)

                if table_exists(cur,"domestic_interest_attraction_rank"):
                    cur.execute("""SELECT attraction_name,COALESCE(total_registration_count,0) n
                        FROM domestic_interest_attraction_rank WHERE region_name LIKE %s
                        ORDER BY ranking LIMIT 15""", ("%"+case["region_name"]+"%",))
                    for x in cur.fetchall(): add(rows,seen,rid,"poi",x["attraction_name"],"attraction_rank",x["n"] or 1,1)

                if table_exists(cur,"major_attraction_visitors_monthly"):
                    cur.execute("""SELECT attraction_name,COUNT(*) n FROM major_attraction_visitors_monthly
                        WHERE district_name LIKE %s GROUP BY attraction_name ORDER BY n DESC LIMIT 15""",
                        ("%"+case["region_name"]+"%",))
                    for x in cur.fetchall(): add(rows,seen,rid,"poi",x["attraction_name"],"attraction_visitors",x["n"],1)

                if table_exists(cur,"event") and table_exists(cur,"event_point"):
                    cur.execute("""SELECT e.event_name,COUNT(*) n FROM event e JOIN event_point p ON p.event_id=e.event_id
                        WHERE e.region_id=%s AND p.point_date BETWEEN %s AND %s GROUP BY e.event_id,e.event_name""",
                        (rid,case["start"],case["end"]))
                    for x in cur.fetchall(): add(rows,seen,rid,"event",x["event_name"],"event_calendar",x["n"],1)

                titles=[]
                if table_exists(cur,"youtube_video"):
                    cur.execute("""SELECT title FROM youtube_video WHERE region_id=%s
                        AND DATE(published_at) BETWEEN %s AND %s""", (rid,case["start"],case["end"]))
                    titles += [x["title"] for x in cur.fetchall()]
                if table_exists(cur,"event_evidence_candidate"):
                    cur.execute("""SELECT title FROM event_evidence_candidate WHERE region_id=%s
                        AND peak_date BETWEEN %s AND %s""", (rid,case["start"],case["end"]))
                    titles += [x["title"] for x in cur.fetchall()]
                tokens=[]
                for title in titles:
                    tokens += [t for t in re.findall(r"[가-힣A-Za-z][가-힣A-Za-z0-9]{1,19}", clean_text(title))
                               if t not in STOP and not t.isdigit()]
                for token,n in Counter(tokens).most_common(40):
                    if n >= 2: add(rows,seen,rid,"content",token,"title_frequency",n,0,"반복 제목어: 사례 직접 관련 시 1")
    finally: db.close()
    df=pd.DataFrame(rows).sort_values(["region_name","keyword_type","include","evidence_count"],ascending=[True,True,False,False])
    df.to_csv(REVIEW,index=False,encoding="utf-8-sig")
    print(f"[출력] {REVIEW} · {len(df)}개 후보")
    print("Excel에서 include를 1/0으로 검토한 뒤 03_collect_pilot.cmd를 실행하세요.")


def naver_request(case, groups):
    key_id=os.getenv("NAVER_KEY_ID","").strip(); secret=os.getenv("NAVER_KEY_SECRET","").strip()
    if not key_id or not secret or "CHANGE_ME" in (key_id,secret):
        raise SystemExit(".env의 NAVER_KEY_ID와 NAVER_KEY_SECRET을 실제 검색어 트렌드 API 키로 변경하세요.")
    body={"startDate":case["start"],"endDate":case["end"],"timeUnit":"date",
          "keywordGroups":[{"groupName":k,"keywords":v[:20]} for k,v in groups.items()]}
    headers={"X-NCP-APIGW-API-KEY-ID":key_id,"X-NCP-APIGW-API-KEY":secret,"Content-Type":"application/json"}
    url="https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
    for attempt in range(4):
        r=requests.post(url,headers=headers,data=json.dumps(body,ensure_ascii=False),timeout=90)
        if r.status_code==200: return r.json()
        if r.status_code==429: time.sleep(30*(attempt+1)); continue
        if r.status_code in (401,403): raise RuntimeError(f"네이버 인증 실패 {r.status_code}: {r.text[:300]}")
        time.sleep(3*(attempt+1))
    raise RuntimeError(f"네이버 호출 실패: {r.status_code} {r.text[:300]}")


def collect():
    config(); OUT.mkdir(exist_ok=True)
    if not REVIEW.exists(): raise SystemExit("먼저 02_prepare_keywords.cmd를 실행하세요.")
    df=pd.read_csv(REVIEW,dtype={"region_id":str})
    if "include" not in df: raise SystemExit("keyword_review.csv에 include 열이 없습니다.")
    df=df[pd.to_numeric(df.include,errors="coerce").fillna(0).eq(1)].copy()
    db=conn(); daily_rows=[]
    try:
        with db.cursor() as cur:
            for rid,case in CASES.items():
                sub=df[df.region_id.eq(rid)]
                groups={k:g.keyword.dropna().astype(str).drop_duplicates().tolist()[:20]
                        for k,g in sub.groupby("keyword_type")}
                groups={k:v for k,v in groups.items() if v}
                if "region" not in groups: raise RuntimeError(f"{case['region_name']} region 검색어가 없습니다.")
                if len(groups)>5: raise RuntimeError(f"{case['region_name']} 검색어 그룹이 5개를 초과했습니다: {list(groups)}")
                print(f"[{case['region_name']}] "+" · ".join(f"{k} {len(v)}개" for k,v in groups.items()))
                payload=naver_request(case,groups)
                for result in payload.get("results",[]):
                    group=result["title"]
                    for point in result.get("data",[]):
                        ratio=float(point["ratio"])
                        daily_rows.append({"region_id":rid,"region_name":case["region_name"],
                            "observed_date":point["period"],"keyword_group":group,"ratio":ratio})
                        cur.execute("""INSERT INTO viral_keyword_signal_daily
                            (region_id,observed_date,keyword_group,ratio,keywords_json)
                            VALUES(%s,%s,%s,%s,%s) AS new
                            ON DUPLICATE KEY UPDATE ratio=new.ratio,keywords_json=new.keywords_json,collected_at=CURRENT_TIMESTAMP""",
                            (rid,point["period"],group,ratio,json.dumps(groups[group],ensure_ascii=False)))
                for _,x in sub.iterrows():
                    cur.execute("""INSERT INTO viral_keyword_dictionary
                        (region_id,keyword_text,keyword_type,source_system,evidence_count,active,valid_from,valid_to)
                        VALUES(%s,%s,%s,%s,%s,1,%s,%s) AS new
                        ON DUPLICATE KEY UPDATE keyword_type=new.keyword_type,source_system=new.source_system,
                        evidence_count=new.evidence_count,active=1,valid_from=new.valid_from,valid_to=new.valid_to""",
                        (rid,x.keyword,x.keyword_type,x.source,int(x.evidence_count),case["start"],case["end"]))
                db.commit(); time.sleep(1)
    finally: db.close()
    pd.DataFrame(daily_rows).to_csv(DAILY,index=False,encoding="utf-8-sig")
    print(f"[완료] {DAILY} · {len(daily_rows):,}행")


def set_font():
    available={x.name for x in font_manager.fontManager.ttflist}
    for f in ["Malgun Gothic","맑은 고딕","NanumGothic","DejaVu Sans"]:
        if f in available: plt.rcParams["font.family"]=f; break
    plt.rcParams["axes.unicode_minus"]=False


def analyze():
    if not DAILY.exists(): raise SystemExit("먼저 03_collect_pilot.cmd를 실행하세요.")
    set_font(); search=pd.read_csv(DAILY,dtype={"region_id":str},parse_dates=["observed_date"])
    db=conn(); summaries=[]
    try:
        for rid,case in CASES.items():
            daily=query_df(db,"""SELECT observed_date,naver_interest,visitors_external FROM vw_daily_core_signal
                WHERE region_id=%s AND observed_date BETWEEN %s AND %s ORDER BY observed_date""",
                (rid,case["start"],case["end"]))
            if daily.empty:
                raise RuntimeError(f"{case['region_name']}의 일별 핵심 신호가 조회되지 않았습니다.")
            daily["observed_date"]=pd.to_datetime(daily.observed_date)
            daily["naver_interest"] = pd.to_numeric(daily["naver_interest"], errors="coerce")
            daily["visitors_external"] = pd.to_numeric(daily["visitors_external"], errors="coerce")
            wide=search[search.region_id.eq(rid)].pivot(index="observed_date",columns="keyword_group",values="ratio").reset_index()
            x=daily.merge(wide,on="observed_date",how="outer").sort_values("observed_date")
            case_mask=x.observed_date.between(case["case_start"],case["case_end"])
            visitor_peak=x.loc[case_mask].sort_values("visitors_external",ascending=False).iloc[0]
            for group in sorted(search.loc[search.region_id.eq(rid),"keyword_group"].unique()):
                peak=x.loc[case_mask].sort_values(group,ascending=False).iloc[0]
                summaries.append({"region_id":rid,"region_name":case["region_name"],"keyword_group":group,
                    "search_peak_date":peak.observed_date.date(),"search_peak_ratio":peak[group],
                    "visitor_peak_date":visitor_peak.observed_date.date(),
                    "search_to_visit_days":(visitor_peak.observed_date-peak.observed_date).days})
            fig,ax1=plt.subplots(figsize=(11,5.6)); ax2=ax1.twinx()
            for group in [c for c in x.columns if c in set(search.keyword_group)]:
                ax1.plot(x.observed_date,x[group],lw=1.8,label=f"검색:{group}")
            v=x.visitors_external; v_idx=v/v.loc[x.observed_date<pd.Timestamp(case["case_start"])].median()*100
            ax2.plot(x.observed_date,v_idx,color="#222",lw=2.2,alpha=.65,label="외지인 방문자(기준=100)")
            ax1.axvspan(pd.Timestamp(case["case_start"]),pd.Timestamp(case["case_end"]),color="#E8B04A",alpha=.12,label="사례 구간")
            ax1.set_title(f"{case['region_name']} 콘텐츠 검색어 파일럿",loc="left",fontweight="bold",fontsize=15)
            ax1.set_ylabel("네이버 상대 검색지수"); ax2.set_ylabel("외지인 방문자 지수")
            h1,l1=ax1.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
            ax1.legend(h1+h2,l1+l2,frameon=False,ncol=3,fontsize=9,loc="upper left")
            ax1.grid(alpha=.2); fig.tight_layout()
            name="yeongwol_keyword_pilot.png" if rid=="51750" else "geoje_keyword_pilot.png"
            fig.savefig(OUT/name,dpi=200,bbox_inches="tight"); plt.close(fig)
    finally: db.close()
    s=pd.DataFrame(summaries)
    s.to_csv(OUT/"pilot_peak_summary.csv",index=False,encoding="utf-8-sig")
    print(f"[완료] {OUT}")
    print(s.to_string(index=False))
    print("주의: 사후 선정 검색어 파일럿이므로 전체 모델의 예측 성능으로 해석하지 마세요.")


def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["create-tables","prepare","collect","analyze"])
    a=p.parse_args()
    {"create-tables":create_tables,"prepare":prepare,"collect":collect,"analyze":analyze}[a.command]()


if __name__=="__main__": main()
