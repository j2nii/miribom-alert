import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import SourceBadge from "./SourceBadge.jsx";
import CaveatNote from "./CaveatNote.jsx";

const PANEL_WIDTH = 320;
const PANEL_HEIGHT_OPEN = 440;
const PANEL_HEIGHT_COLLAPSED = 52; // also the collapsed toggle's width -- it's a 52x52 circle
const EDGE_MARGIN = 8;
const DRAG_THRESHOLD = 4; // px of pointer movement before a press counts as a drag, not a click
const STORAGE_KEY = "chatWidgetPosition";
const INPUT_MIN_HEIGHT = 56; // ~2 lines, so the placeholder text doesn't scroll on its own
const INPUT_MAX_HEIGHT = 120;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

// window.innerWidth includes the vertical scrollbar's own width, so a
// button positioned flush against it ends up rendered *under* the
// scrollbar. document.documentElement.clientWidth excludes it.
function safeViewportWidth() {
  return document.documentElement.clientWidth;
}

// Left/right edges of the centered page content (.app-grid in App.jsx) --
// the empty space outside of this on either side is the "margin" the
// collapsed icon is allowed to roam in. Queried directly rather than
// threaded down as another ref/prop; .app-grid is a stable, single element.
function getContentBounds() {
  const el = document.querySelector(".app-grid");
  return el ? el.getBoundingClientRect() : null;
}

// Collapsed (icon-only) mode is free to move anywhere within whichever side
// margin it's currently in (not pinned to one exact pixel), but must never
// sit on top of page content or get clipped by the scrollbar. The open
// panel has no such restriction -- clampToViewport below just keeps *it*
// fully on screen, wherever that is.
const MARGIN_GAP = 12;
function clampToMargin(x, width) {
  const safeRight = safeViewportWidth();
  const bounds = getContentBounds();
  if (!bounds) return clamp(x, EDGE_MARGIN, safeRight - width - EDGE_MARGIN);

  const onLeft = x + width / 2 < window.innerWidth / 2;
  if (onLeft) {
    const maxX = Math.max(EDGE_MARGIN, bounds.left - MARGIN_GAP - width);
    return clamp(x, EDGE_MARGIN, maxX);
  }
  const minX = Math.min(safeRight - width - EDGE_MARGIN, bounds.right + MARGIN_GAP);
  return clamp(x, minX, safeRight - width - EDGE_MARGIN);
}

function clampToViewport(pos, width, height) {
  return {
    x: clamp(pos.x, EDGE_MARGIN, safeViewportWidth() - width - EDGE_MARGIN),
    y: clamp(pos.y, EDGE_MARGIN, window.innerHeight - height - EDGE_MARGIN),
  };
}

function loadStoredPosition() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveStoredPosition(pos) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pos));
  } catch {
    // per-viewer convenience only -- ignore write failures (private mode, etc.)
  }
}

function defaultPosition() {
  return clampToViewport(
    { x: safeViewportWidth() - PANEL_WIDTH - 20, y: window.innerHeight - PANEL_HEIGHT_OPEN - 20 },
    PANEL_WIDTH,
    PANEL_HEIGHT_OPEN
  );
}


// AREA0 관제 대시보드에 임베드된 자연어 질의 위젯. `boundaryRef`가 가리키는
// 영역(AREA0의 2단 레이아웃 전체 -- 채팅 칸 자기 자신이 아니라)이 화면에 조금이라도
// 보이는 동안은 계속 docked(2단 배치) 상태를 유지하고, 그 영역이 뷰포트에서
// 완전히 벗어나야만 floating 모드로 전환된다 -- AREA0를 절반만 내렸다고 바로
// 1단으로 무너지지 않게 하기 위함. floating일 때만 드래그로 위치를 옮길 수 있고,
// 접으면 토글 버튼만 남는다.
export default function ChatWidget({ region, regionLabel, boundaryRef, maxHeight }) {
  const [floating, setFloating] = useState(false);
  const [open, setOpen] = useState(true);
  const [position, setPosition] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const dragRef = useRef({ dragging: false, offsetX: 0, offsetY: 0 });
  const textareaRef = useRef(null);
  const messagesRef = useRef(null);

  // Grows the textarea up to INPUT_MAX_HEIGHT as the question gets longer,
  // then leaves it fixed and lets its own scrollbar take over.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${clamp(el.scrollHeight, INPUT_MIN_HEIGHT, INPUT_MAX_HEIGHT)}px`;
  }, [input]);

  // Keeps the latest message in view while tokens are streaming in.
  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const el = boundaryRef?.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        const nowFloating = !entry.isIntersecting;
        setFloating(nowFloating);
        setOpen(!nowFloating);
        // Position starts out unset (null) -- without initializing it here,
        // the very first time the widget floats it renders with no
        // `position: fixed` style at all (see panelStyle/toggle style below),
        // so it stays wherever it was in the flow instead of appearing on
        // screen. Only set it if nothing's been picked (stored or dragged)
        // yet.
        if (nowFloating) {
          setPosition((prev) => prev ?? loadStoredPosition() ?? defaultPosition());
        }
      },
      { threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [boundaryRef]);

  function ensurePosition() {
    if (position) return position;
    const stored = loadStoredPosition();
    const next = stored ?? defaultPosition();
    setPosition(next);
    return next;
  }

  function handleToggle() {
    ensurePosition();
    setOpen((v) => !v);
  }

  // The toggle button is both clickable (open) and draggable (move) --
  // pointerdown/up around a drag still fires a native click afterward, so
  // without this every drag would also toggle the panel open. Track whether
  // the pointer actually moved past a small threshold; the click handler
  // below checks it and swallows the click if so.
  function handleToggleClick() {
    if (dragRef.current.moved) {
      dragRef.current.moved = false;
      return;
    }
    handleToggle();
  }

  function handlePointerDown(e) {
    const pos = ensurePosition();
    dragRef.current = {
      dragging: true,
      moved: false,
      startX: e.clientX,
      startY: e.clientY,
      offsetX: e.clientX - pos.x,
      offsetY: e.clientY - pos.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e) {
    if (!dragRef.current.dragging) return;
    if (Math.abs(e.clientX - dragRef.current.startX) > DRAG_THRESHOLD || Math.abs(e.clientY - dragRef.current.startY) > DRAG_THRESHOLD) {
      dragRef.current.moved = true;
    }
    const rawX = e.clientX - dragRef.current.offsetX;
    const rawY = e.clientY - dragRef.current.offsetY;
    if (open) {
      setPosition(clampToViewport({ x: rawX, y: rawY }, PANEL_WIDTH, PANEL_HEIGHT_OPEN));
    } else {
      setPosition({
        x: clampToMargin(rawX, PANEL_HEIGHT_COLLAPSED),
        y: clamp(rawY, EDGE_MARGIN, window.innerHeight - PANEL_HEIGHT_COLLAPSED - EDGE_MARGIN),
      });
    }
  }

  function handlePointerUp(e) {
    if (!dragRef.current.dragging) return;
    dragRef.current.dragging = false;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // pointer may already be released -- harmless
    }
    if (position) saveStoredPosition(position);
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

  async function handleSubmit(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    const history = messages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }, { role: "assistant", content: "", streaming: true }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/query", {
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  // Re-clamped to the viewport on every render (not just while dragging) --
  // `position` can come from a stale localStorage value, or from wherever
  // the collapsed icon happened to be sitting, so it isn't necessarily a
  // valid *panel*-sized position. Without this, opening the panel from an
  // icon parked near the right margin rendered it partly off-screen.
  const openPosition = floating && position ? clampToViewport(position, PANEL_WIDTH, PANEL_HEIGHT_OPEN) : null;
  const panelStyle = openPosition
    ? { position: "fixed", left: openPosition.x, top: openPosition.y, width: PANEL_WIDTH }
    : !floating && maxHeight
      ? { height: maxHeight, maxHeight }
      : undefined;
  const panelClass = `chat-widget ${floating ? "chat-widget--floating" : "chat-widget--docked"}`;

  return (
    <div className={`chat-widget-slot${floating ? " chat-widget-slot--floating" : ""}`}>
      {floating && !open ? (
        <button
          className="chat-widget__toggle"
          style={
            position
              ? { position: "fixed", left: clampToMargin(position.x, PANEL_HEIGHT_COLLAPSED), top: position.y }
              : undefined
          }
          onClick={handleToggleClick}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          title="지역 상황 물어보기"
        >
          💬
        </button>
      ) : (
        <div className={panelClass} style={panelStyle}>
          <div
            className="chat-widget__header"
            onPointerDown={floating ? handlePointerDown : undefined}
            onPointerMove={floating ? handlePointerMove : undefined}
            onPointerUp={floating ? handlePointerUp : undefined}
          >
            <p className="section-title" style={{ margin: 0 }}>
              지역 상황 물어보기
            </p>
            {floating && (
              // stopPropagation so this click doesn't also bubble into the
              // header's onPointerDown drag handler above -- without it, a
              // plain click on this button also starts a (zero-distance)
              // drag on the header first, which captures the pointer and
              // eats the click until you press again.
              <button
                type="button"
                className="chat-widget__collapse"
                onPointerDown={(e) => e.stopPropagation()}
                onClick={handleToggle}
              >
                접기
              </button>
            )}
          </div>

          <div className="chat-widget__messages" ref={messagesRef}>
            {messages.length === 0 && (
              <p className="chat-widget__hint">
                예: "지금 {regionLabel ?? region} 상황 어때?", "이번 주말 방문객 얼마나 예상돼?"
              </p>
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
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  ) : (
                    <p>{m.content}</p>
                  )}
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
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="지역 상황을 물어보세요 (Shift+Enter로 줄바꿈)"
              rows={1}
              disabled={loading}
            />
            <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
              전송
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
