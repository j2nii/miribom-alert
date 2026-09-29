import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import SourceBadge from "./SourceBadge.jsx";
import CaveatNote from "./CaveatNote.jsx";
import { normalizeMarkdown } from "../../lib/markdown.js";

const INPUT_MIN_HEIGHT = 56;
// 프롬프트에 실리는 분량만 자른다. 화면의 대화는 이 값과 무관하게 남는다.
// web/api/query.js에도 같은 이름의 상한이 있다 -- 두 값을 따로 두면 서버가
// 자른 뒤 클라이언트가 또 잘라 맥락이 조용히 짧아진다.
const MAX_HISTORY_MESSAGES = 20;

// 빈 대화창에서 무엇을 물어야 할지 모르는 담당자를 위한 시작점. 모든 지역에
// signal_status와 checklist가 있어 어느 지역에서 눌러도 근거 있는 답이 나온다.
const SUGGESTIONS = ["지금 {지역} 상황 어때?", "오늘 뭘 먼저 해야 해?", "어디가 제일 붐벼?"];

// 출처 칩에 쓰는 데이터 계약별 한글 이름 (api/query.js의 TOOLS와 같은 dataType 키).
const DATA_LABELS = {
  signal_status: "신호 상태",
  forecast: "7일 예측",
  outlook: "6개월 전망",
  visitor_profile: "방문객 프로파일",
  hotspots: "인기 관광지",
  content_type: "콘텐츠 유형",
  checklist: "체크리스트",
  precedent: "선례",
  before_after: "조치 전후",
  timeline: "타임라인",
};

// 답이 무엇을 근거로 섰는지 한 줄로 보여 준다. 조회했지만 파일이 없는 계약도
// "준비 전"으로 남긴다 -- 답이 비어 있는 이유를 매번 확인할 수 있어야 한다.
function SourceChips({ results, envelopes }) {
  if (!results?.length) return null;
  return (
    <div className="chat-popup-sources">
      {results.map((result) => {
        const envelope = envelopes?.[result.dataType];
        const [tone, label] =
          result.status === "unsupported" ? ["none", "준비 전"]
          : result.status === "error" ? ["none", "조회 실패"]
          : envelope?._mock ? ["sample", "샘플"]
          : ["real", "실측"];
        return (
          <span key={result.dataType} className={`chat-popup-source-chip is-${tone}`}>
            {DATA_LABELS[result.dataType] ?? result.dataType} <b>{label}</b>
          </span>
        );
      })}
    </div>
  );
}
const INPUT_MAX_HEIGHT = 120;

export default function ChatWidget({ region, regionLabel }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef(null);
  const messagesRef = useRef(null);
  const launcherRef = useRef(null);
  const requestRef = useRef(null);

  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    if (open) textareaRef.current?.focus();
  }, [open]);
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, INPUT_MIN_HEIGHT), INPUT_MAX_HEIGHT)}px`;
  }, [input, open]);
  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, open]);
  function closeChat() {
    setOpen(false);
    launcherRef.current?.focus();
  }

  // Applies a partial update to the assistant message that's currently
  // streaming (always the last message in the list once it's been added).
  function patchLastMessage(patch) {
    setMessages((prev) => {
      const next = [...prev];
      const i = next.length - 1;
      next[i] = { ...next[i], ...(typeof patch === "function" ? patch(next[i]) : patch) };
      return next;
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    return ask(input.trim());
  }

  // 예시 질문 칩은 입력창을 거치지 않고 바로 보낸다.
  async function ask(question) {
    if (!question || loading) return;

    const history = messages.slice(-MAX_HISTORY_MESSAGES).map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }, { role: "assistant", content: "", streaming: true }]);
    setInput("");
    setLoading(true);

    try {
      requestRef.current = new AbortController();
      const res = await fetch("/api/query", {
        signal: requestRef.current.signal,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region, regionLabel, question, history }),
      });

      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.error ?? `HTTP ${res.status}`);
      }

      // Server streams newline-delimited JSON: {type:"token",text} while
      // the answer is being written, then one {type:"done", usedDataTypes,
      // envelopes} (or {type:"error"}) at the end. See web/api/query.js.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let serverError = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const evt = JSON.parse(line);
          if (evt.type === "token") {
            patchLastMessage((m) => ({ content: m.content + evt.text }));
          } else if (evt.type === "done") {
            patchLastMessage({ usedDataTypes: evt.usedDataTypes, envelopes: evt.envelopes, streaming: false });
          } else if (evt.type === "error") {
            serverError = evt.error;
          }
        }
      }

      if (serverError) throw new Error(serverError);
    } catch (err) {
      if (err.name === "AbortError") return;
      patchLastMessage({
        content: `지금은 답변할 수 없습니다 (${err.message}). 잠시 후 다시 시도해주세요.`,
        isError: true,
        streaming: false,
      });
    } finally {
      patchLastMessage((m) => (m.streaming ? { streaming: false } : {}));
      setLoading(false);
    }
  }

  function handleInputKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <div className="chat-popup-root">
      <button type="button" ref={launcherRef} className="chat-popup-launcher"
        aria-label="관광신호 도우미 열기" aria-expanded={open} aria-controls="regional-chat-popup"
        onClick={() => open ? closeChat() : setOpen(true)}>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 0 1 18 0Z"/><path d="M7 10h8M7 14h5"/></svg>
        <span>관광신호 도우미</span>
      </button>
      {open && (
        <section id="regional-chat-popup" className="chat-widget chat-popup-panel" role="dialog" aria-modal="false" aria-labelledby="regional-chat-title"
          onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeChat(); } }}>
          <div className="chat-widget__header chat-popup-header">
            <div><strong id="regional-chat-title">관광신호 도우미 · {regionLabel ?? region}</strong><p>우리 지역의 신호와 대응 정보를 쉽게 설명해 드려요.</p></div>
            <button type="button" className="chat-popup-close" onClick={closeChat} aria-label="관광신호 도우미 닫기">×</button>
          </div>
          <div className="chat-widget__messages" ref={messagesRef}>
            {messages.length === 0 && (
              <>
                <p className="chat-widget__hint">
                  “{regionLabel ?? region}에서 먼저 확인할 변화는?”처럼 질문해 보세요.
                </p>
                <div className="chat-popup-suggestions">
                  {SUGGESTIONS.map((template) => {
                    const question = template.replace("{지역}", regionLabel ?? region);
                    return <button key={template} type="button" onClick={() => ask(question)} disabled={loading}>{question}</button>;
                  })}
                </div>
              </>
            )}
            {messages.map((m, i) => {
              const isPendingFirstToken = m.streaming && !m.content;
              return (
                <div
                  key={i}
                  className={`chat-message chat-message--${m.role}${m.isError ? " chat-message--error" : ""}${isPendingFirstToken ? " chat-message--loading" : ""}`}
                >
                  {isPendingFirstToken ? (
                    <p>답변 준비 중…</p>
                  ) : m.role === "assistant" ? (
                    <ReactMarkdown>{normalizeMarkdown(m.content)}</ReactMarkdown>
                  ) : (
                    <p>{m.content}</p>
                  )}
                  <SourceChips results={m.usedDataTypes} envelopes={m.envelopes} />
                  {m.envelopes &&
                    Object.entries(m.envelopes).map(([dataType, envelope]) => (
                      <div key={dataType} className="chat-message__source">
                        <SourceBadge envelope={envelope} />
                        <CaveatNote envelope={envelope} />
                      </div>
                    ))}
                </div>
              );
            })}
          </div>

          <form className="chat-widget__input-row" onSubmit={handleSubmit}>
            <textarea
              aria-label="관광신호 도우미 질문"
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="궁금한 신호나 대응 방법을 물어보세요"
              rows={1}
              disabled={loading}
            />
            <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
              전송
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
