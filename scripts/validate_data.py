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


SEMANTIC_CHECKS = {"signal_status": check_signal_status}


def validate(data_dir: Path) -> int:
    store = {}
    for schema_path in SCHEMA_DIR.glob("*.schema.json"):
        schema = load(schema_path)
        store[schema["$id"]] = schema
        store[schema_path.name] = schema

    failures = 0
    for name in FILES:
        data_path = data_dir / f"{name}.json"
        schema_path = SCHEMA_DIR / f"{name}.schema.json"

        if not data_path.exists():
            print(f"[MISSING] {data_path.relative_to(ROOT)}")
            failures += 1
            continue

        schema = load(schema_path)
        resolver = RefResolver(base_uri=f"{SCHEMA_DIR.as_uri()}/", referrer=schema, store=store)
        validator = Draft7Validator(schema, resolver=resolver)
        payload = load(data_path)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)

        if errors:
            failures += 1
            print(f"[FAIL] {name}.json ({len(errors)}건)")
            for err in errors[:5]:
                location = "/".join(str(p) for p in err.absolute_path) or "(root)"
                print(f"    {location}: {err.message}")
        elif name in SEMANTIC_CHECKS and (rule_errors := SEMANTIC_CHECKS[name](payload)):
            failures += 1
            print(f"[FAIL] {name}.json (규칙 위반 {len(rule_errors)}건)")
            for msg in rule_errors:
                print(f"    {msg}")
        else:
            mock_flag = load(data_path).get("_mock", False)
            print(f"[OK]   {name}.json{'  (목업)' if mock_flag else ''}")

    return failures


if __name__ == "__main__":
    target = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "data/mock")
    print(f"검사 대상: {target.relative_to(ROOT)}\n")
    failed = validate(target)
    print(f"\n{'실패 ' + str(failed) + '건' if failed else '전체 통과'}")
    sys.exit(1 if failed else 0)
