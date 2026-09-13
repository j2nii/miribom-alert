"""에이전트③ 매뉴얼 매칭 — 현재 상황에 해당하는 매뉴얼 조치를 골라 data/prod/checklist.json으로 낸다.

역할 분담 (설계결정 D-08)
    코드  후보 선별(D-03 필터 + D-07 혼잡도 조건), 정렬, 조치 문장·원문 복사
    LLM   상황 유형 판정, 매뉴얼 범위 밖 이슈, 후보별 관련도와 사유

입력은 data/prod/{이름}.json이 있으면 그것을, 없으면 data/mock/을 쓴다.
입력 중 하나라도 목업이면 결과도 _mock: true다.

사용법:
    uv run python agents/agent3_match.py --dump-prompt                 # LLM 요청만 저장
    uv run --extra llm python agents/agent3_match.py                    # .env에 있는 키로 자동 선택
    uv run python agents/agent3_match.py --provider upstage              # Upstage Solar
    uv run python agents/agent3_match.py --provider openai --model qwen2.5:14b   # 로컬 서버
    uv run python agents/agent3_match.py --provider replay --response agents/runs/agent3_xxx.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from jsonschema import Draft7Validator

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")  # sys.exit 메시지가 윈도우 콘솔에서 깨지지 않게

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "agents"))

from common import load_input, load_prompt, merge_sources  # noqa: E402
from llm_client import LLMError, complete_json  # noqa: E402
from validate_data import validate_payload  # noqa: E402

PROMPT_PATH = ROOT / "agents" / "prompts" / "agent3_manual_match.md"
MANUAL_PATH = ROOT / "manual" / "checklist_items.json"
RUNS_DIR = ROOT / "agents" / "runs"
OUT = ROOT / "data" / "prod" / "checklist.json"

MANUAL_DOC = "지속가능한 관광지 혼잡도 운영 관리 매뉴얼(한국관광공사, 2026.03)"
MANUAL_SRC = {
    "name": "지속가능한 관광지 혼잡도 운영 관리 매뉴얼",
    "provider": "한국관광공사",
    "retrieved_at": "2026-09-12",
    "url": "https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1603&bcIdx=310400",
}
SITUATION_TYPES = ["유입 급증형", "병목 정체형", "안전 위험형", "민원 급증형"]
RELEVANCE = ["핵심", "관련", "일반"]

# 정렬: 상태(D-07) → 우선순위 → 시점 → 관련도(D-08) → id (D-03)
STATUS_ORDER = {"발동": 0, "대기": 1}
PRIORITY_ORDER = {"최우선": 0, "높음": 1, "보통": 2}
PHASE_ORDER = {"사전(예보 대응)": 0, "오전(준비)": 1, "운영 중(모니터링)": 2, "비상 대응": 3, "마감(평가)": 4}
RELEVANCE_ORDER = {r: i for i, r in enumerate(RELEVANCE)}


# ── 입력 ────────────────────────────────────────────────────────────────

def normalize_poi(name: str) -> str:
    return re.sub(r"\s+", "", name)


def build_situation(signal: dict, hotspots: dict, profile: dict, content: dict, spatial_type: str) -> dict:
    s, h, p, c = signal["data"], hotspots["data"], profile["data"], content["data"]
    counted = [i for i in c["items"] if i["confidence"] >= 0.6 and i["content_type"] != "관광무관"]
    poi_counts = Counter(poi for item in counted for poi in item["poi_mentioned"])
    top_videos = sorted(counted, key=lambda i: -i["view_count"])[:8]

    return {
        "region": s["region"]["name"],
        "as_of": s["as_of"],
        "alert_level": s["alert_level"],
        "previous_alert_level": s.get("previous_alert_level"),
        "congestion_level": s["congestion_level"],
        "cross_validation": [
            {k: v for k, v in sig.items() if k in ("stage", "signal", "value", "threshold", "exceeded", "trend")}
            for sig in s["cross_validation"]
        ],
        "escalation": s.get("escalation"),
        "target_spatial_type": spatial_type,
        "hotspots_top5": [
            {k: v for k, v in spot.items() if k in ("rank", "poi_name", "spatial_type", "congestion_level", "change_rate", "bottleneck")}
            for spot in h["ranking"][:5]
        ],
        "visitor_profile_tags": p.get("profile_tags", []),
        "content_type_share": [
            {"content_type": row["content_type"], "count": row["count"], "ratio": row["ratio"]} for row in c["summary"]
        ],
        "repeated_pois": [{"poi": poi, "videos": n} for poi, n in poi_counts.most_common(8)],
        "top_videos": [
            {"title": v["title"], "content_type": v["content_type"], "view_count": v["view_count"], "poi_mentioned": v["poi_mentioned"]}
            for v in top_videos
        ],
        "zone_signals": [
            {"title": i["title"], "zone_signal": i["zone_signal"], "poi_mentioned": i["poi_mentioned"], "sentiment": i["sentiment"]}
            for i in c["items"] if i.get("zone_signal")
        ],
        "negative_videos": [i["title"] for i in c["items"] if i.get("sentiment") == "부정"],
    }


# ── 후보 선별 (코드) ──────────────────────────────────────────────────────

def standby_condition(levels: list[int]) -> str:
    low = min(levels)
    if levels == list(range(low, 6)):
        return f"혼잡도 {low}단계 이상 관측 시" if low < 5 else "혼잡도 5단계 관측 시"
    return f"혼잡도 {'·'.join(map(str, levels))}단계 관측 시"


def select_candidates(records: list[dict], alert: str, congestion: int, spatial: str, profile_tags: list[str]):
    candidates, excluded = [], 0
    for r in records:
        if alert not in r["단계"]:  # 1차 (D-03)
            excluded += 1
        elif r["공간유형"] and spatial not in r["공간유형"]:  # 2차
            excluded += 1
        elif r["프로파일"] and not set(r["프로파일"]) & set(profile_tags):  # 3차
            excluded += 1
        else:
            status = "발동" if congestion in r["혼잡도단계"] else "대기"  # D-07
            candidates.append((r, status))
    return candidates, excluded


def candidate_view(record: dict, status: str) -> dict:
    view = {"id": record["id"], "조치": record["조치"], "시점": record["시점"], "우선순위": record["우선순위"], "status": status}
    if status == "대기":
        view["발동조건"] = standby_condition(record["혼잡도단계"])
    if record["공간유형"]:
        view["공간유형"] = record["공간유형"]
    if record.get("상황유형"):
        view["상황유형"] = record["상황유형"]
    return view


def output_schema(ids: list[str]) -> dict:
    # 후보 id를 enum으로 묶어 존재하지 않는 항목을 만들 수 없게 한다 (D-08)
    def obj(props: dict) -> dict:
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}

    return obj({
        "situation_types": {"type": "array", "items": obj({
            "type": {"type": "string", "enum": SITUATION_TYPES}, "evidence": {"type": "string"}})},
        "out_of_scope": {"type": "array", "items": obj({"issue": {"type": "string"}, "evidence": {"type": "string"}})},
        "judgments": {"type": "array", "items": obj({
            "id": {"type": "string", "enum": ids},
            "relevance": {"type": "string", "enum": RELEVANCE},
            "reason": {"type": "string"}})},
    })


def check_response(data: dict, schema: dict, ids: list[str]) -> list[str]:
    errors = [e.message for e in Draft7Validator(schema).iter_errors(data)]
    if errors:
        return errors
    judged = [j["id"] for j in data["judgments"]]
    missing = sorted(set(ids) - set(judged))
    duplicated = sorted({i for i in judged if judged.count(i) > 1})
    if missing:
        errors.append(f"판정 누락: {', '.join(missing)}")
    if duplicated:
        errors.append(f"중복 판정: {', '.join(duplicated)}")
    return errors


# ── 출력 ────────────────────────────────────────────────────────────────

def build_payload(candidates, excluded, verdict, situation, inputs, model_info) -> dict:
    judgments = {j["id"]: j for j in verdict["judgments"]}
    items = []
    for record, status in candidates:
        j = judgments[record["id"]]
        item = {
            "id": record["id"],
            "phase": record["시점"],
            "action": record["조치"],
            "owner": record["담당"],
            "priority": record["우선순위"],
            "alert_level": situation["alert_level"],
            "spatial_type": record["공간유형"],
            "profile_tags": record["프로파일"],
            "manual_ref": {
                "document": MANUAL_DOC,
                "page": record["근거"]["쪽"],
                "section": record["근거"]["절"],
                "quote": record["근거"]["원문"],
            },
            "match_reason": j["reason"],
            "status": status,
            "relevance": j["relevance"],
        }
        if status == "대기":
            item["standby_condition"] = standby_condition(record["혼잡도단계"])
        if record.get("상황유형"):
            item["situation_type"] = record["상황유형"]
        items.append(item)

    items.sort(key=lambda i: (STATUS_ORDER[i["status"]], PRIORITY_ORDER[i["priority"]],
                              PHASE_ORDER[i["phase"]], RELEVANCE_ORDER[i["relevance"]], i["id"]))
    for rank, item in enumerate(items, 1):
        item["rank"] = rank

    signal, hotspots, _profile, content = (inputs[n][0] for n in ("signal_status", "hotspots", "visitor_profile", "content_type"))
    mock_inputs = [name for name, (_, is_mock) in inputs.items() if is_mock]

    content_pois = {normalize_poi(p["poi"]) for p in situation["repeated_pois"]}
    hotspot_pois = {normalize_poi(s["poi_name"]) for s in hotspots["data"]["ranking"]}
    caveat = [
        f"매뉴얼 구조화가 진행 중이다. 현재 {len(json.loads(MANUAL_PATH.read_text(encoding='utf-8'))['items'])}건 기준으로 매칭했으며, "
        "전체 항목이 반영되면 결과가 늘어난다(분산 유도 조치 p.40 등 미포함).",
        "조치 문장·쪽수·원문은 구조화 레코드에서 그대로 복사했다. LLM은 관련도·사유·상황 유형만 판정했다(D-08).",
        "'대기' 항목은 현재 혼잡도가 조건에 미달한 현장 조치다. 선행 신호만으로는 발동하지 않는다(D-07).",
        f"공간 유형은 급증 지점 1위 기준({situation['target_spatial_type']})이다. 지점별로 유형이 다르면 결과가 달라진다.",
    ]
    if mock_inputs:
        caveat.insert(0, f"입력 중 목업이 있다({', '.join(mock_inputs)}). 판정 방식 검증용이며 수치로 판단하지 말 것.")
    if len(content_pois & hotspot_pois) <= 1:
        caveat.append("콘텐츠 반복 언급 지점과 급증 지점 명칭이 거의 일치하지 않는다. POI 명칭 정규화 전이다.")

    top_type = max(content["data"]["summary"], key=lambda r: r["count"])["content_type"]
    sources = merge_sources([MANUAL_SRC], signal["source"], content["source"])

    return {
        "_mock": bool(mock_inputs),
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": sources,
        "period": {"start": signal["data"]["as_of"], "end": signal["data"]["as_of"], "granularity": "일"},
        "caveat": caveat,
        "data": {
            "region": signal["data"]["region"],
            "matched_for": {
                "alert_level": situation["alert_level"],
                "congestion_level": situation["congestion_level"],
                "spatial_type": situation["target_spatial_type"],
                "content_type": top_type,
                "profile_tags": situation["visitor_profile_tags"],
            },
            "items": items,
            "excluded_count": excluded,
            "assessment": {"situation_types": verdict["situation_types"], "out_of_scope": verdict["out_of_scope"]},
            "model": model_info,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="에이전트③ 매뉴얼 매칭")
    parser.add_argument("--provider", choices=["anthropic", "upstage", "openai", "replay"],
                        help="기본: LLM_PROVIDER, 없으면 .env에 있는 키로 선택")
    parser.add_argument("--model")
    parser.add_argument("--base-url", help="openai 백엔드 주소")
    parser.add_argument("--response", type=Path, help="replay 백엔드가 읽을 응답 파일")
    parser.add_argument("--spatial-type", help="매칭 기준 공간 유형. 기본: 급증 지점 1위의 유형")
    parser.add_argument("--dump-prompt", action="store_true", help="LLM을 호출하지 않고 요청만 저장")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    inputs = {name: load_input(name) for name in ("signal_status", "hotspots", "visitor_profile", "content_type")}
    signal, hotspots, profile, content = (inputs[n][0] for n in inputs)
    spatial = args.spatial_type or hotspots["data"]["ranking"][0]["spatial_type"]
    situation = build_situation(signal, hotspots, profile, content, spatial)

    records = json.loads(MANUAL_PATH.read_text(encoding="utf-8"))["items"]
    candidates, excluded = select_candidates(
        records, situation["alert_level"], situation["congestion_level"], spatial, situation["visitor_profile_tags"])
    ids = [r["id"] for r, _ in candidates]
    active = sum(1 for _, s in candidates if s == "발동")
    print(f"상황: {situation['alert_level']} / 혼잡도 {situation['congestion_level']} / {spatial}")
    print(f"후보 {len(candidates)}건 (발동 {active} · 대기 {len(candidates) - active}) / 제외 {excluded}건")

    system, prompt_version = load_prompt(PROMPT_PATH)
    user = json.dumps({"situation": situation, "candidates": [candidate_view(r, s) for r, s in candidates]},
                      ensure_ascii=False, indent=1)
    schema = output_schema(ids)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    if args.dump_prompt:
        path = RUNS_DIR / f"agent3_request_{stamp}.json"
        path.write_text(json.dumps({"prompt_version": prompt_version, "system": system, "user": user, "schema": schema},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"요청 저장: {path.relative_to(ROOT)} (user {len(user):,}자)")
        return

    errors = []
    for attempt in (1, 2):  # 로컬 소형 모델은 가끔 형식을 어긴다 — 한 번만 재시도
        try:
            result = complete_json(system, user, schema, provider=args.provider, model=args.model,
                                   base_url=args.base_url, response_path=args.response)
        except LLMError as e:
            sys.exit(f"LLM 호출 실패: {e}")
        errors = check_response(result.data, schema, ids)
        replayed = result.provider.startswith("replay")
        if not errors or replayed:
            break
        print(f"  응답 검증 실패({attempt}회차): {errors[:3]}")
    if errors:
        sys.exit(f"LLM 응답이 계약을 어겼다: {errors}")

    if not replayed:  # 재생한 응답은 이미 파일로 있으므로 로그를 다시 쓰지 않는다
        log = RUNS_DIR / f"agent3_{stamp}.json"
        log.write_text(json.dumps({"prompt_version": prompt_version, "provider": result.provider, "model": result.model,
                                   "user": user, "response": result.data}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"실행 로그: {log.relative_to(ROOT)}")

    model_info = {"name": result.model, "provider": result.provider, "prompt_version": prompt_version}
    payload = build_payload(candidates, excluded, result.data, situation, inputs, model_info)
    problems = validate_payload("checklist", payload)
    if problems:
        sys.exit(f"스키마 검증 실패: {problems[:5]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"출력: {args.out.relative_to(ROOT)}{'  (목업 입력 포함)' if payload['_mock'] else ''}\n")

    for st in result.data["situation_types"]:
        print(f"  상황 유형  {st['type']}: {st['evidence']}")
    for oos in result.data["out_of_scope"]:
        print(f"  범위 밖    {oos['issue']}: {oos['evidence']}")
    print()
    for item in payload["data"]["items"]:
        mark = "▶" if item["status"] == "발동" else "…"
        print(f"  {item['rank']:>2} {mark} [{item['relevance']}] {item['id']} p.{item['manual_ref']['page']:<2} {item['action'][:42]}")


if __name__ == "__main__":
    main()
