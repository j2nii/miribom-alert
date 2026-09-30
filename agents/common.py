"""에이전트 스크립트 공통 — 입력 로딩, 프롬프트 파일 파싱."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "agents" / "runs"


def load_input(name: str, region: str | None = None) -> tuple[dict, bool]:
    """data/prod에 있으면 그것을, 없으면 data/mock을 읽는다. (payload, 목업 여부)를 돌려준다.

    region이 있으면 {name}_{region}.json을 찾는다(기본 지역인 거제는 접미사 없이
    {name}.json) — agent_hotspots.py 등 다른 지역별 산출물과 같은 파일명 규칙이다.
    다른 지역의 파일로 대신 채우지 않는다(발명 금지) — 없으면 그대로 에러를 낸다.
    """
    filename = f"{name}_{region}.json" if region else f"{name}.json"
    for folder in ("prod", "mock"):
        path = ROOT / "data" / folder / filename
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload, bool(payload.get("_mock", False))
    raise FileNotFoundError(f"{filename}이 data/prod에도 data/mock에도 없다")


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
