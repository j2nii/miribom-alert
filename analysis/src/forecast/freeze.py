"""서식4에 들어갈 수치를 한 곳에 동결하고, 나중에 어긋나면 잡아낸다.

왜 필요한가
    문서를 쓰는 동안 코드를 한 번 더 돌리거나 데이터가 갱신되면 숫자가 조용히 바뀐다.
    서식4에 12.27%라고 적어 놓고 실제 결과가 12.31%가 되면, 심사에서 재현을 요청받았을 때
    답할 수 없다. 그래서 (1) 쓸 수치를 한 파일에 모으고 (2) 각 수치의 출처를 파일·키로 적고
    (3) 다시 돌렸을 때 달라졌는지 검사하는 기능을 함께 둔다.

    동결 대상은 **검증을 통과한 수치만**이다. 철회한 수치는 '금지' 목록에 남겨,
    실수로 다시 쓰는 일을 막는다.

사용법
    uv run python analysis/src/forecast/freeze.py            # 현재 결과를 동결 (덮어쓰기)
    uv run python analysis/src/forecast/freeze.py --check    # 동결본과 현재 결과를 대조
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"
FROZEN = INTERIM / "frozen_numbers.json"
REPORT = ROOT / "docs" / "확정수치_0924.md"

TOLERANCE = 1e-9   # 같은 코드·같은 데이터면 완전히 같아야 한다

# 입력 데이터가 바뀌면 수치가 바뀐다. 지문을 남겨 "왜 달라졌는가"를 즉시 가린다.
INPUT_FILES = ["panel_daily.csv", "datalab_monthly.csv", "attraction_monthly.csv"]


def dig(data, path: str):
    """'results.LAG+CAL.smape' 같은 경로로 중첩 구조에서 값을 꺼낸다. 리스트는 [0] 표기."""
    current = data
    for part in path.split("."):
        if part.endswith("]") and "[" in part:
            name, index = part[:-1].split("[")
            if name:
                current = current[name]
            current = current[int(index)]
        else:
            current = current[part]
    return current


def find_in_list(items, key: str, value, field: str):
    for item in items:
        if item.get(key) == value:
            return item[field]
    raise KeyError(f"{key}={value} 를 찾지 못했습니다")


# (이름, 출처 파일, 값 꺼내는 방법, 단위, 서식4 용도, 상태)
SPEC = [
    # ---------------- 예측 ----------------
    ("기준선_작년같은요일_sMAPE", "baseline_h7.json",
     lambda d: dig(d, "results.B1_작년같은요일.smape"), "%", "계량성과·3)(1)", "확정"),
    ("달력까지_sMAPE", "ablation_h7.json",
     lambda d: dig(d, "results.LAG+CAL+FES.smape"), "%", "계량성과·3)(1)", "확정"),
    ("데이터랩포함_sMAPE", "ablation_h7.json",
     lambda d: dig(d, "results.LAG+CAL+FES+NAV+DLB.smape"), "%", "핵심성과·계량성과", "확정"),
    ("최종_오차감축률", "ablation_h7.json",
     lambda d: round(100 * (12.27 - dig(d, "results.LAG+CAL+FES+NAV+DLB.smape")) / 12.27, 1),
     "%", "핵심성과 (12.27% 기준)", "확정"),
    ("데이터랩_기여_sMAPE차", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "데이터랩 월간 추가", "sMAPE_차이"),
     "%p", "2)·3)(1)", "확정"),
    ("데이터랩_기여_95CI", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "데이터랩 월간 추가", "지역평균차이_95CI"),
     "%p", "2)", "확정"),
    ("데이터랩_지역승률", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "데이터랩 월간 추가", "지역승률_pct"),
     "%", "계량성과", "확정"),
    ("데이터랩_위약제외_순수기여", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "진짜 데이터랩 - 위약 (순수 신호분)", "sMAPE_차이"),
     "%p", "2)", "확정"),
    ("검색_기여_sMAPE차", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "네이버 검색 추가", "sMAPE_차이"),
     "%p", "3)(1) 기여 없음 근거", "확정"),
    ("검색_기여_95CI", "ablation_h7.json",
     lambda d: find_in_list(d["comparisons"], "비교", "네이버 검색 추가", "지역평균차이_95CI"),
     "%p", "3)(1)", "확정"),
    ("테스트_행수", "ablation_h7.json", lambda d: d["test_rows"], "건", "2)", "확정"),
    ("테스트_지역수", "ablation_h7.json", lambda d: d["test_regions"], "개", "2)", "확정"),
    ("데이터랩_기여_h1", "ablation_h1.json",
     lambda d: find_in_list(d["comparisons"], "비교", "데이터랩 월간 추가", "sMAPE_차이"),
     "%p", "부록(1일 앞에서도 같음)", "확정"),

    # ---------------- 지점 쏠림 ----------------
    ("지점_관측수", "point_level.json", lambda d: d["지점_관측수"], "건", "3)(2)", "확정"),
    ("지점수", "point_level.json", lambda d: d["지점수"], "곳", "3)(2)", "확정"),
    ("지점_시군구수", "point_level.json", lambda d: d["시군구수"], "개", "3)(2)", "확정"),
    ("지점급증_건수", "point_level.json", lambda d: d["지점급증_건수"], "건", "계량성과", "확정"),
    ("사각지대_건수", "point_level.json", lambda d: d["사각지대_건수"], "건", "핵심성과·계량성과", "확정"),
    ("사각지대_시군구수", "point_level.json", lambda d: d["사각지대_시군구수"], "개", "계량성과", "확정"),
    ("지점배율_상위1pct", "point_level.json", lambda d: d["지점_배율분포"]["상위1%"], "배", "3)(2)", "확정"),
    ("시군구배율_상위1pct", "point_level.json", lambda d: d["시군구_배율분포"]["상위1%"], "배", "3)(2)", "확정"),
    ("지점배율_최대", "point_level.json", lambda d: d["지점_배율분포"]["최대"], "배", "3)(2)", "확정"),
    ("시군구배율_최대", "point_level.json", lambda d: d["시군구_배율분포"]["최대"], "배", "1)·3)(2)", "확정"),

    # ---------------- 반론 검증 ----------------
    ("R1_지점비중_중앙값", "point_level_rigor.json",
     lambda d: d["R1_지점비중_pct"]["중앙값"], "%", "3)(2) 감지 불가능성", "확정"),
    ("R1_총량기여_중앙값", "point_level_rigor.json",
     lambda d: d["R1_총량기여_pp"]["중앙값"], "%p", "3)(2) 감지 불가능성", "확정"),
    ("R1_시군구잡음_표준편차", "point_level_rigor.json",
     lambda d: d["R1_시군구배율_표준편차"], "배", "3)(2)", "확정"),
    ("R1_필요배율_중앙값", "point_level_rigor.json",
     lambda d: d["R1_필요배율_중앙값"], "배", "3)(2) 핵심 문장", "확정"),
    ("R2_과거최대초과", "point_level_rigor.json",
     lambda d: d["R2_과거상위5%초과"]["과거최대초과"], "건", "3)(2)", "확정"),
    ("R2_대상건수", "point_level_rigor.json",
     lambda d: d["R2_과거상위5%초과"]["대상"], "건", "3)(2)", "확정"),
    ("R3_2025년_비율", "point_level_rigor.json",
     lambda d: find_in_list(d["R3_연도재현"], "연도", "2025", "비율_pct"), "%", "3)(2) 재현성", "확정"),
    ("R3_2026년_비율", "point_level_rigor.json",
     lambda d: find_in_list(d["R3_연도재현"], "연도", "2026", "비율_pct"), "%", "3)(2) 재현성", "확정"),
    ("R5_비율_95CI", "point_level_rigor.json", lambda d: d["R5_비율95CI_pct"], "%", "계량성과", "확정"),
    ("R7_검색판별력_AUC", "point_level_rigor.json",
     lambda d: d["R7_검색판별력_AUC"], "AUC", "3)(2) 검색으로는 안 된다", "확정"),
    ("R8_월평균경보", "point_level_rigor.json", lambda d: d["R8_월평균경보"], "건/월", "3)(2-1) 운영 부담", "확정"),
    ("R8_시군구당_월경보", "point_level_rigor.json",
     lambda d: d["R8_시군구당_월경보"], "건/월", "3)(2-1)", "확정"),

    # ---------------- 명절 정렬 ----------------
    ("명절정렬_임계초과지역", "pipeline_comparison.json",
     lambda d: d["holiday_aligned_national"]["above_threshold"], "곳", "1)·3)(3)", "확정"),
    ("명절정렬_중앙값", "pipeline_comparison.json",
     lambda d: d["holiday_aligned_national"]["median_ratio"], "배", "1)·3)(3)", "확정"),
    ("명절정렬_최대", "pipeline_comparison.json",
     lambda d: d["holiday_aligned_national"]["max_ratio"], "배", "1)·3)(3)", "확정"),

    # ---------------- 조기경보(부정 결과) ----------------
    ("경보_검증구간_AUC_2025_10", "detect_ablation.json",
     lambda d: next(r["AUC"] for r in d["within_month"]
                    if r["월"] == "2025-10" and r["신호"] == "결합(검색+데이터랩)" and r["라벨"] == "전년대비"),
     "AUC", "3) 한계", "확정"),
    ("경보_테스트구간_AUC_2026_02", "detect_ablation.json",
     lambda d: next(r["AUC"] for r in d["within_month"]
                    if r["월"] == "2026-02" and r["신호"] == "결합(검색+데이터랩)" and r["라벨"] == "전년대비"),
     "AUC", "3) 한계", "확정"),

    # ---------------- 근거 기사 ----------------
    ("근거기사_커버리지", "evidence_check.json", lambda d: d["coverage_pct"], "%", "2) 쓰지 않은 이유", "확정"),

    # ---------------- 파이프라인 대조 ----------------
    ("수영님_에피소드_전체", "pipeline_comparison.json", lambda d: d["final_episodes"], "건", "3) 대조", "확정"),
    ("수영님_에피소드_테스트", "pipeline_comparison.json", lambda d: d["final_episodes_test"], "건", "3) 대조", "확정"),
]

# 09.26 측정: 씨앗 묶음 3벌((0,1,2)/(3,4,5)/(6,7,8))로 같은 실험을 돌려 승률이 얼마나 흔들리는지
# 잰 결과. 효과가 실재하는 변수는 승률이 거의 고정이고, 효과가 없는 변수만 크게 흔들린다.
STABILITY = [
    ("달력 추가", "94.3 / 95.2 / 94.3", "0.9%p", "−1.382 ~ −1.363", "그대로 인용 가능"),
    ("데이터랩 월간 추가", "75.4 / 77.2 / 75.0", "2.2%p", "−0.316 ~ −0.273", "그대로 인용 가능"),
    ("네이버 검색 추가", "44.3 / 54.4 / 51.3", "10.1%p", "+0.020 ~ +0.026", "**승률 인용 금지**"),
]

FORBIDDEN = [
    ("전년대비 급증 43건을 탐지했다", "설 날짜 이동 인공물. 명절 정렬 시 임계 초과 0곳 (D-15)"),
    ("검색 신호 필터링으로 경보 품질 2배 개선(상승도 1.99)", "기저율을 전국 평균으로 잡은 착시. 지역 맞춤 시 1.03 (09.22 철회)"),
    ("검색이 방문 급증을 며칠 앞서 알려준다", "상승도 1.0~1.25, 임계·연도에 따라 방향이 뒤집힘"),
    ("SNS 언급량이 예측을 개선한다", "위약 대조군 대비 잡음 수준 (방문자 계열 제외 시 기여 사라짐)"),
    ("날씨를 넣어 sMAPE 8.70%까지 낮췄다", "대상일 실측 날씨는 예측 시점에 알 수 없음(상한 모델)"),
    ("뉴스 기사량을 변수로 활용했다", "커버리지 1.28%·정답 주변 표집·52.8%가 사후 발행 → 입력 금지"),
    ("검색을 넣으면 228곳 중 127곳에서 오히려 나빠진다",
     "승률 44.3%는 씨앗 묶음 3벌 중 가장 낮은 값(44.3/54.4/51.3). 효과가 없는 변수라 흔들린 것이므로 '차이 없음'으로만 쓴다"),
]


def fingerprint() -> dict:
    """입력 파일의 크기와 해시. 숫자가 달라졌을 때 '데이터가 바뀐 것인지'를 먼저 가린다."""
    marks = {}
    for name in INPUT_FILES:
        path = INTERIM / name
        if not path.exists():
            marks[name] = None
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        marks[name] = {"bytes": path.stat().st_size, "sha256": digest.hexdigest()[:16]}
    return marks


def collect() -> tuple[dict, list[str]]:
    cache, values, missing = {}, {}, []
    for name, source, getter, unit, usage, status in SPEC:
        path = INTERIM / source
        if source not in cache:
            if not path.exists():
                cache[source] = None
            else:
                cache[source] = json.loads(path.read_text(encoding="utf-8"))
        data = cache[source]
        if data is None:
            missing.append(f"{name} ← {source} 없음")
            continue
        try:
            values[name] = {"값": getter(data), "단위": unit, "출처": source,
                            "용도": usage, "상태": status}
        except (KeyError, IndexError, StopIteration, TypeError) as error:
            missing.append(f"{name} ← {source} 에서 값을 꺼내지 못함 ({error})")
    return values, missing


def write_report(frozen: dict) -> None:
    lines = [
        "# 확정 수치 — 서식4에 이 값만 쓴다",
        "",
        f"> 동결 {frozen['동결시각']} · 생성 `uv run python analysis/src/forecast/freeze.py`",
        "> 대조 `uv run python analysis/src/forecast/freeze.py --check` — 값이 하나라도 달라지면 알려준다.",
        "",
        "숫자를 문서에 옮길 때는 **반드시 이 표에서** 가져온다. 스크립트 출력이나 대화 기록에서 옮기지 않는다.",
        "",
        "## 확정 수치",
        "",
        "| 이름 | 값 | 단위 | 서식4 용도 | 출처 파일 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, item in frozen["수치"].items():
        value = item["값"]
        shown = f"{value[0]} ~ {value[1]}" if isinstance(value, list) else value
        lines.append(f"| `{name}` | **{shown}** | {item['단위']} | {item['용도']} | `{item['출처']}` |")

    lines += ["", "## 쓰면 안 되는 문장", "",
              "| 쓰지 않는다 | 이유 |", "| --- | --- |"]
    for sentence, reason in frozen["금지"]:
        lines.append(f"| ~~{sentence}~~ | {reason} |")

    lines += ["", "## 지역 승률을 인용하기 전에 (09.26 측정)", "",
              "같은 실험을 씨앗 묶음 3벌로 돌려 승률이 얼마나 흔들리는지 쟀다.",
              "**효과가 실재하는 변수는 승률이 거의 고정이고, 효과가 없는 변수만 크게 흔들린다.**", "",
              "| 비교 | 씨앗 묶음별 승률(%) | 흔들림 폭 | sMAPE 차이 범위 | 판단 |",
              "| --- | --- | --- | --- | --- |"]
    for name, values, spread, gap, verdict in STABILITY:
        lines.append(f"| {name} | {values} | {spread} | {gap} | {verdict} |")

    lines += ["", "## 입력 데이터 지문", "",
              "수치가 달라졌다면 먼저 여기를 본다. 지문이 같은데 값이 다르면 코드가 바뀐 것이다.", "",
              "| 파일 | 크기 | sha256(앞 16자리) |", "| --- | --- | --- |"]
    for name, mark in frozen["입력지문"].items():
        if mark is None:
            lines.append(f"| `{name}` | (없음) | — |")
        else:
            lines.append(f"| `{name}` | {mark['bytes']:,} bytes | `{mark['sha256']}` |")

    lines += ["", "## 재현 절차", "",
              "```bash",
              "uv run python analysis/src/forecast/run_all.py         # 전 과정 재실행",
              "uv run python analysis/src/forecast/freeze.py --check  # 동결본과 대조",
              "```", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def freeze() -> None:
    values, missing = collect()
    frozen = {
        "동결시각": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "기준일": "데이터 마지막 날 2026-08-14 (지점 입장객은 2026-06)",
        "수치": values,
        "금지": FORBIDDEN,
        "입력지문": fingerprint(),
    }
    FROZEN.write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(frozen)
    print(f"동결 완료 — 수치 {len(values)}개 · 금지 문장 {len(FORBIDDEN)}개")
    if missing:
        print(f"주의: {len(missing)}개 수치를 넣지 못했습니다 (해당 스크립트를 먼저 실행하세요)")
        for item in missing:
            print(f"  - {item}")
    print(f"출력: {FROZEN.relative_to(ROOT)} · {REPORT.relative_to(ROOT)}")


def check() -> int:
    if not FROZEN.exists():
        print("동결본이 없습니다. 먼저 인자 없이 실행하세요.")
        return 1
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    current, missing = collect()

    drifted, gone = [], []
    for name, item in frozen["수치"].items():
        if name not in current:
            gone.append(name)
            continue
        before, after = item["값"], current[name]["값"]
        same = (before == after) or (
            isinstance(before, (int, float)) and isinstance(after, (int, float))
            and abs(before - after) <= TOLERANCE)
        if not same:
            drifted.append((name, before, after, item["출처"]))

    marks_before, marks_after = frozen["입력지문"], fingerprint()
    changed_inputs = [name for name in marks_before if marks_before[name] != marks_after.get(name)]

    print(f"동결 시각 {frozen['동결시각']} · 수치 {len(frozen['수치'])}개 대조")
    if changed_inputs:
        print(f"입력 데이터가 바뀌었습니다: {', '.join(changed_inputs)}")
    else:
        print("입력 데이터 지문 일치")

    if not drifted and not gone and not missing:
        print("\n모든 수치가 동결본과 같습니다. 서식4의 숫자를 그대로 쓰면 됩니다.")
        return 0

    if drifted:
        print(f"\n달라진 수치 {len(drifted)}개 — 서식4를 고쳐야 합니다")
        for name, before, after, source in drifted:
            print(f"  {name:<28} 동결 {before} → 현재 {after}   ({source})")
    if gone:
        print(f"\n현재 결과에서 사라진 수치 {len(gone)}개: {', '.join(gone)}")
    if missing:
        print(f"\n꺼내지 못한 수치 {len(missing)}개")
        for item in missing:
            print(f"  - {item}")
    if changed_inputs:
        print("\n입력이 바뀌었다면 값이 달라지는 것이 정상입니다. 확인 후 다시 동결하세요.")
    else:
        print("\n입력은 그대로인데 값이 달라졌습니다. 코드 변경을 먼저 확인하세요.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="동결본과 현재 결과를 대조만 한다")
    args = parser.parse_args()
    sys.exit(check() if args.check else (freeze() or 0))


if __name__ == "__main__":
    main()
