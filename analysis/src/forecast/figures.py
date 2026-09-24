"""서식4·발표에 넣을 그림 4장.

담는 것은 전면 검토(analysis/src/forecast/review_checks.py)를 통과한 사실만이다.
철회한 주장(검색 필터링으로 경보 품질 개선)은 그리지 않는다.

    figure1_예측사다리.png    변수를 더할 때 오차가 어떻게 변했는가
    figure2_영월타임라인.png   개봉 → 검색 → 방문 → 행정 대응의 시간축
    figure3_지점vs시군구.png   같은 사건이 지점과 시군구에서 얼마나 다르게 보이는가
    figure4_급증의성격.png     시군구 방문 급증은 무엇이 만드는가
    figure5_추가데이터기여도.png  어떤 추가 데이터가 실제로 예측을 개선했는가 (09.24)
    figure6_명절정렬재검.png    전년대비 급증 43건이 설 날짜 이동이었음 (09.24)
    figure7_총량감시_사각지대.png 지점 급증의 98%는 시군구 총량에서 보이지 않는다 (09.24)

사용법:
    uv run python analysis/src/forecast/figures.py
"""

import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"
OUT_DIR = ROOT / "docs" / "submission" / "figures"

INK = "#1f2933"
MUTED = "#7b8794"
ACCENT = "#0b6fa4"
WARM = "#c2410c"
GRID = "#e4e7eb"


def set_korean_font() -> str:
    """윈도우에 있는 한글 글꼴을 쓴다. 없으면 이름만 바꿔 계속 진행한다."""
    for name in ("Malgun Gothic", "NanumGothic", "AppleGothic"):
        try:
            matplotlib.font_manager.findfont(name, fallback_to_default=False)
        except Exception:
            continue
        plt.rcParams["font.family"] = name
        plt.rcParams["axes.unicode_minus"] = False
        return name
    return "기본값(한글 깨질 수 있음)"


def style(ax, title: str, subtitle: str = "") -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK, loc="left", pad=22 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9.5, color=MUTED, va="bottom")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def figure_ladder() -> None:
    summary = json.loads((INTERIM / "baseline_h7.json").read_text(encoding="utf-8"))
    results = summary["results"]
    labels = ["작년 같은 요일\n(기준선)", "+ 달력", "+ 축제", "+ 검색", "+ 날씨 실측\n(상한)"]
    keys = ["B1_작년같은요일", "B3_달력", "M1_축제추가", "M2_검색추가", "M3_날씨포함_상한"]
    values = [results[k]["smape"] for k in keys]
    colors = [MUTED, ACCENT, ACCENT, WARM, "#9aa5b1"]

    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.12, f"{value:.2f}%",
                ha="center", fontsize=10, color=INK, fontweight="bold")
    gain = (values[0] - values[1]) / values[0] * 100
    ax.annotate("", xy=(0.72, values[1] + 0.05), xytext=(0.28, values[0] - 0.05),
                arrowprops={"arrowstyle": "->", "color": ACCENT, "linewidth": 1.4})
    ax.text(0.5, (values[0] + values[1]) / 2 + 0.45, f"달력만으로\n오차 {gain:.0f}% 감소",
            ha="center", fontsize=10, color=ACCENT, fontweight="bold")
    ax.text(3, values[3] + 1.05, "검색을 더해도\n변화 없음", ha="center", fontsize=9.5, color=WARM)
    ax.set_ylim(0, max(values) * 1.25)
    ax.set_ylabel("예측 오차 sMAPE (%, 낮을수록 좋음)", fontsize=10, color=MUTED)
    style(ax, "무엇이 방문자 예측을 개선하는가",
          "7일 앞 외지인 방문자 예측 · 228개 시군구 · 2026-01-01~08-14 검증")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure1_예측사다리.png", dpi=200)
    plt.close(fig)


def figure_yeongwol_timeline() -> None:
    """요일 변동이 커서 7일 이동평균으로 추세를 보여 준다. 이벤트는 가로 라벨로 층을 나눠 겹치지 않게."""
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    frame = panel[(panel["region_id"] == "51750") &
                  (panel["observed_date"] >= "2025-12-20") &
                  (panel["observed_date"] <= "2026-05-10")].copy()
    frame["search_ma"] = frame["naver_interest"].rolling(7, min_periods=4).mean()
    frame["visit_ma"] = frame["visitors_external"].rolling(7, min_periods=4).mean() / 1000
    frame = frame[frame["observed_date"] >= "2026-01-01"]

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    ax.axvspan(pd.Timestamp("2026-02-15"), pd.Timestamp("2026-03-06"), color="#f0f7fb", zorder=0)
    ax.plot(frame["observed_date"], frame["search_ma"], color=ACCENT, linewidth=2.4)
    ax.set_ylabel("네이버 검색지수 (7일 평균)", color=ACCENT, fontsize=10)
    ax.tick_params(axis="y", colors=ACCENT)
    ax.set_ylim(0, frame["search_ma"].max() * 1.45)

    twin = ax.twinx()
    twin.plot(frame["observed_date"], frame["visit_ma"], color=WARM, linewidth=2.0)
    twin.set_ylabel("외지인 방문자 (천 명, 7일 평균)", color=WARM, fontsize=10)
    twin.tick_params(axis="y", colors=WARM)
    twin.spines[["top"]].set_visible(False)
    twin.set_ylim(0, frame["visit_ma"].max() * 1.45)

    top = ax.get_ylim()[1]
    events = [("2026-02-04", "영화 개봉", 0.97), ("2026-02-15", "검색 신호", 0.88),
              ("2026-03-06", "강원도 안전점검", 0.97), ("2026-04-16", "영월군 수용 대책", 0.88)]
    for date, label, height in events:
        when = pd.Timestamp(date)
        ax.axvline(when, color=MUTED, linestyle="--", linewidth=1, zorder=1)
        ax.annotate(label, xy=(when, top * height), fontsize=9, color=INK, ha="center",
                    bbox={"facecolor": "white", "edgecolor": GRID, "boxstyle": "round,pad=0.25"})
    ax.text(pd.Timestamp("2026-02-19"), top * 0.62, "19일", fontsize=11, color=ACCENT, fontweight="bold")
    ax.annotate("", xy=(pd.Timestamp("2026-03-06"), top * 0.58), xytext=(pd.Timestamp("2026-02-15"), top * 0.58),
                arrowprops={"arrowstyle": "<->", "color": ACCENT, "linewidth": 1.3})
    ax.text(pd.Timestamp("2026-01-03"), top * 0.30, "파랑: 검색지수\n주황: 외지인 방문자",
            fontsize=9, color=MUTED)

    style(ax, "영월 — 영화 개봉이 만든 검색과 방문",
          "검색 신호(2/15)가 첫 행정 조치(3/6)보다 19일 앞섰다 · 요일 변동을 없애려 7일 이동평균 사용")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure2_영월타임라인.png", dpi=200)
    plt.close(fig)


def figure_point_vs_region() -> None:
    """지점 입장객과 시군구 총량이 같은 사건을 얼마나 다르게 보여주는가."""
    attractions = {"청령포": {"2026-02": 38223 / 4763, "2026-03": 84251 / 7106},
                   "단종장릉": {"2026-02": 26578 / 2917, "2026-03": 55387 / 4109}}
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    frame = panel[panel["region_id"] == "51750"].set_index("observed_date")["visitors_external"]
    region_ratio = {}
    for month in ("2026-02", "2026-03"):
        now = frame[month].sum()
        before = frame[f"2025-{month[-2:]}"].sum()
        region_ratio[month] = now / before

    months = ["2026-02", "2026-03"]
    series = [("청령포 입장객", [attractions["청령포"][m] for m in months], ACCENT),
              ("단종장릉 입장객", [attractions["단종장릉"][m] for m in months], "#3d9dc7"),
              ("영월 시군구 전체\n외지인 방문자", [region_ratio[m] for m in months], MUTED)]

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    width = 0.26
    positions = range(len(months))
    for index, (label, values, color) in enumerate(series):
        offsets = [p + (index - 1) * width for p in positions]
        bars = ax.bar(offsets, values, width=width, color=color, label=label)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.25, f"{value:.1f}배",
                    ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax.axhline(1, color=GRID, linewidth=1)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(["2026년 2월", "2026년 3월"])
    ax.set_ylabel("전년 같은 달 대비 배수", fontsize=10, color=MUTED)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_ylim(0, 15)
    style(ax, "같은 사건이 지점에서는 12배, 시군구에서는 1배대",
          "출처: 관광지식정보시스템 입장객(지점) · 이동통신 방문자수(시군구)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure3_지점vs시군구.png", dpi=200)
    plt.close(fig)


def figure_surge_composition() -> None:
    """겹치지 않는 네 칸으로 나눈다. 공휴일·축제 둘 다인 사건을 양쪽에 세면 합계가 사건 수를 넘는다."""
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str}, parse_dates=["observed_date"])
    surges = pd.read_csv(INTERIM / "detected_surges_yoy.csv", dtype={"region_id": str},
                         parse_dates=["start", "end"])
    lookup = panel.set_index(["region_id", "observed_date"])[["is_public_holiday", "festival_active"]]

    buckets = {"공휴일만": 0, "공휴일 + 축제": 0, "축제만": 0, "둘 다 아님": 0}
    for surge in surges.itertuples():
        window = lookup.loc[(surge.region_id, slice(surge.start, surge.end)), :]
        holiday = bool(window["is_public_holiday"].max() > 0)
        festival = bool(window["festival_active"].max() > 0)
        key = ("공휴일 + 축제" if holiday and festival else
               "공휴일만" if holiday else "축제만" if festival else "둘 다 아님")
        buckets[key] += 1

    labels = list(buckets)
    values = [buckets[k] for k in labels]
    colors = [ACCENT, "#3d9dc7", "#7fc2dd", WARM]

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    bars = ax.barh(labels, values, color=colors, height=0.55)
    for bar, value in zip(bars, values):
        share = value / sum(values) * 100
        ax.text(value + 0.6, bar.get_y() + bar.get_height() / 2, f"{value}건 ({share:.0f}%)",
                va="center", fontsize=10, color=INK, fontweight="bold")
    ax.set_xlim(0, max(values) * 1.3)
    ax.invert_yaxis()
    ax.set_xlabel("사건 수", fontsize=10, color=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    style(ax, "시군구 방문 급증은 대부분 달력이 만든다",
          f"전년 대비 급증 {sum(values)}건 · 2026-01-01~08-14 · 228개 시군구")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure4_급증의성격.png", dpi=200)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font = set_korean_font()
    figure_ladder()
    figure_yeongwol_timeline()
    figure_point_vs_region()
    figure_surge_composition()
    figure_block_contribution()
    figure_holiday_alignment()
    figure_blind_spot()
    print(f"글꼴: {font}")
    for path in sorted(OUT_DIR.glob("*.png")):
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size // 1024}KB")




def figure_block_contribution() -> None:
    """어떤 데이터가 실제로 예측을 개선했는가 — 95% 구간까지 함께 그린다.

    막대만 그리면 '조금 좋아졌다'가 전부 개선처럼 보인다. 구간이 0을 걸치면
    차이가 없다는 뜻이므로, 0선을 넘는 막대와 넘지 않는 막대를 색으로 구분한다.
    """
    summary = json.loads((INTERIM / "ablation_h7.json").read_text(encoding="utf-8"))
    wanted = ["달력 추가", "축제 추가", "네이버 검색 추가", "데이터랩 월간 추가",
              "과거 날씨 추가", "진짜 데이터랩 - 위약 (순수 신호분)", "당일 실측 날씨(상한·운영불가)"]
    rows = [c for name in wanted for c in summary["comparisons"] if c["비교"] == name]

    labels = [r["비교"].replace(" 추가", "").replace("(상한·운영불가)", "\n(상한·운영불가)")
              .replace(" (순수 신호분)", "\n(순수 신호분)") for r in rows]
    values = [r["sMAPE_차이"] for r in rows]
    lows = [r["지역평균차이_95CI"][0] for r in rows]
    highs = [r["지역평균차이_95CI"][1] for r in rows]

    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    positions = range(len(rows))
    for position, row, value, low, high in zip(positions, rows, values, lows, highs):
        meaningful = high < 0 and abs(value) >= row["씨앗잡음"]
        color = ACCENT if meaningful else MUTED
        ax.barh(position, value, color=color, height=0.55)
        ax.plot([low, high], [position, position], color=INK, linewidth=1.4)
        note = f"{value:+.3f}%p" + ("" if meaningful else "  (차이 없음/잡음 수준)")
        ax.text(min(low, value) - 0.04, position, note, ha="right", va="center",
                fontsize=9, color=INK if meaningful else MUTED)
    ax.axvline(0, color=INK, linewidth=1)
    ax.set_yticks(list(positions))
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("sMAPE 변화 (음수일수록 오차가 줄어든 것)", fontsize=9.5, color=MUTED)
    ax.set_xlim(min(lows) - 0.55, max(max(highs), 0) + 0.15)
    style(ax, "추가 데이터는 예측을 개선하는가",
          "7일 앞 예측 · 228개 시군구 · 테스트 2026-01-01~08-14 · 가로선은 지역 붓스트랩 95% 구간")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure5_추가데이터기여도.png", dpi=200)
    plt.close(fig)


def figure_holiday_alignment() -> None:
    """전년대비 급증이 '설 날짜 이동'이었음을 한 장으로 보인다."""
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    panel["year"] = panel["observed_date"].dt.year
    seollal = panel[panel["holiday_name"].fillna("").str.contains("설날")]
    average = seollal.groupby(["region_id", "year"])["visitors_external"].mean().unstack()
    ratios = (average[2026] / average[2025]).dropna()

    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    ax.hist(ratios, bins=28, color=ACCENT, alpha=0.85)
    ax.axvline(1.0, color=MUTED, linewidth=1.2, linestyle="--")
    ax.text(0.995, ax.get_ylim()[1] * 0.62, "작년 설과 같음 ", color=MUTED, fontsize=9,
            va="center", ha="right")
    ax.axvline(1.82, color=WARM, linewidth=1.8)
    ax.text(1.82, ax.get_ylim()[1] * 0.96, " 우리가 쓴 급증 임계 1.82배\n 넘는 지역 0곳",
            color=WARM, fontsize=9.5, va="top", fontweight="bold")
    ax.set_xlim(0.8, 2.0)
    ax.set_xlabel("2026년 설 연휴 ÷ 2025년 설 연휴 (지역별 일평균 외지인)", fontsize=9.5, color=MUTED)
    ax.set_ylabel("지역 수", fontsize=9.5, color=MUTED)
    style(ax, "'전년대비 급증 43건'은 설 날짜가 옮겨간 결과였다",
          f"228개 시군구 · 중앙값 {ratios.median():.2f}배 · 최대 {ratios.max():.2f}배 "
          "· 명절을 맞춰 비교하면 급증이라 부를 지역이 없다")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure6_명절정렬재검.png", dpi=200)
    plt.close(fig)


def figure_blind_spot() -> None:
    """총량 감시의 사각지대를 한 장으로 — 가로 시군구 배율, 세로 지점 배율.

    오른쪽 위(둘 다 큼)에 점이 몰려야 "총량으로도 보인다"가 되는데, 실제로는
    왼쪽 위(지점만 큼)에 몰린다. 그 사분면이 곧 우리가 말하는 사각지대다.
    """
    path = INTERIM / "point_level_ratios.csv"
    if not path.exists():
        print("  figure7 건너뜀 — point_level.py를 먼저 실행하세요")
        return
    frame = pd.read_csv(path, dtype={"region_id": str})
    summary = json.loads((INTERIM / "point_level.json").read_text(encoding="utf-8"))
    surge, flat = summary["지점_급증임계"], summary["시군구_평탄상한"]

    blind = frame[(frame["point_ratio"] >= surge) & (frame["region_ratio"] < flat)]
    rest = frame.drop(blind.index)

    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.scatter(rest["region_ratio"], rest["point_ratio"], s=9, color=MUTED, alpha=0.35,
               linewidths=0, label="나머지 지점-월")
    ax.scatter(blind["region_ratio"], blind["point_ratio"], s=26, color=WARM, alpha=0.85,
               linewidths=0, label="사각지대 (지점만 급증)")
    ax.axhline(surge, color=INK, linewidth=1, linestyle="--")
    ax.axvline(flat, color=INK, linewidth=1, linestyle="--")
    ax.text(flat + 0.01, surge * 1.03, f" 시군구 {flat}배 · 지점 {surge}배 기준선",
            fontsize=8.5, color=INK, va="bottom")
    caption = f"사각지대 {len(blind)}건\n({blind['region_id'].nunique()}개 시군구)"
    ax.text(0.63, 18, caption, fontsize=11, color=WARM, fontweight="bold", va="top")

    for name, offset in (("청령포", (-78, 14)), ("단종장릉", (-88, -22))):
        hit = frame[frame["attraction_name"].str.contains(name, na=False)]
        if hit.empty:
            continue
        row = hit.loc[hit["point_ratio"].idxmax()]
        ax.scatter([row["region_ratio"]], [row["point_ratio"]], s=40, color=ACCENT, zorder=5)
        ax.annotate(f"{name} {row['point_ratio']:.1f}배 (영월)",
                    (row["region_ratio"], row["point_ratio"]),
                    textcoords="offset points", xytext=offset, fontsize=9.5, color=ACCENT,
                    arrowprops=dict(arrowstyle="-", color=ACCENT, linewidth=0.8))

    ax.set_yscale("log")
    ax.set_ylim(0.25, 22)
    ax.set_yticks([0.5, 1, 2, 5, 10, 20])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.get_yaxis().set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.tick_params(axis="y", which="minor", length=0)
    ax.set_xlim(0.6, 1.45)
    ax.set_xlabel("시군구 총 방문자 전년 같은 달 대비 배율", fontsize=9.5, color=MUTED)
    ax.set_ylabel("지점 입장객 전년 같은 달 대비 배율 (로그)", fontsize=9.5, color=MUTED)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    style(ax, "시군구 총량은 지점의 쏠림을 놓친다",
          f"2026년 3~6월 · {summary['지점수']:,}개 관광지점 × {summary['시군구수']}개 시군구 "
          f"· 지점 급증 {summary['지점급증_건수']}건 중 {summary['사각지대_건수']}건은 시군구에서 보이지 않는다")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "figure7_총량감시_사각지대.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
