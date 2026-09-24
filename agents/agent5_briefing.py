"""에이전트⑤ 브리핑 생성 — 담당 공무원이 아침에 읽는 3문단 브리핑을 data/prod/briefing.json으로 낸다.

역할 분담 (설계결정 D-04·D-08·D-10·D-11)
    코드  1문단(현재 상황)·2문단(예상 전개)을 데이터에서 템플릿으로 작성, 범위 밖 문장,
          권고 조치 원문·쪽수 삽입, 분량 맞추기, 검증
    LLM   3문단의 종합 판단 한 문장, 권고 조치 1~3건 선택과 사유

1·2문단을 코드가 쓰는 이유(D-11): 경보·교차검증·예측은 구조가 정해진 데이터라 규칙으로 쓰는 편이 정확하고,
매일 같은 문장 틀이어야 어제와 비교된다. solar-pro3는 분량 제한을 지키지 못했다(09.13 실측 — 목표 글자 수로
줄여 달라는 요청에도 251자를 233자로만 줄였다).

사용법:
    uv run python agents/agent5_briefing.py --dump-prompt
    uv run python agents/agent5_briefing.py                                  # .env에 있는 키로 자동 선택
    uv run python agents/agent5_briefing.py --provider upstage               # Upstage solar-pro3
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
ALERT_ORDER = ["관심", "주의", "경계", "심각"]
REQUIRED_FOR_LEVEL = {"주의": 1, "경계": 2, "심각": 3}  # D-05: 그 단계에 머무르는 요건
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
FORBIDDEN = re.compile(r"AI|인공지능|LLM|에이전트|분석한 결과|확실히|반드시")


# ── 표기 도우미 ────────────────────────────────────────────────────────────

def kdate(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month}월 {d.day}일({WEEKDAY[d.weekday()]})"


def pct(ratio: float) -> str:
    return f"{ratio * 100:.0f}%"


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


def _jong(word: str) -> int:
    """마지막 글자의 받침 번호. 한글이 아니면(괄호·숫자 등) 받침 없음으로 본다."""
    code = ord(word[-1]) - 0xAC00
    return code % 28 if 0 <= code <= 11171 else 0


def ro(word: str) -> str:
    return "로" if _jong(word) in (0, 8) else "으로"  # 8 = ㄹ받침


def eun(word: str) -> str:
    return "는" if _jong(word) == 0 else "은"


def eul(word: str) -> str:
    return "를" if _jong(word) == 0 else "을"


def iga(word: str) -> str:
    return "가" if _jong(word) == 0 else "이"


# ── 1·2문단과 범위 밖 문장 (코드가 데이터에서 쓴다, D-11) ─────────────────────────

# 템플릿 문장은 짧게 쓴다 — 코드가 아낀 글자만큼 3문단(권고 조치)에 예산이 돌아간다.
# 09.13 첫 템플릿은 1문단 194자·2문단 151자여서 권고가 1건만 들어갔다.
SIGNAL_SHORT = {"내비게이션 검색건수": "내비게이션 검색", "외지인 방문자수": "외지인 방문자"}


def signal_value(sig: dict, key: str) -> str:
    """신호 값 표기. %p는 전국 중앙값 대비 초과분, 배는 전년 동요일 대비 배율이다 (D-13)."""
    x = sig[key]
    if x is None:
        return "값 없음"
    unit = sig.get("unit", "")
    if unit == "비율":
        return pct(x)
    if unit == "%p":
        return f"{x:+}%p"
    return f"{x}{unit}"


def signal_phrase(sig: dict) -> str:
    name = re.sub(r"\s*전[주월년].*$", "", sig["signal"]).replace("목적지 ", "")
    name = SIGNAL_SHORT.get(name, name)
    basis = {"%p": " 전국 대비", "배": " 전년 대비"}.get(sig.get("unit", ""), "")
    body = f"{name}{basis} {signal_value(sig, 'value')}, 임계 {signal_value(sig, 'threshold')}"
    return f"{sig['stage']} 신호({body})" if sig.get("stage") else f"{name}({body})"


def demand_verdict(exceeded_stages: set) -> str:
    """v3 회의안 A의 판정 규칙: 세 지표가 모두 오르면 실수요, 언급량만 오르면 노이즈."""
    if exceeded_stages >= {"관심", "의도", "실현"}:
        return "세 신호가 모두 넘어 실수요로 판단된다."
    if exceeded_stages == {"관심"}:
        return "언급만 늘어 실수요는 아직 확정되지 않았다."
    if exceeded_stages == {"관심", "의도"}:
        return "검색까지 늘어 방문 전환 가능성이 높다."
    return ""


def render_situation(signal: dict) -> str:
    s = signal["data"]
    region, cur, prev = s["region"]["name"], s["alert_level"], s.get("previous_alert_level")
    # 월 단위 판정이면 기준 월을 밝힌다 — 오늘 상황으로 읽히지 않게 (D-13)
    if signal["period"]["granularity"] == "월":
        region = f"{date.fromisoformat(s['as_of']).month}월 기준 {region}"
    if prev and prev != cur:
        verb = "올렸다" if ALERT_ORDER.index(cur) > ALERT_ORDER.index(prev) else "내렸다"
        out = [f"{region} 경보를 {prev}에서 {cur}{ro(cur)} {verb}."]
    else:
        out = [f"{region} 경보는 {cur}{eul(cur)} 유지한다."]

    over = [x for x in s["cross_validation"] if x["exceeded"]]
    under = [x for x in s["cross_validation"] if not x["exceeded"]]
    a, b = "·".join(map(signal_phrase, over)), "·".join(map(signal_phrase, under))
    if over and under:
        out.append(f"{a}{'만' if len(over) == 1 else eun(a)} 임계를 넘고 {b}{eun(b)} 미달이다.")
    elif over:
        out.append(f"{a}{eun(a)} 모두 임계를 넘었다.")
    else:
        out.append(f"{b}{eun(b)} 모두 미달이다.")
    if verdict := demand_verdict({x.get("stage") for x in over}):
        out.append(verdict)
    # 현 단계 요건에 못 미쳤는데 유지한 경우 이유를 밝힌다 — "모두 미달인데 왜 주의인가"로 읽히지 않게 (D-05)
    held = (not prev or prev == cur) and cur != "관심" and len(over) < REQUIRED_FOR_LEVEL[cur]
    if held:
        out.append("하향은 2개월 연속 미달일 때만 한다.")
    if esc := s.get("escalation"):
        out.append(f"{esc['next_level']} 상향에는 3개 중 {esc['required_exceeded']}개 초과가 필요하다.")
    return " ".join(out)


def render_outlook(forecast: dict, checklist: dict) -> str:
    f = forecast["data"]
    daily = {d["date"]: d for d in f["daily"]}
    top, *others = f["peak_days"][:3]
    day = daily[top["date"]]
    metric = f["model"]["metric"]
    head = (f"최대 피크는 {kdate(top['date'])} {top['predicted']:,}명(80% 구간 {day['lower']:,}~{day['upper']:,}명)으로 "
            f"예상 경보 {top['expected_alert_level']}")
    perf = f"(검증 {metric['name']} {metric['value']}%)"
    if others:
        levels = {p["expected_alert_level"] for p in others}
        if len(levels) == 1:
            lvl = levels.pop()
            rest = f"{'·'.join(kdate(p['date']) for p in others)}도 {lvl}{iga(lvl)} 예상된다"
        else:
            rest = f"{', '.join(kdate(p['date']) + ' ' + p['expected_alert_level'] for p in others)} 단계가 예상된다"
        out = [f"{head}이며, {rest}{perf}."]
    else:
        out = [f"{head}이다{perf}."]
    types = [t["type"] for t in checklist["data"].get("assessment", {}).get("situation_types", [])]
    if types:
        out.append(f"예상 혼잡 유형은 {'·'.join(types)}이다.")
    return " ".join(out)


def render_out_of_scope(checklist: dict) -> str:
    issues = [o["issue"] for o in checklist["data"].get("assessment", {}).get("out_of_scope", [])]
    if not issues:
        return ""
    return f"{'·'.join(issues)}{eun(issues[-1])} 혼잡도 매뉴얼 범위 밖이어서 조치를 제시하지 않는다."


# ── facts (출력에 출처로 남기고, LLM 문장의 숫자를 대조하는 기준) ───────────────────

def build_facts(inputs: dict) -> list[dict]:
    facts: list[dict] = []

    def add(label: str, value: str, source: str, mock_of: str) -> None:
        if inputs[mock_of][1]:
            source += " [목업]"
        facts.append({"id": f"F{len(facts) + 1}", "label": label, "value": value, "source": source})

    s = inputs["signal_status"][0]["data"]
    add("경보 단계", f"{s['alert_level']} (직전 {s.get('previous_alert_level', '-')})",
        "3중 교차검증 판정(설계결정 D-05)", "signal_status")
    for sig in s["cross_validation"]:
        value, threshold = signal_value(sig, "value"), signal_value(sig, "threshold")
        label = f"{sig['stage']} 신호 — {sig['signal']}" if sig.get("stage") else sig["signal"]
        add(label, f"{value} (임계 {threshold}, {'초과' if sig['exceeded'] else '미달'})", sig["provider"], "signal_status")
    if esc := s.get("escalation"):
        add("다음 단계 상향 조건", f"{esc['next_level']} 상향에는 3개 신호 중 {esc['required_exceeded']}개 초과 필요, "
            f"현재 {esc['current_exceeded']}개", "설계결정 D-05", "signal_status")

    c = inputs["content_type"][0]["data"]
    total = sum(row["count"] for row in c["summary"])
    top = max(c["summary"], key=lambda r: r["count"])
    add("콘텐츠 유형 1위", f"{top['content_type']} {pct(top['ratio'])} ({top['count']}건/{total}건)",
        "YouTube Data API v3 수집, 에이전트② 분류", "content_type")
    counted = [i for i in c["items"] if i["confidence"] >= 0.6 and i["content_type"] != "관광무관"]
    poi, n = Counter(p for i in counted for p in i["poi_mentioned"]).most_common(1)[0]
    add("가장 많이 언급된 지점", f"{poi} ({n}개 영상)", "YouTube Data API v3 수집, 에이전트② 추출", "content_type")

    f = inputs["forecast"][0]["data"]
    daily = {d["date"]: d for d in f["daily"]}
    metric = f["model"]["metric"]
    add("예측 모델 성능", f"검증 {metric['name']} {metric['value']}%", "방문객 예측", "forecast")
    top_peak, *others = f["peak_days"][:3]
    day = daily[top_peak["date"]]
    add("최대 피크 예상일", f"{kdate(top_peak['date'])} {top_peak['predicted']:,}명 "
        f"(80% 구간 {day['lower']:,}~{day['upper']:,}명), 예상 경보 {top_peak['expected_alert_level']}", "방문객 예측", "forecast")
    if others:
        add("그 밖의 피크 예상일", ", ".join(f"{kdate(p['date'])} 예상 경보 {p['expected_alert_level']}" for p in others),
            "방문객 예측", "forecast")

    assessment = inputs["checklist"][0]["data"].get("assessment", {})
    if assessment.get("situation_types"):
        add("예상 혼잡 상황 유형", ", ".join(t["type"] for t in assessment["situation_types"]),
            "에이전트③ 판정(매뉴얼 p.39 분류)", "checklist")
    for issue in assessment.get("out_of_scope", []):
        add("매뉴얼 범위 밖 이슈", issue["issue"], "에이전트③ 판정", "checklist")
    return facts


def action_candidates(checklist: dict) -> list[dict]:
    # 발동 중인 항목만 권고할 수 있다. 대기 항목은 조건이 오기 전까지 권고하지 않는다(D-07).
    # 조치_글자수: LLM이 글자 수를 세지 못하므로 3문단 분량을 가늠할 수 있게 코드가 미리 알려 준다
    return [
        {"id": i["id"], "조치": i["action"], "조치_글자수": len(i["action"]), "쪽": i["manual_ref"]["page"],
         "시점": i["phase"], "우선순위": i["priority"], "relevance": i.get("relevance", "일반"), "사유": i.get("match_reason", "")}
        for i in checklist["data"]["items"] if i.get("status", "발동") == "발동"
    ]


def output_schema(action_ids: list[str]) -> dict:
    def obj(props: dict) -> dict:
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}

    return obj({
        "action_lead": {"type": "string"},
        "actions": {"type": "array", "items": obj({"id": {"type": "string", "enum": action_ids}, "why": {"type": "string"}})},
    })


# ── 3문단 조립과 검증 ────────────────────────────────────────────────────

def assemble_p3(lead: str, chosen: list[dict], candidates: dict, note: str,
                with_why: list[bool]) -> tuple[str, list[dict]]:
    parts, actions = [lead.strip()], []
    for mark, pick, show in zip(CIRCLED, chosen, with_why):
        cand = candidates[pick["id"]]
        why = pick["why"].strip().rstrip(".")
        parts.append(f"{mark} {cand['조치']} (p.{cand['쪽']})" + (f" — {why}." if show else "."))
        # 본문에서 뺀 사유도 JSON에는 남긴다 — 화면에서 툴팁으로 보여 줄 수 있다
        actions.append({"checklist_id": cand["id"], "action": cand["조치"], "page": cand["쪽"], "why": why})
    if note:
        parts.append(note)
    return " ".join(parts), actions


def verify_llm(out: dict, allowed: set[str]) -> list[str]:
    errors = []
    chosen = [a["id"] for a in out["actions"]]
    if not 1 <= len(chosen) <= MAX_ACTIONS:
        errors.append(f"권고 조치는 1~{MAX_ACTIONS}건이어야 한다 (현재 {len(chosen)}건)")
    if len(set(chosen)) != len(chosen):
        errors.append("같은 조치를 두 번 골랐다")
    written = {"종합 판단(action_lead)": out["action_lead"], **{f"{a['id']} 사유": a["why"] for a in out["actions"]}}
    for where, text in written.items():
        if stray := sorted(numbers(text) - allowed):
            errors.append(f"{where}의 숫자 {stray}가 facts에 없다 — 출처 없는 수치")
        if hit := FORBIDDEN.search(text):
            errors.append(f"{where}에 금지 표현 '{hit.group()}'")
    return errors


def fit_actions(p12_len: int, out: dict, candidates: dict, note: str) -> tuple[str, list[dict], dict]:
    """600자를 넘으면 ① 뒤쪽 권고부터 사유를 본문에서 빼고(모든 사유까지) ② 그래도 넘치면 뒤쪽 권고를 뺀다.

    D-04가 요구하는 것은 권고 조치와 쪽수이고 사유는 부가 정보다(JSON의 actions[].why에는 남는다).
    solar-pro3는 사유를 30자로 쓰라고 해도 40~60자로 써서(09.13) 권고를 빼는 방식으로는 1건만 남았다.
    09.16: 첫 권고의 사유를 끝까지 남기자, 조치 원문을 되풀이한 사유 때문에 권고가 1건으로 줄었다 — 첫 사유도 뺄 수 있게 했다.
    """
    chosen = list(out["actions"])
    n = len(chosen)
    plans = [[True] * k + [False] * (n - k) for k in range(n, -1, -1)]  # 사유를 뒤에서부터 하나씩 뺀 배치
    for with_why in plans:
        p3, actions = assemble_p3(out["action_lead"], chosen, candidates, note, with_why)
        if p12_len + len(p3) <= CHAR_MAX:
            return p3, actions, {"whys_omitted": with_why.count(False), "actions_dropped": 0}
    while len(chosen) > 1:
        chosen.pop()
        with_why = [False] * len(chosen)
        p3, actions = assemble_p3(out["action_lead"], chosen, candidates, note, with_why)
        if p12_len + len(p3) <= CHAR_MAX:
            break
    return p3, actions, {"whys_omitted": with_why.count(False), "actions_dropped": n - len(chosen)}


def main() -> None:
    parser = argparse.ArgumentParser(description="에이전트⑤ 브리핑 생성")
    parser.add_argument("--provider", choices=["anthropic", "upstage", "openai", "replay"],
                        help="기본: LLM_PROVIDER, 없으면 .env에 있는 키로 선택")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--response", type=Path)
    # solar-pro4 medium은 분량을 맞추려다 추론 토큰 15,993개로 16,000 한도를 다 썼다(09.13). 판단 범위가 좁아진
    # 지금도 긴 추론이 필요 없으므로 low를 기본으로 둔다
    parser.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high"],
                        help="추론 모델(upstage)의 추론 강도. 기본 low")
    parser.add_argument("--region", help="지역 코드(예: 51750). 기본(거제)은 파일명에 접미사가 없다")
    parser.add_argument("--dump-prompt", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out is None:
        args.out = OUT.with_name(f"briefing_{args.region}.json") if args.region else OUT

    inputs = {name: load_input(name, args.region) for name in ("signal_status", "forecast", "content_type", "checklist")}
    signal, forecast, checklist = (inputs[n][0] for n in ("signal_status", "forecast", "checklist"))
    facts = build_facts(inputs)
    allowed = set().union(*(numbers(f["label"] + " " + f["value"]) for f in facts))
    candidates = action_candidates(checklist)
    cand_map = {c["id"]: c for c in candidates}

    p1, p2, note = render_situation(signal), render_outlook(forecast, checklist), render_out_of_scope(checklist)
    p12_len = len(p1) + len(p2)
    budget = CHAR_MAX - p12_len
    print(f"1문단 {len(p1)}자 · 2문단 {len(p2)}자 (코드 작성) → 3문단 예산 {budget}자 / 권고 후보 {len(candidates)}건")

    system, prompt_version = load_prompt(PROMPT_PATH)
    user = json.dumps({
        "paragraph1_현재상황": p1, "paragraph2_예상전개": p2,
        "paragraph3_예산": {"전체_글자수": budget, "범위밖_문장": note, "범위밖_문장_글자수": len(note),
                          "도입과_조치에_쓸_수_있는_글자수": budget - len(note) - 1},
        "facts": facts, "action_candidates": candidates,
    }, ensure_ascii=False, indent=1)
    schema = output_schema(list(cand_map))
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    if args.dump_prompt:
        path = RUNS_DIR / f"agent5_request_{stamp}.json"
        path.write_text(json.dumps({"prompt_version": prompt_version, "system": system, "user": user, "schema": schema},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"요청 저장: {path.relative_to(ROOT)} (user {len(user):,}자)")
        return

    # 분량은 fit_actions가 코드로 맞춘다. LLM 재요청은 숫자·금지 표현 같은 규칙 위반에만 쓴다
    # (사유를 짧게 다시 쓰라는 재요청은 temperature 0의 solar-pro3에서 같은 출력만 돌아왔다, 09.13)
    message, errors = user, []
    for attempt in (1, 2, 3):
        try:
            result = complete_json(system, message, schema, provider=args.provider, model=args.model,
                                   base_url=args.base_url, response_path=args.response, max_tokens=16000,
                                   reasoning_effort=args.reasoning_effort)
        except LLMError as e:
            sys.exit(f"LLM 호출 실패: {e}")
        replayed = result.provider.startswith("replay")
        errors = verify_llm(result.data, allowed)
        if not errors:
            p3, actions, trim = fit_actions(p12_len, result.data, cand_map, note)
            total = p12_len + len(p3)
            if total > CHAR_MAX:
                errors.append(f"권고 조치를 1건으로 줄여도 {total}자 — 종합 판단(action_lead)과 첫 사유를 짧게 쓸 것 "
                              f"(3문단 예산 {budget}자, 현재 {len(p3)}자)")
            elif total < CHAR_MIN:
                errors.append(f"세 문단 합계 {total}자 — 종합 판단과 사유를 {CHAR_MIN - total}자 이상 늘릴 것")
        if not errors or replayed:
            break
        print(f"  반려({attempt}회차): {errors}")
        # 직전 출력과 이유를 함께 보여 주고 그 출력을 고치게 한다
        message = (user + "\n\n[직전 출력]\n" + json.dumps(result.data, ensure_ascii=False)
                   + "\n\n[고칠 점 — 직전 출력을 고쳐서 JSON 전체를 다시 출력]\n" + "\n".join(f"- {e}" for e in errors))

    if errors:
        if not replayed:
            rejected = RUNS_DIR / f"agent5_rejected_{stamp}.json"
            rejected.write_text(json.dumps({"prompt_version": prompt_version, "provider": result.provider,
                                            "model": result.model, "errors": errors, "response": result.data},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"반려 기록: {rejected.relative_to(ROOT)}")
        sys.exit(f"브리핑이 규칙을 어겼다: {errors}")

    if not replayed:
        log = RUNS_DIR / f"agent5_{stamp}.json"
        log.write_text(json.dumps({"prompt_version": prompt_version, "provider": result.provider, "model": result.model,
                                   "user": user, "response": result.data, "trim": trim},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"실행 로그: {log.relative_to(ROOT)}")

    paragraphs = [{"heading": "현재 상황", "text": p1}, {"heading": "예상 전개", "text": p2},
                  {"heading": "권고 조치", "text": p3}]
    mock_inputs = [n for n, (_, is_mock) in inputs.items() if is_mock]
    caveat = [
        "1·2문단과 범위 밖 문장은 코드가 입력 데이터로 작성했다. LLM은 3문단의 종합 판단과 권고 조치 선택·사유만 썼다(D-11).",
        "LLM이 쓴 문장의 숫자는 facts와 코드로 대조했다. 출처는 facts의 source에 있다(D-10).",
        "권고 조치 문장과 쪽수는 checklist.json의 매뉴얼 원문을 코드가 그대로 넣었다(D-08).",
        "예측 수치는 80% 구간과 함께 읽을 것. 구간을 벗어나는 날이 5일 중 1일꼴로 발생한다.",
    ]
    if trim["whys_omitted"]:
        caveat.append(f"분량(600자) 때문에 권고 {trim['whys_omitted']}건의 사유를 본문에서 뺐다. 사유는 actions의 why에 있다.")
    if trim["actions_dropped"]:
        caveat.append(f"분량(600자) 때문에 LLM이 고른 권고 {len(result.data['actions'])}건 중 "
                      f"{len(actions)}건만 실었다(선택 순서대로).")
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
            "facts": facts,
            "char_count": sum(len(p["text"]) for p in paragraphs),
            "model": {"name": result.model, "provider": result.provider, "prompt_version": prompt_version},
        },
    }
    if problems := validate_payload("briefing", payload):
        sys.exit(f"스키마 검증 실패: {problems[:5]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"출력: {args.out.relative_to(ROOT)}{'  (목업 입력 포함)' if payload['_mock'] else ''}")
    print(f"분량: {payload['data']['char_count']}자 / 권고 {len(actions)}건 / 본문에서 뺀 사유 {trim['whys_omitted']}건"
          + (f" / 뺀 권고 {trim['actions_dropped']}건" if trim["actions_dropped"] else "") + "\n")
    for p in paragraphs:
        print(f"[{p['heading']}] {p['text']}\n")


if __name__ == "__main__":
    main()
