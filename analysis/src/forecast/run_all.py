"""전 과정을 한 번에 다시 돌리고, 결과가 동결본과 같은지까지 확인한다.

왜 필요한가
    스크립트가 열 개가 넘고 실행 순서가 있다. 하나를 빼먹고 돌리면 옛 결과가 섞여
    문서의 숫자와 어긋난다. 심사에서 "재현되나요"라는 질문에 답하려면 명령 하나로
    처음부터 끝까지 돌아가야 한다.

실행 순서 (앞 단계의 출력이 뒤 단계의 입력이다)
    1. build_panel        DB → 일별 패널            (DB 접속 필요)
    2. build_external     DB → 데이터랩 월간·근거·바이럴 (DB 접속 필요)
    3. baseline           예측 사다리
    4. models             모델 계열 비교
    5. ablation h=7/h=1   추가 데이터 기여도          (가장 오래 걸린다)
    6. detect             급증 탐지
    7. detect_ablation    월 단위 조기경보
    8. evidence_check     근거 기사 사용 가능성
    9. compare_pipelines  수영님 450건 대조·명절 정렬  (DB 접속 필요)
   10. point_level        전국 지점 vs 시군구
   11. point_level_rigor  반론 8종 검증
   12. figures            그림 8장
   13. freeze --check     동결본과 대조

사용법
    uv run python analysis/src/forecast/run_all.py              # 전체 (20~40분)
    uv run python analysis/src/forecast/run_all.py --offline    # DB 없이 (패널이 이미 있을 때)
    uv run python analysis/src/forecast/run_all.py --quick      # h=1 ablation 생략
    uv run python analysis/src/forecast/run_all.py --freeze     # 끝나고 대조 대신 새로 동결
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

# (표시 이름, 스크립트, 인자, DB 필요, 오래 걸림)
STEPS = [
    ("패널 생성", "build_panel.py", [], True, False),
    ("외부 데이터 내려받기", "build_external.py", [], True, False),
    ("예측 사다리", "baseline.py", [], False, False),
    ("모델 계열 비교", "models.py", [], False, True),
    ("기여도 실험 h=7", "ablation.py", ["--horizon", "7", "--seeds", "3"], False, True),
    ("기여도 실험 h=1", "ablation.py", ["--horizon", "1", "--seeds", "3"], False, True),
    ("급증 탐지", "detect.py", [], False, False),
    ("월 단위 조기경보", "detect_ablation.py", [], False, False),
    ("근거 기사 판정", "evidence_check.py", [], False, False),
    ("파이프라인 대조·명절 정렬", "compare_pipelines.py", [], True, False),
    ("전국 지점 분석", "point_level.py", [], True, False),
    ("반론 8종 검증", "point_level_rigor.py", [], False, False),
    ("그림 생성", "figures.py", [], False, False),
]


def run(script: str, arguments: list[str]) -> tuple[bool, float, str]:
    started = time.time()
    result = subprocess.run([sys.executable, str(HERE / script), *arguments],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(ROOT))
    elapsed = time.time() - started
    if result.returncode == 0:
        return True, elapsed, ""
    tail = (result.stderr or result.stdout or "").strip().splitlines()[-6:]
    return False, elapsed, "\n".join(f"      {line}" for line in tail)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="DB가 필요한 단계를 건너뛴다")
    parser.add_argument("--quick", action="store_true", help="오래 걸리는 단계를 건너뛴다")
    parser.add_argument("--freeze", action="store_true", help="끝나고 대조 대신 새로 동결한다")
    args = parser.parse_args()

    planned = [step for step in STEPS
               if not (args.offline and step[3]) and not (args.quick and step[4])]
    skipped = [step[0] for step in STEPS if step not in planned]

    print(f"재현 실행 — {len(planned)}단계" + (f" (건너뜀: {', '.join(skipped)})" if skipped else ""))
    print("=" * 66)

    results, failed = [], []
    for index, (label, script, arguments, _, _) in enumerate(planned, start=1):
        print(f"[{index:>2}/{len(planned)}] {label} ... ", end="", flush=True)
        ok, elapsed, tail = run(script, arguments)
        print(f"{'완료' if ok else '실패'} ({elapsed:.0f}초)")
        if not ok:
            print(tail)
            failed.append(label)
        results.append((label, ok, elapsed))

    total = sum(item[2] for item in results)
    print("=" * 66)
    print(f"{len(results) - len(failed)}/{len(results)}단계 성공 · 총 {total / 60:.1f}분")

    if failed:
        print(f"실패한 단계: {', '.join(failed)}")
        print("앞 단계가 실패하면 뒤 단계의 결과는 옛 값일 수 있습니다. 고친 뒤 다시 돌리세요.")
        sys.exit(1)

    print()
    freeze_args = [] if args.freeze else ["--check"]
    sys.stdout.flush()   # 자식 프로세스 출력과 순서가 섞이지 않게 먼저 비운다
    # 대조 결과는 사람이 읽어야 하므로 출력을 가로채지 않고 그대로 흘려보낸다
    finished = subprocess.run([sys.executable, str(HERE / "freeze.py"), *freeze_args],
                              cwd=str(ROOT))
    if finished.returncode != 0:
        print("\n동결본과 달라진 수치가 있습니다. 서식4에 옮긴 숫자를 고쳐야 합니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
