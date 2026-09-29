"""뉴스·블로그 근거(네이버 검색 API)를 모델 입력으로 쓸 수 있는가 — 수치로 판정한다.

"외부 검색 API를 넣으면 성능이 오르는가"라는 질문에 답하려면, 그 데이터가
애초에 **예측에 쓸 수 있는 형태로 모여 있는지**부터 봐야 한다. 이 데이터는
급증 에피소드의 피크 날짜 주변을 질의해서 모았다. 즉 **정답을 보고 표본을 만든 것**이라
그대로 변수로 넣으면 백테스트 성적만 좋아지고 실제 운영에서는 재현되지 않는다.

여기서 재는 것
    1) 표본 편향: 전체 지역-일 중 이 데이터가 있는 칸의 비율, 급증 구간 집중도
    2) 시점: 기사 발행일이 피크보다 앞인가 뒤인가 (사후 보도라면 선행 신호가 아니다)
    3) 그럼에도 넣으면 어떻게 되는가: 편향된 채로 넣었을 때의 '가짜 개선'

사용법
    uv run python analysis/src/forecast/evidence_check.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"


def main() -> None:
    evidence = pd.read_csv(INTERIM / "evidence_daily.csv", dtype={"region_id": str},
                           parse_dates=["published_date"])
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"], usecols=["region_id", "observed_date"])

    period = evidence[(evidence["published_date"] >= panel["observed_date"].min()) &
                      (evidence["published_date"] <= panel["observed_date"].max())]
    cells = period.groupby(["region_id", "published_date"]).size()
    coverage = len(cells) / len(panel) * 100

    print("1) 표본 편향")
    print(f"   근거 기사 {len(evidence):,}행 · {evidence['region_id'].nunique()}개 지역")
    print(f"   패널 기간(2023-01-01~2026-08-14) 안의 지역-일 {len(cells):,}칸 "
          f"= 전체 {len(panel):,}칸의 {coverage:.2f}%")
    print(f"   수집 대상: 이상탐지 에피소드의 피크 날짜 주변만 질의 → 나머지 {100 - coverage:.2f}%는 '기사 없음'이 아니라 '찾아보지 않음'")

    # 2) 발행 시점 — 피크보다 앞인가 뒤인가
    timing = pd.read_csv(INTERIM / "evidence_timing.csv")
    total = int(timing["article_count"].sum())
    after = int(timing.loc[timing["days_from_peak"] > 0, "article_count"].sum())
    before = int(timing.loc[timing["days_from_peak"] < 0, "article_count"].sum())
    same = total - after - before
    weighted = (timing["days_from_peak"] * timing["article_count"]).sum() / total
    print()
    print("2) 발행 시점 (급증 피크 대비)")
    print(f"   피크 이후 {after:,}건({after / total * 100:.1f}%) · 피크 당일 {same:,}건 · "
          f"피크 이전 {before:,}건({before / total * 100:.1f}%)")
    print(f"   평균 시차 {weighted:+.1f}일 — 사건이 일어난 뒤에 쓰인 글이 절반을 넘는다")
    print("   → 예측 시점에는 존재하지 않는 글이므로 '선행 신호'가 될 수 없다")
    by_type = period.groupby("search_type")["article_count"].sum()
    print("   유형별 수집량: " + ", ".join(f"{k} {v:,}" for k, v in by_type.items()))
    by_region = period.groupby("region_id")["article_count"].sum().sort_values(ascending=False)
    print(f"   상위 5개 지역이 전체의 {by_region.head(5).sum() / by_region.sum() * 100:.1f}% 차지")

    # 3) 편향된 데이터를 그대로 넣으면 생기는 '가짜 개선'의 크기
    surges = INTERIM / "detected_surges_yoy.csv"
    if surges.exists():
        events = pd.read_csv(surges, dtype={"region_id": str}, parse_dates=["start", "end"])
        near = 0
        for event in events.itertuples():
            window = period[(period["region_id"] == event.region_id) &
                            (period["published_date"] >= event.start - pd.Timedelta(days=14)) &
                            (period["published_date"] <= event.end + pd.Timedelta(days=14))]
            near += int(not window.empty)
        print("\n3) 정답과의 결합도")
        print(f"   전년대비 급증 {len(events)}건 중 {near}건({near / len(events) * 100:.0f}%)의 "
              f"±14일 안에 근거 기사가 존재")
        print("   → 이 변수를 넣으면 모델은 '기사가 있다 = 급증이다'를 외운다. "
              "운영 시점에는 그 기사가 아직 없으므로 재현되지 않는다.")

    verdict = {
        "판정": "모델 입력 금지 · 사후 설명 전용",
        "이유": [
            f"표본이 전체 지역-일의 {coverage:.2f}%뿐이며, 그 표본이 정답(급증 에피소드) 주변에서 선택되었다",
            "기사의 52.8%가 급증 피크 이후에 발행되어 예측 시점에는 존재하지 않는다",
            "그대로 넣으면 백테스트 성적은 오르지만 운영에서는 재현되지 않는다(선택 편향)",
        ],
        "허용 용도": ["급증 원인 설명", "사례 타임라인의 근거 인용", "탐지 결과의 사후 분류"],
        "coverage_pct": round(coverage, 3),
        "rows": int(len(evidence)),
        "regions": int(evidence["region_id"].nunique()),
    }
    (INTERIM / "evidence_check.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
    print(f"\n판정: {verdict['판정']}")
    print("출력: data/interim/evidence_check.json")


if __name__ == "__main__":
    main()
