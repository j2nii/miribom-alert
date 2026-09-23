"""data/mock 또는 data/prod의 JSON이 data/schema 계약을 지키는지 검사한다.

사용법:
    python scripts/validate_data.py data/mock
    python scripts/validate_data.py data/prod
"""

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

from jsonschema import Draft7Validator, RefResolver
import itertools

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "data" / "schema"

FILES = [
    "signal_status",
    "forecast",
    "visitor_profile",
    "hotspots",
    "content_type",
    "checklist",
    "precedent",
    "before_after",
    "timeline",
    "briefing",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


ALERT_ORDER = ["관심", "주의", "경계", "심각"]
# 설계결정 D-05: 다음 단계로 올라가는 데 필요한 임계 초과 신호 수
REQUIRED_FOR_NEXT = {"주의": 1, "경계": 2, "심각": 3}


def check_signal_status(payload: dict) -> list[str]:
    """스키마로 표현할 수 없는 필드 간 규칙(D-05)을 검사한다."""
    d = payload["data"]
    errors = []
    exceeded = sum(1 for s in d["cross_validation"] if s["exceeded"])
    if d["agreement"]["exceeded_count"] != exceeded:
        errors.append(f"agreement.exceeded_count={d['agreement']['exceeded_count']}인데 exceeded=true 신호는 {exceeded}개")

    for sig in d["cross_validation"]:
        if sig["value"] is None and (sig["exceeded"] or not sig.get("missing_reason")):
            errors.append(f"{sig.get('stage', sig['signal'])}: 값이 없으면 exceeded=false이고 missing_reason이 있어야 한다")

    history = d.get("history")
    if history:  # D-13: 이력의 마지막 항목이 현재 판정이다
        last = history[-1]
        if (last["as_of"], last["alert_level"], last["exceeded_count"]) != (d["as_of"], d["alert_level"], exceeded):
            errors.append("history 마지막 항목이 as_of·alert_level·초과 개수와 다르다")
        if len(history) > 1 and d.get("previous_alert_level") != history[-2]["alert_level"]:
            errors.append("previous_alert_level이 history 직전 항목과 다르다")
        for prev, cur in itertools.pairwise(history):
            step = ALERT_ORDER.index(cur["alert_level"]) - ALERT_ORDER.index(prev["alert_level"])
            expected = {1: "상향", -1: "하향", 0: "유지"}.get(step)
            if expected is None or cur["change"] != expected:
                errors.append(f"{cur['as_of']}: 한 달에 한 단계씩만 움직이고 change가 이동과 맞아야 한다 (D-05)")

    esc = d.get("escalation")
    if esc is None:
        return errors
    level = d["alert_level"]
    if level == "심각":
        errors.append("최고 단계(심각)에는 escalation을 두지 않는다")
        return errors
    expected_next = ALERT_ORDER[ALERT_ORDER.index(level) + 1]
    if esc["next_level"] != expected_next:
        errors.append(f"escalation.next_level은 {expected_next}여야 한다 (현재 {esc['next_level']})")
    if esc["required_exceeded"] != REQUIRED_FOR_NEXT[expected_next]:
        errors.append(f"{level}→{expected_next} 상향 요건은 {REQUIRED_FOR_NEXT[expected_next]}/3 (D-05)")
    if esc["current_exceeded"] != exceeded:
        errors.append(f"escalation.current_exceeded={esc['current_exceeded']}인데 실제 초과 {exceeded}개")
    if esc["met"] != (exceeded >= esc["required_exceeded"]) and expected_next != "심각":
        # 경계→심각은 혼잡도 5단계 실측으로도 충족되므로 개수만으로 판정하지 않는다
        errors.append("escalation.met이 초과 개수와 맞지 않는다")
    return errors


def check_briefing(payload: dict) -> list[str]:
    """D-04: 문단 순서 고정, 글자 수 일치, 권고 조치는 원문·쪽수 그대로 3문단에."""
    d = payload["data"]
    errors = []
    headings = [p["heading"] for p in d["paragraphs"]]
    if headings != ["현재 상황", "예상 전개", "권고 조치"]:
        errors.append(f"문단 순서는 현재 상황 → 예상 전개 → 권고 조치 (현재 {headings})")
    total = sum(len(p["text"]) for p in d["paragraphs"])
    if total != d["char_count"]:
        errors.append(f"char_count={d['char_count']}인데 실제 {total}자")
    last = d["paragraphs"][-1]["text"]
    for a in d["actions"]:
        if a["action"] not in last or f"p.{a['page']}" not in last:
            errors.append(f"{a['checklist_id']}의 원문 또는 쪽수가 권고 조치 문단에 없다")
    return errors


SEMANTIC_CHECKS = {"signal_status": check_signal_status, "briefing": check_briefing}


def validate_payload(name: str, payload: dict) -> list[str]:
    """스키마 검사 후, 통과하면 필드 간 규칙까지 검사한다. 에이전트 스크립트도 이 함수로 출력 직전 검증한다."""
    store = {}
    for schema_path in SCHEMA_DIR.glob("*.schema.json"):
        schema = load(schema_path)
        store[schema["$id"]] = schema
        store[schema_path.name] = schema

    schema = store[f"{name}.schema.json"]
    resolver = RefResolver(base_uri=f"{SCHEMA_DIR.as_uri()}/", referrer=schema, store=store)
    errors = sorted(Draft7Validator(schema, resolver=resolver).iter_errors(payload), key=lambda e: e.path)
    if errors:
        return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in errors]
    return SEMANTIC_CHECKS[name](payload) if name in SEMANTIC_CHECKS else []


def validate(data_dir: Path, partial: bool = False) -> int:
    failures = 0
    for name in FILES:
        data_path = data_dir / f"{name}.json"

        if not data_path.exists():
            if partial:
                print(f"[없음] {name}.json")
            else:
                print(f"[MISSING] {data_path.relative_to(ROOT)}")
                failures += 1
            continue

        failures += check_file(name, data_path)

    # 지역별 추가 파일 — 기본 지역은 {name}.json, 그 밖의 지역은 {name}_{시군구코드}.json (D-12)
    for data_path in sorted(data_dir.glob("*_[0-9][0-9][0-9][0-9][0-9].json")):
        name = data_path.stem.rsplit("_", 1)[0]
        if name in FILES:
            failures += check_file(name, data_path)

    return failures


def check_file(name: str, data_path: Path) -> int:
    payload = load(data_path)
    errors = validate_payload(name, payload)
    if errors:
        print(f"[FAIL] {data_path.name} ({len(errors)}건)")
        for msg in errors[:5]:
            print(f"    {msg}")
        return 1
    print(f"[OK]   {data_path.name}{'  (목업)' if payload.get('_mock', False) else ''}")
    return 0


if __name__ == "__main__":
    # --partial: 아직 교체되지 않은 파일은 실패로 세지 않는다 (data/prod 점진 교체 중에 사용)
    partial = "--partial" in sys.argv
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = ROOT / (positional[0] if positional else "data/mock")
    print(f"검사 대상: {target.relative_to(ROOT)}\n")
    failed = validate(target, partial)
    print(f"\n{'실패 ' + str(failed) + '건' if failed else '전체 통과'}")
    sys.exit(1 if failed else 0)
