"""LLM 호출 백엔드. 에이전트③⑤가 공유한다 (설계결정 D-08).

백엔드 3종 — 호출하는 쪽 코드는 백엔드가 무엇이든 같다.
    anthropic  Anthropic API. 공식 SDK 사용, 기본 모델 claude-opus-5
    openai     OpenAI 호환 서버. vLLM·Ollama·llama.cpp 등 로컬 서빙용 (Claude가 아닌 모델)
    replay     저장해 둔 응답 파일을 그대로 돌려준다. 재현·오프라인 시연용

설정은 인자 > 환경변수(.env) 순으로 읽는다.
    LLM_PROVIDER   anthropic | openai | replay
    LLM_MODEL      모델명. openai 백엔드는 필수 (예: qwen2.5:14b)
    LLM_BASE_URL   openai 백엔드 주소. 기본 http://localhost:11434/v1 (Ollama). vLLM은 보통 :8000/v1
    LLM_API_KEY    openai 백엔드 인증이 필요할 때만
    ANTHROPIC_API_KEY  anthropic 백엔드 (SDK가 직접 읽는다)
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_BASE_URL = "http://localhost:11434/v1"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    data: dict
    raw_text: str
    provider: str
    model: str


def complete_json(
    system: str,
    user: str,
    schema: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    response_path: Path | None = None,
    max_tokens: int = 16000,
) -> LLMResult:
    """system·user 프롬프트를 보내고 schema에 맞는 JSON 객체를 받는다."""
    provider = provider or os.getenv("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        return _anthropic(system, user, schema, model or os.getenv("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL, max_tokens)
    if provider == "openai":
        model = model or os.getenv("LLM_MODEL")
        if not model:
            raise LLMError("openai 백엔드는 모델명이 필요하다 (--model 또는 LLM_MODEL)")
        url = base_url or os.getenv("LLM_BASE_URL") or DEFAULT_OPENAI_BASE_URL
        return _openai_compatible(system, user, schema, model, url, max_tokens)
    if provider == "replay":
        if response_path is None:
            raise LLMError("replay 백엔드는 응답 파일이 필요하다 (--response)")
        return _replay(response_path)
    raise LLMError(f"알 수 없는 백엔드: {provider}")


def _anthropic(system: str, user: str, schema: dict, model: str, max_tokens: int) -> LLMResult:
    import anthropic  # 선택 의존성 — uv sync --extra llm

    client = anthropic.Anthropic()
    try:
        # Opus 5는 temperature를 받지 않는다. 출력 형식은 structured outputs로 강제하고,
        # 안전 분류기가 거절하면 서버가 다른 모델로 재시도하도록 fallbacks를 켠다.
        response = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}, "effort": "high"},
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic 인증 실패 — ANTHROPIC_API_KEY 또는 `ant auth login` 확인") from e
    except TypeError as e:
        # 자격 증명이 전혀 없으면 SDK가 요청 전에 TypeError를 낸다
        if "authentication method" not in str(e):
            raise
        raise LLMError("Anthropic 자격 증명이 없다 — .env에 ANTHROPIC_API_KEY를 넣거나 `ant auth login`") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Anthropic 요청 한도 초과 — 잠시 후 재실행") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API 오류 {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Anthropic API에 연결할 수 없다 — 네트워크 확인") from e

    if response.stop_reason == "refusal":
        raise LLMError(f"모델이 응답을 거절했다: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise LLMError("출력이 max_tokens에서 잘렸다 — 후보 수를 줄이거나 max_tokens를 늘릴 것")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return LLMResult(_parse(text), text, "anthropic", response.model)


def _openai_compatible(system: str, user: str, schema: dict, model: str, base_url: str, max_tokens: int) -> LLMResult:
    import requests

    headers = {}
    if api_key := os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        # vLLM·Ollama 모두 json_schema 형식을 지원한다. 미지원 서버는 무시하므로 _parse에서 한 번 더 방어한다.
        "response_format": {"type": "json_schema", "json_schema": {"name": "output", "schema": schema, "strict": True}},
    }
    try:
        response = requests.post(f"{base_url.rstrip('/')}/chat/completions", json=body, headers=headers, timeout=600)
        response.raise_for_status()
    except requests.ConnectionError as e:
        raise LLMError(f"로컬 LLM 서버({base_url})에 연결할 수 없다 — 서버 실행 여부 확인") from e
    except requests.HTTPError as e:
        raise LLMError(f"로컬 LLM 서버 오류 {response.status_code}: {response.text[:300]}") from e

    choice = response.json()["choices"][0]
    if choice.get("finish_reason") == "length":
        raise LLMError("출력이 max_tokens에서 잘렸다 — 로컬 모델의 컨텍스트 길이 확인")
    text = choice["message"]["content"]
    return LLMResult(_parse(text), text, "openai-compatible", model)


def _replay(path: Path) -> LLMResult:
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    # 실행 로그(agents/runs/*.json)면 response 필드를, 아니면 파일 전체를 응답으로 본다
    data = saved.get("response", saved)
    model = saved.get("model", "replay")
    # 원래 어떤 백엔드로 만든 응답인지 남긴다 (예: replay:anthropic, replay:Claude Code 세션)
    provider = f"replay:{saved['provider']}" if "provider" in saved else "replay"
    return LLMResult(data, json.dumps(data, ensure_ascii=False), provider, model)


def _parse(text: str) -> dict:
    # 로컬 모델은 structured output을 무시하고 ```json 펜스로 감싸는 경우가 있다
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON이 아닌 응답: {text[:200]}") from e
