from __future__ import annotations
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "final_report_output"

GROUP_KO = {
    "calendar_related": "달력 효과",
    "festival_exact_overlap": "축제 기간 중첩",
    "unexplained_candidate": "미설명 후보",
    "weather_context": "날씨 맥락",
    "festival_pre_signal": "축제 사전 신호",
    "possible_external": "외부 근거 가능",
    "external_evidence": "외부 근거 확인",
    "festival_nearby": "축제 인접 기간",
}
LABEL_KO = {
    "true_signal": "실제 신호",
    "false_alarm": "오경보",
    "uncertain": "판단 보류",
    "calendar_effect": "달력 효과",
    "weather_or_disruption": "날씨·재난",
}

def connect():
    load_dotenv(ROOT / ".env")
    pw = os.getenv("MYSQL_PASSWORD", "")
    if not pw or pw == "CHANGE_ME":
        raise SystemExit(".env의 MYSQL_PASSWORD를 실제 비밀번호로 변경하세요.")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "yaho_loader"),
        password=pw,
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
    )

def set_font():
    candidates = ["Malgun Gothic", "맑은 고딕", "AppleGothic", "NanumGothic", "DejaVu Sans"]
    available = {x.name for x in font_manager.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 200

def query(conn, sql, params=None):
    return pd.read_sql(sql, conn, params=params)

def save_bar(df, label_col, value_col, title, filename, color="#24557F", horizontal=False):
    fig, ax = plt.subplots(figsize=(9, 5.2))
    if horizontal:
        data = df.sort_values(value_col)
        ax.barh(data[label_col], data[value_col], color=color)
        for i, v in enumerate(data[value_col]): ax.text(v + max(data[value_col])*0.01, i, f"{int(v):,}", va="center")
        ax.set_xlabel("건수")
    else:
        ax.bar(df[label_col], df[value_col], color=color)
        for i, v in enumerate(df[value_col]): ax.text(i, v + max(df[value_col])*0.02, f"{int(v):,}", ha="center")
        ax.set_ylabel("건수")
        ax.tick_params(axis="x", rotation=25)
    ax.set_title(title, loc="left", fontweight="bold", fontsize=15)
    ax.spines[["top","right"]].set_visible(False)
    ax.grid(axis="x" if horizontal else "y", alpha=.2)
    fig.tight_layout(); fig.savefig(OUT / filename, bbox_inches="tight"); plt.close(fig)

def main():
    OUT.mkdir(exist_ok=True)
    set_font()
    conn = connect()
    try:
        groups = query(conn, """
            SELECT final_explanation_group, COUNT(*) AS episodes,
                   COUNT(DISTINCT region_id) AS regions
            FROM vw_final_anomaly_analysis
            GROUP BY final_explanation_group ORDER BY episodes DESC
        """)
        groups["분류"] = groups["final_explanation_group"].map(GROUP_KO).fillna(groups["final_explanation_group"])
        groups.to_csv(OUT / "explanation_group_summary.csv", index=False, encoding="utf-8-sig")
        save_bar(groups, "분류", "episodes", "이상 에피소드 설명 유형", "01_explanation_groups.png", horizontal=True)

        pre = query(conn, """
            SELECT region_id, region_name, episode_no, search_peak_date, visitor_peak_date,
                   representative_festival_name, festival_start,
                   search_to_festival_lead_days, visitor_to_festival_lead_days,
                   peak_anomaly_score
            FROM vw_final_anomaly_analysis
            WHERE final_explanation_group='festival_pre_signal'
            ORDER BY peak_anomaly_score DESC
        """)
        pre.to_csv(OUT / "festival_pre_signal_detail.csv", index=False, encoding="utf-8-sig")
        s = pre.loc[pre.search_to_festival_lead_days > 0, "search_to_festival_lead_days"]
        v = pre.loc[pre.visitor_to_festival_lead_days > 0, "visitor_to_festival_lead_days"]

        lead_summary = pd.DataFrame([
            {"지표":"검색 신호", "선행 사례":len(s), "평균 선행일":round(s.mean(),2), "중앙 선행일":round(s.median(),2),
             "3일 이상":int((s>=3).sum()), "7일 이상":int((s>=7).sum())},
            {"지표":"방문 신호", "선행 사례":len(v), "평균 선행일":round(v.mean(),2), "중앙 선행일":round(v.median(),2),
             "3일 이상":int((v>=3).sum()), "7일 이상":int((v>=7).sum())},
        ])
        lead_summary.to_csv(OUT / "leadtime_summary.csv", index=False, encoding="utf-8-sig")
        fig, ax = plt.subplots(figsize=(8.4, 5.0))
        x=np.arange(2); width=.34
        ax.bar(x-width/2, lead_summary["평균 선행일"], width, label="평균", color="#24557F")
        ax.bar(x+width/2, lead_summary["중앙 선행일"], width, label="중앙값", color="#78A6C8")
        for container in ax.containers: ax.bar_label(container, fmt="%.1f일", padding=3)
        ax.set_xticks(x, lead_summary["지표"]); ax.set_ylabel("축제 시작 대비 선행일")
        ax.set_title("검색 신호가 방문 신호보다 먼저 나타남", loc="left", fontweight="bold", fontsize=15)
        ax.legend(frameon=False); ax.spines[["top","right"]].set_visible(False); ax.grid(axis="y",alpha=.2)
        fig.tight_layout(); fig.savefig(OUT/"02_leadtime_comparison.png",bbox_inches="tight"); plt.close(fig)

        top = pre.loc[pre.search_to_festival_lead_days > 0].nlargest(10, "search_to_festival_lead_days").copy()
        top["사례"] = top["region_name"] + " · " + top["representative_festival_name"].fillna("")
        save_bar(top, "사례", "search_to_festival_lead_days", "검색 피크가 먼저 나타난 축제 사례", "03_top_festival_leads.png", horizontal=True)

        review = query(conn, """
            SELECT human_label, COUNT(*) AS episodes
            FROM anomaly_human_review GROUP BY human_label ORDER BY episodes DESC
        """)
        review["검토 결과"] = review["human_label"].map(LABEL_KO).fillna(review["human_label"])
        review.to_csv(OUT/"human_review_summary.csv", index=False, encoding="utf-8-sig")
        save_bar(review, "검토 결과", "episodes", "미설명 상위 20건 인간 검토 결과", "04_human_review.png")

        episodes = query(conn, """
            SELECT * FROM (
              SELECT region_id,region_name,episode_no,episode_start,episode_end,
                     search_peak_date,visitor_peak_date,peak_anomaly_score,
                     final_explanation_group,representative_festival_name,
                     ROW_NUMBER() OVER(PARTITION BY region_name ORDER BY peak_anomaly_score DESC) rn
              FROM vw_final_anomaly_analysis
              WHERE region_name IN ('영월군','거제시')
            ) x WHERE rn=1 ORDER BY region_name
        """)
        episodes.to_csv(OUT/"yeongwol_geoje_selected_cases.csv", index=False, encoding="utf-8-sig")
        if not episodes.empty:
            fig, axes = plt.subplots(len(episodes), 1, figsize=(10, 4.2*len(episodes)), squeeze=False)
            for ax, (_,e) in zip(axes[:,0], episodes.iterrows()):
                daily = query(conn, """
                    SELECT observed_date,naver_interest,visitors_external
                    FROM vw_daily_core_signal
                    WHERE region_id=%s
                      AND observed_date BETWEEN DATE_SUB(%s,INTERVAL 30 DAY) AND DATE_ADD(%s,INTERVAL 30 DAY)
                    ORDER BY observed_date
                """, (e.region_id,e.visitor_peak_date,e.visitor_peak_date))
                if daily.empty: continue
                daily["observed_date"]=pd.to_datetime(daily["observed_date"])
                for col in ["naver_interest","visitors_external"]:
                    base=daily[col].median()
                    daily[col+"_idx"]=daily[col]/base*100 if base and not pd.isna(base) else np.nan
                ax.plot(daily.observed_date,daily.naver_interest_idx,label="네이버 검색지수",lw=2,color="#24557F")
                ax.plot(daily.observed_date,daily.visitors_external_idx,label="외지인 방문자",lw=2,color="#D27A3C")
                ax.axvline(pd.to_datetime(e.visitor_peak_date),ls="--",color="#444",alpha=.7,label="방문 피크")
                ax.set_title(f"{e.region_name} 대표 에피소드  {e.episode_start}~{e.episode_end}",loc="left",fontweight="bold")
                ax.set_ylabel("기간 중앙값=100"); ax.grid(alpha=.2); ax.spines[["top","right"]].set_visible(False); ax.legend(frameon=False,ncol=3)
            fig.tight_layout(); fig.savefig(OUT/"05_yeongwol_geoje_timeline.png",bbox_inches="tight"); plt.close(fig)

        total=int(groups.episodes.sum())
        festival=int(groups.loc[groups.final_explanation_group.str.startswith('festival_'),'episodes'].sum())
        true_n=int(review.loc[review.human_label=='true_signal','episodes'].sum())
        false_n=int(review.loc[review.human_label=='false_alarm','episodes'].sum())
        uncertain_n=int(review.loc[review.human_label=='uncertain','episodes'].sum())
        denom=true_n+false_n
        precision=true_n/denom*100 if denom else np.nan
        text=f"""# 관광 바이럴 조기경보 최종 분석 초안

## 핵심 결과

- 전국 146개 지역에서 {total:,}개 이상 에피소드를 탐지했다.
- 축제 기간 또는 인접 기간과 연결된 에피소드는 {festival:,}건이다.
- 축제 사전 신호 유형은 {len(pre):,}건이며, 검색 피크가 실제로 선행한 사례는 {len(s):,}건이다.
- 검색 신호는 축제 시작보다 평균 {s.mean():.2f}일, 중앙값 {s.median():.0f}일 먼저 나타났다.
- 방문 신호는 축제 시작보다 평균 {v.mean():.2f}일, 중앙값 {v.median():.1f}일 먼저 나타났다.
- 미설명 상위 20건의 인간 검토 결과 실제 신호 {true_n}건, 오경보 {false_n}건, 판단 보류 {uncertain_n}건이었다.
- 판단이 완료된 {denom}건에 한정한 조건부 적중률은 {precision:.2f}%이다.

## 해석

검색 관심은 실제 방문보다 앞서 상승하여 관광 수요의 선행지표로 활용될 가능성을 보였다. 다만 축제와 날짜가 일치한다는 사실만으로 인과관계가 확정되는 것은 아니다. 인간 검토 적중률은 전체 450건이 아니라 자동 설명이 어려운 상위 20건 표본의 결과다.

## 보고 시 주의

- 알려진 요인 연결 비율을 모델 정확도라고 표현하지 않는다.
- 정답 사건의 전국 모집단이 없으므로 재현율과 F1은 계산하지 않는다.
- 월별 SNS 지표는 일별 바이럴 발생일의 직접 근거로 사용하지 않는다.
- 영월과 거제 사례는 기사 공식자료와 관광지 단위 수치를 함께 확인한 뒤 최종 발표 사례로 확정한다.
"""
        (OUT/"final_analysis_draft.md").write_text(text,encoding="utf-8-sig")
        print(f"[완료] {OUT}")
        for p in sorted(OUT.iterdir()): print(f"  {p.name}")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
