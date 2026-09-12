"""에이전트 스크립트 공통 — 입력 로딩, 프롬프트 파일 파싱."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "agents" / "runs"


def load_input(name: str) -> tuple[dict, bool]:
    """data/prod에 있으면 그것을, 없으면 data/mock을 읽는다. (payload, 목업 여부)를 돌려준다."""
    for folder in ("prod", "mock"):
        path = ROOT / "data" / folder / f"{name}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload, bool(payload.get("_mock", False))
    raise FileNotFoundError(f"{name}.json이 data/prod에도 data/mock에도 없다")


def load_prompt(path: Path) -> tuple[str, str]:
    """프롬프트 파일에서 '# 시스템 프롬프트' 절과 버전을 읽는다. 설계 근거 절은 모델에 보내지 않는다."""
    text = path.read_text(encoding="utf-8")
    version = re.search(r"^version:\s*(\S+)", text, re.M).group(1)
    system = text.split("# 시스템 프롬프트", 1)[1].split("\n---\n", 1)[0].strip()
    return system, f"{path.stem}_{version}"


def merge_sources(*source_lists: list[dict]) -> list[dict]:
    merged = []
    for sources in source_lists:
        for src in sources:
            if src["name"] not in {s["name"] for s in merged}:
                merged.append(src)
    return merged
