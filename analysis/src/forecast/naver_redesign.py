"""검색 변수가 왜 예측을 나쁘게 했는가 — 설계 오류를 찾아 고쳐서 다시 잰다.

문제 제기
    09.24 기여도 실험에서 네이버 검색을 넣으면 오차가 +0.026%p 늘고
    **228개 지역 중 101곳만 좋아지고 127곳이 나빠졌다**(승률 44.3%).
    정보가 없는 변수라면 승률이 50% 근처에서 맴돌아야지, 절반 아래로 내려가지 않는다.
    변수를 만드는 방식에 문제가 있다는 신호다.

진단에서 확인한 것
    1) 검색지수는 해마다 내려간다 — 전국 평균 2023년 64.6 → 2026년 47.8
       228개 지역 중 217곳이 같은 방향으로 줄었고 중앙값 0.73배다.
       같은 기간 방문자는 오히려 1.05배로 늘었다. 관광 수요가 준 것이 아니라
       **검색지수라는 자료 자체가 계속 내려가는 것**이다.
    2) 지역별 수준 차이가 100배가 넘는다 (평균 2.2 ~ 244.5).

    그런데 기존 변수에는 `naver_last`·`naver_mean7`·`naver_mean28` 같은
    **절대 수준**이 그대로 들어가 있었다. 전국 공통 모델에서 절대 수준을 쓰면
      - 지역마다 같은 값이 다른 뜻을 갖고 (수준이 사실상 지역 이름표가 된다)
      - 학습 구간(2023~24)에서 배운 기준선이 시험 구간(2026)에서는 27% 어긋난다.
    두 가지 모두 예측을 **적극적으로 틀리게** 만든다. 승률이 절반 아래로 내려간 이유다.

고친 방식 — 수준을 지우고 '그 지역의 평소 대비'만 남긴다
    NAV_구버전 : 절대 수준 3개 + 비율 3개 (기존)
    NAV_개선   : 전부 비율. 그 지역 직전 1년 평균 대비, 28일 평균 대비,
                 그리고 전년 대비는 **전국 공통 하락분을 나눠서 제거**한다.

    변수 개수를 6개로 맞춰 '변수를 더 넣은 효과'가 섞이지 않게 했다.

사용법
    uv run python analysis/src/forecast/naver_redesign.py
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

from ablation import fit_predict, paired_bootstrap, region_smape  # noqa: E402
from baseline import (NAVER_DELAY, SPLITS, TARGET, build_features,  # noqa: E402
                      lagged, rolling_mean, smape)

HORIZON = 7
SEEDS = 3


def drift_report(panel: pd.DataFrame) -> dict:
    """검색지수가 관광과 무관하게 내려가는지 먼저 수치로 남긴다."""
    frame = panel[panel["observed_date"].dt.month <= 8].copy()   # 2026년은 8월까지뿐
    frame["year"] = frame["observed_date"].dt.year
    search = frame.groupby(["region_id", "year"])["naver_interest"].mean().unstack()
    visits = frame.groupby(["region_id", "year"])[TARGET].mean().unstack()
    search_ratio = (search[2026] / search[2023]).dropna()
    visit_ratio = (visits[2026] / visits[2023]).dropna()
    national = frame.groupby("year")["naver_interest"].mean()
    return {
        "전국평균_연도별": {int(k): round(float(v), 2) for k, v in national.items()},
        "검색_2026대비2023_중앙값": round(float(search_ratio.median()), 3),
        "검색이_줄어든_지역수": int((search_ratio < 1).sum()),
        "지역수": int(len(search_ratio)),
        "방문자_2026대비2023_중앙값": round(float(visit_ratio.median()), 3),
        "지역별_검색수준_최소": round(float(panel.groupby("region_id")["naver_interest"].mean().min()), 2),
        "지역별_검색수준_최대": round(float(panel.groupby("region_id")["naver_interest"].mean().max()), 2),
    }


def redesigned_features(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """절대 수준을 빼고 '그 지역의 평소 대비'만 남긴 검색 변수.

    핵심 두 가지
      - 모든 변수를 **그 지역 자신의 최근 1년 평균**으로 나눈다 → 지역 간 수준 차이 제거
      - 전년 대비는 **같은 날 전국 중앙값으로 한 번 더 나눈다** → 전국 공통 하락분 제거
        (전국이 다 같이 27% 줄었다면 그건 그 지역의 신호가 아니다)
    """
    frame = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True).copy()
    cut = horizon + NAVER_DELAY

    last = lagged(frame, "naver_interest", cut)
    mean7 = rolling_mean(frame, "naver_interest", cut, 7)
    mean28 = rolling_mean(frame, "naver_interest", cut, 28)
    mean365 = rolling_mean(frame, "naver_interest", cut, 365)
    mean7_year_ago = rolling_mean(frame, "naver_interest", cut + 364, 7)

    base = mean365.replace(0, np.nan)
    out = pd.DataFrame(index=frame.index)
    out["nv_last_rel"] = last / base          # 어제가 평소의 몇 배인가
    out["nv_mean7_rel"] = mean7 / base        # 최근 한 주가 평소의 몇 배인가
    out["nv_mean28_rel"] = mean28 / base      # 최근 한 달이 평소의 몇 배인가
    out["nv_short_vs_month"] = mean7 / mean28.replace(0, np.nan)   # 달아오르는 중인가
    out["nv_jump"] = last / mean28.replace(0, np.nan)              # 하루짜리 튐

    # 전년 대비 — 전국이 다 같이 줄어든 만큼은 빼고 본다
    raw_yoy = mean7 / mean7_year_ago.replace(0, np.nan)
    national = raw_yoy.groupby(frame["observed_date"]).transform("median")
    out["nv_yoy_detrended"] = raw_yoy / national.replace(0, np.nan)
    return out


def evaluate(fit_frame, test, blocks, label_base, label_other, note):
    base_r = region_smape(test, label_base)
    other_r = region_smape(test, label_other)
    low, high = paired_bootstrap(base_r, other_r)
    wins = int((other_r < base_r).sum())
    total = len(base_r)
    gap = smape(test[TARGET].to_numpy(), test[label_other].to_numpy()) - \
        smape(test[TARGET].to_numpy(), test[label_base].to_numpy())
    verdict = "개선" if high < 0 else ("악화" if low > 0 else "차이 없음")
    return {"비교": note, "sMAPE_차이": round(gap, 3),
            "95CI": [round(low, 3), round(high, 3)],
            "좋아진_지역": wins, "나빠진_지역": total - wins,
            "지역승률_pct": round(100 * wins / total, 1), "판정": verdict}


def main() -> None:
    panel = pd.read_csv(INTERIM / "panel_daily.csv", dtype={"region_id": str},
                        parse_dates=["observed_date"])
    panel = panel.sort_values(["region_id", "observed_date"]).reset_index(drop=True)

    report = drift_report(panel)
    print("1) 진단 — 검색지수는 관광과 무관하게 내려간다")
    print("   전국 평균 검색지수(1~8월): " +
          " → ".join(f"{year} {value}" for year, value in report["전국평균_연도별"].items()))
    print(f"   2026 ÷ 2023: 검색 {report['검색_2026대비2023_중앙값']}배 "
          f"(줄어든 지역 {report['검색이_줄어든_지역수']}/{report['지역수']}곳) vs "
          f"방문자 {report['방문자_2026대비2023_중앙값']}배")
    print(f"   지역별 검색 수준: {report['지역별_검색수준_최소']} ~ {report['지역별_검색수준_최대']} "
          f"({report['지역별_검색수준_최대'] / report['지역별_검색수준_최소']:.0f}배 차이)")
    print("   → 절대 수준을 전국 공통 모델에 넣으면 학습 구간 기준이 시험 구간에서 어긋난다")

    data = build_features(panel, HORIZON)
    data = pd.concat([data, redesigned_features(panel, HORIZON)], axis=1)

    def slice_split(name):
        start, end = SPLITS[name]
        return data[(data["observed_date"] >= start) & (data["observed_date"] <= end)]

    lag = [c for c in data.columns if c.startswith("vis_")]
    cal = ["day_of_week", "calendar_month", "is_weekend", "is_public_holiday", "rest_run_length"]
    fes = ["festival_active", "festival_pre", "festival_post"]
    nav_old = ["naver_last", "naver_mean7", "naver_mean28",
               "naver_ratio_7_28", "naver_jump", "naver_year_ratio"]
    nav_new = [c for c in data.columns if c.startswith("nv_")]
    nav_level_only = ["naver_last", "naver_mean7", "naver_mean28"]
    nav_ratio_only = ["naver_ratio_7_28", "naver_jump", "naver_year_ratio"]

    fit_frame = pd.concat([slice_split("train"), slice_split("valid")]).dropna(subset=lag + [TARGET])
    test = slice_split("test").copy()
    test = test[test[lag].notna().all(axis=1)].copy()

    configs = {
        "기준(검색 없음)": lag + cal + fes,
        "구버전 검색 6개": lag + cal + fes + nav_old,
        "수준만 3개": lag + cal + fes + nav_level_only,
        "비율만 3개": lag + cal + fes + nav_ratio_only,
        "개선 검색 6개": lag + cal + fes + nav_new,
    }

    print(f"\n2) 다시 재기 — 학습 {len(fit_frame):,}행 · 시험 {len(test):,}행 · 씨앗 {SEEDS}개")
    print(f"   {'구성':<18}{'변수수':>6}{'sMAPE':>9}")
    results = {}
    for label, columns in configs.items():
        preds = np.column_stack([fit_predict(fit_frame, test, columns, seed) for seed in range(SEEDS)])
        test[label] = preds.mean(axis=1)
        value = smape(test[TARGET].to_numpy(), test[label].to_numpy())
        results[label] = round(value, 3)
        print(f"   {label:<18}{len(columns):>6}{value:>9.3f}")

    comparisons = [
        evaluate(fit_frame, test, configs, "기준(검색 없음)", "구버전 검색 6개", "구버전 검색 추가"),
        evaluate(fit_frame, test, configs, "기준(검색 없음)", "수준만 3개", "절대 수준만 추가"),
        evaluate(fit_frame, test, configs, "기준(검색 없음)", "비율만 3개", "비율만 추가"),
        evaluate(fit_frame, test, configs, "기준(검색 없음)", "개선 검색 6개", "개선 검색 추가"),
        evaluate(fit_frame, test, configs, "구버전 검색 6개", "개선 검색 6개", "구버전 → 개선"),
    ]

    print("\n3) 판정 (음수 = 오차 감소 = 개선)")
    print(f"   {'비교':<20}{'sMAPE차':>9}{'95% 구간':>20}{'좋아짐':>7}{'나빠짐':>7}{'승률':>8}  판정")
    for row in comparisons:
        ci = f"[{row['95CI'][0]:+.3f}, {row['95CI'][1]:+.3f}]"
        print(f"   {row['비교']:<20}{row['sMAPE_차이']:>+9.3f}{ci:>20}"
              f"{row['좋아진_지역']:>7}{row['나빠진_지역']:>7}{row['지역승률_pct']:>7.1f}%  {row['판정']}")

    summary = {"진단": report, "구성별_sMAPE": results, "비교": comparisons,
               "horizon": HORIZON, "seeds": SEEDS,
               "시험_지역수": int(test["region_id"].nunique())}
    (INTERIM / "naver_redesign.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n출력: data/interim/naver_redesign.json")


if __name__ == "__main__":
    main()
