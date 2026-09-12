"""에이전트⑤ 브리핑 생성 — 담당 공무원이 아침에 읽는 3문단 브리핑을 data/prod/briefing.json으로 낸다.

역할 분담 (설계결정 D-04·D-08·D-10)
    코드  수치 목록(facts) 준비, 3문단 조립, 권고 조치 원문·쪽수 삽입, 길이·수치·금지어 검증
    LLM   1·2문단 서술, 권고 조치 1~3건 선택과 사유, 범위 밖 이슈 한 문장

LLM이 쓴 문장 속 숫자는 모두 LLM이 인용했다고 밝힌 facts 안에 있어야 한다. 아니면 반려한다.

사용법:
    uv run python agents/agent5_briefing.py --dump-prompt
    uv run --extra llm python agents/agent5_briefing.py                     # Anthropic API
    uv run python agents/agent5_briefing.py --provider openai --model qwen2.5:14b
    uv run python agents/agent5_briefing.py --provider replay --response agents/runs/agent5_xxx.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "agents"))

from common import RUNS_DIR, load_input, load_prompt, merge_sources  # noqa: E402
from llm_client import LLMError, complete_json  # noqa: E402
from validate_data import validate_payload  # noqa: E402

PROMPT_PATH = ROOT / "agents" / "prompts" / "agent5_briefing.md"
OUT = ROOT / "data" / "prod" / "briefing.json"

CHAR_MIN, CHAR_MAX = 400, 600  # D-04
MAX_ACTIONS = 3
CIRCLED = "①②③"
WEEKDAY = "월화수목금토일"
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
FORBIDDEN = re.compile(r"AI|인공지능|LLM|에이전트|분석한 결과|확실히|반드시")


def kdate(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}월 {d.day}일({WEEKDAY[d.weekday()]})"


def pct(ratio: float) -> str:
    return f"{ratio * 100:.0f}%"


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


# ── facts (코드가 사람이 읽는 표기로 미리 만든다) ──────────────────────────────

def build_facts(inputs: dict) -> list[dict]:
    facts: list[dict] = []

    def add(label: str, value: str, source: str, kind: str = "basic", mock_of: str | None = None) -> None:
        if mock_of and inputs[mock_of][1]:
            source += " [목업]"
        facts.append({"id": f"F{len(facts) + 1}", "label": label, "value": value, "source": source, "kind": kind})

    s = inputs["signal_status"][0]["data"]
    add("경보 단계", f"{s['alert_level']} (직전 {s.get('previous_alert_level', '-')})",
        "3중 교차검증 판정(설계결정 D-05)", mock_of="signal_status")
    add("혼잡도 단계", f"{s['congestion_level']}단계", "혼잡도 단계 기준(매뉴얼 p.53)", mock_of="signal_status")
    for sig in s["cross_validation"]:
        ratio = sig.get("unit") == "비율"
        value = pct(sig["value"]) if ratio else f"{sig['value']}{sig.get('unit', '')}"
        threshold = pct(sig["threshold"]) if ratio else f"{sig['threshold']}{sig.get('unit', '')}"
        label = f"{sig['stage']} 신호 — {sig['signal']}" if sig.get("stage") else sig["signal"]
        add(label, f"{value} (임계 {threshold}, {'초과' if sig['exceeded'] else '미달'})",
            sig["provider"], "signal", mock_of="signal_status")
    if esc := s.get("escalation"):
        add("다음 단계 상향 조건",
            f"{esc['next_level']} 상향에는 3개 신호 중 {esc['required_exceeded']}개 초과 필요, 현재 {esc['current_exceeded']}개",
            "설계결정 D-05", mock_of="signal_status")

    c = inputs["content_type"][0]["data"]
    total = sum(row["count"] for row in c["summary"])
    top = max(c["summary"], key=lambda r: r["count"])
    add("콘텐츠 유형 1위", f"{top['content_type']} {pct(top['ratio'])} ({top['count']}건/{total}건)",
        "YouTube Data API v3 수집, 에이전트② 분류", mock_of="content_type")
    counted = [i for i in c["items"] if i["confidence"] >= 0.6 and i["content_type"] != "관광무관"]
    poi, n = Counter(p for i in counted for p in i["poi_mentioned"]).most_common(1)[0]
    add("가장 많이 언급된 지점", f"{poi} ({n}개 영상)", "YouTube Data API v3 수집, 에이전트② 추출", mock_of="content_type")

    f = inputs["forecast"][0]["data"]
    daily = {d["date"]: d for d in f["daily"]}
    add("예측 기간", f"{kdate(f['daily'][0]['date'])}~{kdate(f['daily'][-1]['date'])}", "방문객 예측", mock_of="forecast")
    metric = f["model"]["metric"]
    add("예측 모델 성능", f"{f['model']['name']}, 검증 {metric['name']} {metric['value']}%", "방문객 예측", mock_of="forecast")
    for i, peak in enumerate(f["peak_days"][:3], 1):
        day = daily[peak["date"]]
        add(f"피크 예상일 {i}",
            f"{kdate(peak['date'])} {peak['predicted']:,}명 (80% 구간 {day['lower']:,}~{day['upper']:,}명), 예상 경보 {peak['expected_alert_level']}",
            "방문객 예측", "forecast", mock_of="forecast")

    assessment = inputs["checklist"][0]["data"].get("assessment", {})
    if assessment.get("situation_types"):
        add("예상 혼잡 상황 유형", ", ".join(t["type"] for t in assessment["situation_types"]),
            "에이전트③ 판정(매뉴얼 p.39 분류)", mock_of="checklist")
    for issue in assessment.get("out_of_scope", []):
        add("매뉴얼 범위 밖 이슈", issue["issue"], "에이전트③ 판정", mock_of="checklist")
    return facts


def action_candidates(checklist: dict) -> list[dict]:
    # 발동 중인 항목만 권고할 수 있다. 대기 항목은 조건이 오기 전까지 권고하지 않는다(D-07).
    return [
        {"id": i["id"], "조치": i["action"], "쪽": i["manual_ref"]["page"], "시점": i["phase"],
         "우선순위": i["priority"], "relevance": i.get("relevance", "일반"), "사유": i.get("match_reason", "")}
        for i in checklist["data"]["items"] if i.get("status", "발동") == "발동"
    ]


def output_schema(action_ids: list[str], fact_ids: list[str]) -> dict:
    def obj(props: dict) -> dict:
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}

    return obj({
        "situation": {"type": "string"},
        "outlook": {"type": "string"},
        "action_lead": {"type": "string"},
        "actions": {"type": "array", "items": obj({"id": {"type": "string", "enum": action_ids}, "why": {"type": "string"}})},
        "out_of_scope_note": {"type": "string"},
        "used_facts": {"type": "array", "items": {"type": "string", "enum": fact_ids}},
    })


# ── 조립과 검증 (코드) ────────────────────────────────────────────────────

def assemble(out: dict, candidates: dict) -> tuple[list[dict], list[dict]]:
    actions, parts = [], [out["action_lead"].strip()]
    for mark, chosen in zip(CIRCLED, out["actions"]):
        cand = candidates[chosen["id"]]
        why = chosen["why"].strip().rstrip(".")
        parts.append(f"{mark} {cand['조치']} (p.{cand['쪽']}) — {why}.")
        actions.append({"checklist_id": cand["id"], "action": cand["조치"], "page": cand["쪽"], "why": why})
    if note := out["out_of_scope_note"].strip():
        parts.append(note)
    paragraphs = [
        {"heading": "현재 상황", "text": out["situation"].strip()},
        {"heading": "예상 전개", "text": out["outlook"].strip()},
        {"heading": "권고 조치", "text": " ".join(parts)},
    ]
    return paragraphs, actions


def verify(out: dict, facts: dict, candidates: dict) -> list[str]:
    errors = []
    chosen = [a["id"] for a in out["actions"]]
    if not 1 <= len(chosen) <= MAX_ACTIONS:
        errors.append(f"권고 조치는 1~{MAX_ACTIONS}건이어야 한다 (현재 {len(chosen)}건)")
    if len(set(chosen)) != len(chosen):
        errors.append("같은 조치를 두 번 골랐다")

    used = [facts[i] for i in dict.fromkeys(out["used_facts"])]
    allowed = set().union(*(numbers(f["label"] + " " + f["value"]) for f in used)) if used else set()
    written = {
        "1문단": out["situation"], "2문단": out["outlook"], "3문단 도입": out["action_lead"],
        "범위 밖 문장": out["out_of_scope_note"], **{f"{a['id']} 사유": a["why"] for a in out["actions"]},
    }
    for where, text in written.items():
        if stray := sorted(numbers(text) - allowed):
            errors.append(f"{where}의 숫자 {stray}가 used_facts에 없다 — 출처 없는 수치")
        if hit := FORBIDDEN.search(text):
            errors.append(f"{where}에 금지 표현 '{hit.group()}'")

    if any(f["kind"] == "forecast" for f in used) and "구간" not in out["outlook"]:
        errors.append("2문단이 예측값을 쓰면서 구간을 밝히지 않았다")

    if not errors:
        paragraphs, _ = assemble(out, candidates)
        total = sum(len(p["text"]) for p in paragraphs)
        if not CHAR_MIN <= total <= CHAR_MAX:
            errors.append(f"세 문단 합계 {total}자 — {CHAR_MIN}~{CHAR_MAX}자로 맞출 것")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="에이전트⑤ 브리핑 생성")
    parser.add_argument("--provider", choices=["anthropic", "openai", "replay"])
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--response", type=Path)
    parser.add_argument("--dump-prompt", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    inputs = {name: load_input(name) for name in ("signal_status", "forecast", "content_type", "checklist")}
    facts = build_facts(inputs)
    fact_map = {f["id"]: f for f in facts}
    candidates = action_candidates(inputs["checklist"][0])
    cand_map = {c["id"]: c for c in candidates}

    system, prompt_version = load_prompt(PROMPT_PATH)
    user = json.dumps({"facts": [{k: f[k] for k in ("id", "label", "value", "source")} for f in facts],
                       "action_candidates": candidates}, ensure_ascii=False, indent=1)
    schema = output_schema(list(cand_map), list(fact_map))
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    print(f"facts {len(facts)}개 / 권고 후보 {len(candidates)}건")

    if args.dump_prompt:
        path = RUNS_DIR / f"agent5_request_{stamp}.json"
        path.write_text(json.dumps({"prompt_version": prompt_version, "system": system, "user": user, "schema": schema},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"요청 저장: {path.relative_to(ROOT)} (user {len(user):,}자)")
        return

    message, errors = user, []
    for attempt in (1, 2):
        try:
            result = complete_json(system, message, schema, provider=args.provider, model=args.model,
                                   base_url=args.base_url, response_path=args.response, max_tokens=8000)
        except LLMError as e:
            sys.exit(f"LLM 호출 실패: {e}")
        errors = verify(result.data, fact_map, cand_map)
        replayed = result.provider.startswith("replay")
        if not errors or replayed:
            break
        print(f"  반려({attempt}회차): {errors}")
        # 무엇이 틀렸는지 알려 주고 한 번 더 쓰게 한다 (prefill 없이 user 메시지에 덧붙인다)
        message = user + "\n\n[직전 출력이 반려된 이유 — 고쳐서 다시 출력]\n" + "\n".join(f"- {e}" for e in errors)
    if errors:
        sys.exit(f"브리핑이 규칙을 어겼다: {errors}")

    if not replayed:
        log = RUNS_DIR / f"agent5_{stamp}.json"
        log.write_text(json.dumps({"prompt_version": prompt_version, "provider": result.provider, "model": result.model,
                                   "user": user, "response": result.data}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"실행 로그: {log.relative_to(ROOT)}")

    paragraphs, actions = assemble(result.data, cand_map)
    used = [fact_map[i] for i in dict.fromkeys(result.data["used_facts"])]
    signal, forecast = inputs["signal_status"][0], inputs["forecast"][0]
    mock_inputs = [n for n, (_, is_mock) in inputs.items() if is_mock]
    caveat = [
        "문장 속 수치는 facts 목록의 값만 썼으며 코드가 대조 검증했다. 출처는 facts의 source에 있다(D-10).",
        "권고 조치 문장과 쪽수는 checklist.json의 매뉴얼 원문을 코드가 그대로 넣었다(D-08).",
        "예측 수치는 80% 구간과 함께 읽을 것. 구간을 벗어나는 날이 5일 중 1일꼴로 발생한다.",
    ]
    if mock_inputs:
        caveat.insert(0, f"입력 중 목업이 있다({', '.join(mock_inputs)}). 문장 구조 검증용이며 수치로 판단하지 말 것.")

    payload = {
        "_mock": bool(mock_inputs),
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": merge_sources(*(inputs[n][0]["source"] for n in inputs)),
        "period": {"start": signal["data"]["as_of"], "end": forecast["period"]["end"], "granularity": "일"},
        "caveat": caveat,
        "data": {
            "region": signal["data"]["region"],
            "as_of": signal["data"]["as_of"],
            "alert_level": signal["data"]["alert_level"],
            "paragraphs": paragraphs,
            "actions": actions,
            "facts": [{k: f[k] for k in ("id", "label", "value", "source")} for f in used],
            "char_count": sum(len(p["text"]) for p in paragraphs),
            "model": {"name": result.model, "provider": result.provider, "prompt_version": prompt_version},
        },
    }
    if problems := validate_payload("briefing", payload):
        sys.exit(f"스키마 검증 실패: {problems[:5]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"출력: {args.out.relative_to(ROOT)}{'  (목업 입력 포함)' if payload['_mock'] else ''}")
    print(f"분량: {payload['data']['char_count']}자 / 인용 facts {len(used)}개\n")
    for p in paragraphs:
        print(f"[{p['heading']}] {p['text']}\n")


if __name__ == "__main__":
    main()
