"""manual/checklist_items.json이 태그 체계를 지키는지 검사한다.

사용법:
    python scripts/validate_manual.py                 # manual/checklist_items.json
    python scripts/validate_manual.py manual/checklist_items.sample.json
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

시점 = {"사전(예보 대응)", "오전(준비)", "운영 중(모니터링)", "비상 대응", "마감(평가)"}  # 사전: D-07
상황유형 = {"유입 급증형", "병목 정체형", "안전 위험형", "민원 급증형"}  # 매뉴얼 p.39, 선택 필드
단계 = {"관심", "주의", "경계", "심각"}
혼잡도단계 = {1, 2, 3, 4, 5}
공간유형 = {
    "네트워크 보행 흐름형",
    "지형·경사 이동·저항 흐름형",
    "실내 공간 가치 체류 중심형",
    "실외 공간 가치 체류 중심형",
}
우선순위 = {"최우선", "높음", "보통"}

REQUIRED = ["id", "시점", "단계", "혼잡도단계", "공간유형", "프로파일", "조치", "담당", "우선순위", "근거"]
REQUIRED_근거 = ["문서", "쪽", "절", "원문"]


def check(item: dict, index: int) -> list[str]:
    errors = []
    label = item.get("id") or f"{index}번째 항목"

    for field in REQUIRED:
        if field not in item:
            errors.append(f"{label}: '{field}' 필드 없음")

    if "id" in item and not (item["id"].startswith("CL-") and item["id"][3:].isdigit()):
        errors.append(f"{label}: id는 CL-001 형식이어야 함")

    if item.get("시점") not in 시점:
        errors.append(f"{label}: 시점 '{item.get('시점')}'은 허용 목록에 없음")

    for value in item.get("단계", []):
        if value not in 단계:
            errors.append(f"{label}: 단계 '{value}'은 허용 목록에 없음")
    if item.get("단계") == []:
        errors.append(f"{label}: 단계가 비어 있음 — 최소 1개 필요")

    for value in item.get("혼잡도단계", []):
        if value not in 혼잡도단계:
            errors.append(f"{label}: 혼잡도단계 '{value}'은 1~5 범위 밖")

    if item.get("혼잡도단계") == []:
        errors.append(f"{label}: 혼잡도단계가 비어 있음 — 상관없으면 [1,2,3,4,5]")

    for value in item.get("공간유형", []):
        if value not in 공간유형:
            errors.append(f"{label}: 공간유형 '{value}'은 허용 목록에 없음")

    for value in item.get("상황유형", []):
        if value not in 상황유형:
            errors.append(f"{label}: 상황유형 '{value}'은 허용 목록에 없음")

    if item.get("우선순위") not in 우선순위:
        errors.append(f"{label}: 우선순위 '{item.get('우선순위')}'은 허용 목록에 없음")

    if not str(item.get("조치", "")).strip():
        errors.append(f"{label}: 조치가 비어 있음")

    근거 = item.get("근거", {})
    for field in REQUIRED_근거:
        if not str(근거.get(field, "")).strip():
            errors.append(f"{label}: 근거.{field}가 비어 있음 — 근거 없는 항목은 화면에 표시되지 않음")

    return errors


if __name__ == "__main__":
    target = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "manual/checklist_items.json")

    if not target.exists():
        print(f"파일 없음: {target.relative_to(ROOT)}")
        sys.exit(1)

    items = json.loads(target.read_text(encoding="utf-8")).get("items", [])
    all_errors = [e for i, item in enumerate(items, 1) for e in check(item, i)]

    ids = [item.get("id") for item in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        all_errors.append(f"id 중복: {', '.join(sorted(duplicates))}")

    print(f"검사 대상: {target.relative_to(ROOT)}")
    print(f"항목 수: {len(items)}건\n")

    for error in all_errors:
        print(f"  [FAIL] {error}")

    print(f"\n{'실패 ' + str(len(all_errors)) + '건' if all_errors else '전체 통과'}")
    sys.exit(1 if all_errors else 0)
