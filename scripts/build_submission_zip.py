"""제출용 참고자료 Zip을 만든다.

공모요강: "응모작과 관련된 '실제 업무 활용보고서' 및 '성과보고서' 등의 모든 참고 자료는
Zip파일로 압축해 첨부 요망" (선택 제출)

심사에서 "이 숫자는 어디서 왔나", "재현되나"라는 질문이 나올 때 답이 되는 것만 넣는다.
분석 원자료(패널 34MB 등)는 넣지 않는다 — 용량이 크고 개인정보 심사 대상이 될 수 있다.

넣지 않는 것 (확인 목록)
    .env, 접속 정보, 원본 CSV, 코드 실행 캐시

사용법
    uv run python scripts/build_submission_zip.py
    uv run python scripts/build_submission_zip.py --check   # 빠진 파일만 확인하고 만들지 않는다
"""

import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "submission"

# (Zip 안 경로, 원본 경로, 설명, 필수 여부)
CONTENTS = [
    ("01_그림/", "docs/submission/figures", "서식4·발표용 그림 8장", True),
    ("02_검증보고서/추가데이터_검증.md", "docs/분석_검증_추가데이터_0924.md",
     "어떤 데이터가 실제로 예측을 개선하는가 (위약 대조군 포함)", True),
    ("02_검증보고서/지점쏠림_반론검증.md", "docs/분석_지점쏠림_반론검증_0924.md",
     "핵심 주장에 대한 반론 8가지와 답", True),
    ("02_검증보고서/누출점검표.md", "docs/분석_누출점검표.md",
     "변수별 공개 시점 판단 — 미래 정보를 쓰지 않았다는 근거", True),
    ("03_사례/영월_거제.md", "docs/사례_영월_거제_0924.md",
     "주 사례와 대비 사례, 언론 인용 출처", True),
    ("03_사례/지점급증_원인확인.md", "docs/사례_지점급증_원인확인_0924.md",
     "사각지대 사례의 원인 추적", True),
    ("04_수치/확정수치.md", "docs/확정수치_0924.md",
     "문서의 모든 숫자와 그 출처 파일", True),
    ("05_분석코드/", "analysis/src/forecast", "분석 코드 전체 + 실행 순서 README", True),
    ("06_운영규칙/신호_조치_매핑표.md", "docs/신호_조치_매핑표.md",
     "경보 단계와 매뉴얼 조치의 연결 (지점 신호 포함)", True),
    ("06_운영규칙/설계결정.md", "docs/설계결정.md", "설계 결정 이력 D-01~D-16", True),
    ("07_웹서비스/", "docs/submission/web_screenshots",
     "웹 대시보드 화면 (지은·수영 제공 예정)", False),
]

SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_NAMES = {"__pycache__", ".env", ".env.local"}

README = """제출 참고자료 — 구성 안내

이 압축 파일은 응모작의 분석 과정과 수치 근거를 담고 있습니다.
서식4 본문의 모든 숫자는 04_수치/확정수치.md 에서 출처 파일과 함께 확인할 수 있습니다.

폴더 구성
  01_그림/          서식4와 발표에 쓴 그림
  02_검증보고서/    결과를 믿어도 되는지 확인한 기록 (반론 8가지에 대한 답 포함)
  03_사례/          영월·거제 사례와 전국 급증 사례의 원인 추적
  04_수치/          문서에 쓴 모든 숫자와 출처
  05_분석코드/      분석 코드 전체
  06_운영규칙/      경보 규칙과 관광지 혼잡도 운영관리 매뉴얼의 연결
  07_웹서비스/      웹 대시보드 화면 (해당 시)

재현 방법
  1) 분석 코드는 Python 3.13 + pandas + scikit-learn 으로 동작합니다
  2) 05_분석코드/README.md 의 실행 순서를 따르면 모든 수치가 다시 생성됩니다
  3) run_all.py 는 전 과정을 한 번에 실행하고, freeze.py --check 는 결과가
     04_수치/확정수치.md 와 같은지 자동으로 대조합니다
  4) 원자료는 공개 데이터(한국관광 데이터랩, 공공데이터포털, 기상청)이며
     접속 정보는 포함하지 않았습니다

분석 기준일
  시군구 일별 방문자 2026-08-14 / 관광지점 월별 입장객 2026-06
"""


def collect_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in SKIP_SUFFIXES or any(part in SKIP_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="빠진 항목만 확인한다")
    args = parser.parse_args()

    plan, missing = [], []
    for target, relative, note, required in CONTENTS:
        source = ROOT / relative
        if not source.exists():
            missing.append((relative, note, required))
            continue
        for path in collect_files(source):
            inside = (target + path.name) if target.endswith("/") and source.is_dir() else target
            if source.is_dir():
                inside = target + str(path.relative_to(source)).replace("\\", "/")
            plan.append((inside, path, note))

    total_bytes = sum(path.stat().st_size for _, path, _ in plan)
    print(f"담을 파일 {len(plan)}개 · {total_bytes / 1_048_576:.1f}MB")
    for target, relative, note, required in ((m[0], m[0], m[1], m[2]) for m in missing):
        mark = "필수" if required else "선택"
        print(f"  [{mark}] 빠짐: {relative} — {note}")

    blocking = [item for item in missing if item[2]]
    if blocking:
        print(f"\n필수 항목 {len(blocking)}개가 없습니다. 먼저 채워야 합니다.")
        sys.exit(1)

    if args.check:
        print("\n확인만 했습니다 (--check). 실제로 만들려면 인자 없이 실행하세요.")
        return

    stamp = datetime.now().strftime("%Y%m%d")
    out_path = OUT_DIR / f"제출첨부_{stamp}.zip"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("00_안내.txt", README)
        for inside, path, _ in plan:
            archive.write(path, inside)

    size = out_path.stat().st_size / 1_048_576
    print(f"\n생성: {out_path.relative_to(ROOT)} ({size:.1f}MB, 파일 {len(plan) + 1}개)")
    if size > 20:
        print("주의: 20MB가 넘습니다. 그림 해상도를 낮추거나 코드만 남기는 것을 검토하세요.")
    print("제출 전 확인: 압축을 풀어 00_안내.txt 와 04_수치/확정수치.md 를 읽어볼 것")


if __name__ == "__main__":
    main()
