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
        errors = sorted(validator.iter_errors(load(data_path)), key=lambda e: e.path)

        if errors:
            failures += 1
            print(f"[FAIL] {name}.json ({len(errors)}건)")
            for err in errors[:5]:
                location = "/".join(str(p) for p in err.absolute_path) or "(root)"
                print(f"    {location}: {err.message}")
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
