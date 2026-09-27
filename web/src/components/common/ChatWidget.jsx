import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import SourceBadge from "./SourceBadge.jsx";
import CaveatNote from "./CaveatNote.jsx";
import { normalizeMarkdown } from "../../lib/markdown.js";
import { useMediaQuery, NARROW_QUERY } from "../../hooks/useMediaQuery.js";

const PANEL_WIDTH = 320;
const PANEL_HEIGHT_OPEN = 440;
const TOGGLE_SIZE = 52; // the collapsed toggle is a 52x52 circle (46 on narrow screens)
const TOGGLE_SIZE_NARROW = 46;
const EDGE_MARGIN = 8;
const DRAG_THRESHOLD = 4; // px of pointer movement before a press counts as a drag, not a click
const STORAGE_KEY = "chatWidgetPosition";
const INPUT_MIN_HEIGHT = 56; // ~2 lines, so the placeholder text doesn't scroll on its own
const INPUT_MAX_HEIGHT = 120;
// 모델에게 함께 보내는 최근 대화 맥락의 길이(메시지 개수 = Q&A 10턴). 화면의 말풍선은
// 이 값과 무관하게 계속 남는다 -- 여기서 자르는 건 프롬프트에 실리는 분량뿐이다.
// 답변이 2~4문장 규격이라 20개여도 컨텍스트 부담이 작다. api/query.js에도 같은 상한이 있다.
const MAX_HISTORY_MESSAGES = 20;

// 빈 대화창에 띄우는 예시 질문. 지역 이름은 {지역} 자리에 채워 넣는다. 모든 지역에
// signal_status/checklist가 있으므로 어느 지역에서 눌러도 근거 있는 답이 나온다.
const SUGGESTIONS = [
  "지금 {지역} 상황 어때?",
  "오늘 뭘 먼저 해야 해?",
  "어디가 제일 붐벼?",
];

// 출처 칩에 쓰는 데이터 계약별 한글 이름 (api/query.js의 TOOLS와 같은 dataType 키).
const DATA_LABELS = {
  signal_status: "신호 상태",
  forecast: "7일 예측",
  visitor_profile: "방문객 프로파일",
  hotspots: "인기 관광지",
  content_type: "콘텐츠 유형",
  checklist: "체크리스트",
  precedent: "선례",
  before_after: "조치 전후",
  timeline: "타임라인",
};

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

  const leftRoom = bounds.left - MARGIN_GAP - EDGE_MARGIN;
  const rightRoom = safeRight - bounds.right - MARGIN_GAP - EDGE_MARGIN;

  // 좁은 화면에서는 .app-grid가 폭을 거의 다 써서 "본문 밖 여백"이 존재하지 않는다.
  // 이때 예전 코드는 maxX가 EDGE_MARGIN으로 떨어져 아이콘을 좌하단 *본문 위에* 박아버렸고,
  // 그게 QA에서 나온 "플로팅 아이콘이 정책 브리핑 텍스트를 가림"의 원인이다. 양쪽 모두
  // 아이콘이 들어갈 여백이 없으면 플로팅 버튼의 관례 위치인 오른쪽 아래 코너로 보낸다
  // (본문 마지막 줄은 .app의 모바일 padding-bottom으로 피한다).
  if (leftRoom < width && rightRoom < width) return safeRight - width - EDGE_MARGIN;

  const onLeft = x + width / 2 < window.innerWidth / 2;
  if (onLeft && leftRoom >= width) {
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

// 플로팅 전환은 항상 "접힌 아이콘" 상태로 시작하므로, 기본 위치도 패널 크기가 아니라
// 아이콘 크기 기준 오른쪽 아래 코너로 잡는다. 패널 크기로 계산하면(예전 동작) 세로가
// 짧은 휴대폰에서 아이콘이 화면 중간 본문 위에 떠버린다.
function defaultTogglePosition(size) {
  return {
    x: Math.max(EDGE_MARGIN, safeViewportWidth() - size - EDGE_MARGIN - 4),
    y: Math.max(EDGE_MARGIN, window.innerHeight - size - 20),
  };
}

// 답변 말풍선에 붙는 출처 칩 한 줄. 화면 다른 곳(SourceBadge)과 같은 실측/샘플 언어를
// 쓰고, 조회했지만 파일이 없는 데이터(영월의 forecast 등)도 "준비 전"으로 남긴다 --
// 답변이 어떤 근거 위에 서 있는지 공무원이 매번 확인할 수 있어야 한다.
function ChatSources({ results, envelopes }) {
  if (!results || results.length === 0) return null;
  const detailed = Object.entries(envelopes ?? {});

  return (
    <div className="chat-message__sources">
      <div className="chat-source-chips">
        {results.map((r) => {
          const envelope = envelopes?.[r.dataType];
          const [tone, label] =
            r.status === "unsupported"
              ? ["none", "준비 전"]
              : r.status === "error"
                ? ["none", "조회 실패"]
                : envelope?._mock
                  ? ["sample", "샘플"]
                  : ["real", "실측"];
          return (
            <span key={r.dataType} className={`chat-source-chip chat-source-chip--${tone}`}>
              {DATA_LABELS[r.dataType] ?? r.dataType} <b>{label}</b>
            </span>
          );
        })}
      </div>
      {detailed.length > 0 && (
        <details className="chat-source-detail">
          <summary>출처·주의 상세</summary>
          {detailed.map(([dataType, envelope]) => (
            <div key={dataType} className="chat-source-detail__item">
              <p className="chat-source-detail__name">{DATA_LABELS[dataType] ?? dataType}</p>
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

// AREA0 관제 대시보드에 임베드된 자연어 질의 위젯. `boundaryRef`가 가리키는
// 영역(AREA0의 2단 레이아웃 전체 -- 채팅 칸 자기 자신이 아니라)이 화면에 조금이라도
// 보이는 동안은 계속 docked(2단 배치) 상태를 유지하고, 그 영역이 뷰포트에서
// 완전히 벗어나야만 floating 모드로 전환된다 -- AREA0를 절반만 내렸다고 바로
// 1단으로 무너지지 않게 하기 위함. floating일 때만 드래그로 위치를 옮길 수 있고,
// 접으면 토글 버튼만 남는다.
// `sheetOpen`/`onSheetClose`: 좁은 화면 전용. 모바일에서는 떠다니는 아이콘(FAB)을 아예 쓰지
// 않는다 -- 390px 폭에서는 본문이 화면을 거의 다 채워서 아이콘을 어디에 두든 글자 위에
// 얹히기 때문이다(QA #14-3. 좌하단→우하단으로 옮긴 것만으로는 해결되지 않았다). 대신
// 상단 고정 내비의 "물어보기" 버튼이 이 대화창을 하단 시트로 띄운다. 데스크톱은 아이콘이
// .app-grid 바깥 여백에 있어 본문과 겹치지 않으므로 기존 동작 그대로 둔다.
export default function ChatWidget({ region, regionLabel, boundaryRef, maxHeight, sheetOpen, onSheetClose }) {
  const [floating, setFloating] = useState(false);
  const [open, setOpen] = useState(true);
  const [position, setPosition] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const dragRef = useRef({ dragging: false, offsetX: 0, offsetY: 0 });
  const textareaRef = useRef(null);
  const messagesRef = useRef(null);
  const abortRef = useRef(null);
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const toggleSize = isNarrow ? TOGGLE_SIZE_NARROW : TOGGLE_SIZE;

  // 지역이 바뀌면 대화창과 이력을 즉시 비운다. 이게 없으면 거제에서 나눈 대화가
  // 영월 질의의 프롬프트에 그대로 실려, 영월에는 없는 forecast 수치와 거제 지명을
  // 지어내는 답이 나왔다(QA 재현 버그). 진행 중인 요청도 끊어서, 전환 직전에 보낸
  // 질의의 스트림이 새 지역 대화창에 뒤늦게 꽂히지 않게 한다.
  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setInput("");
    setLoading(false);
  }, [region]);

  // 언마운트 시에도 진행 중 스트림을 정리한다.
  useEffect(() => () => abortRef.current?.abort(), []);

  // 하단 시트는 모달처럼 동작한다 -- Esc로 닫는다.
  useEffect(() => {
    if (!(isNarrow && sheetOpen)) return;
    const onKey = (e) => e.key === "Escape" && onSheetClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isNarrow, sheetOpen, onSheetClose]);

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
          setPosition((prev) => prev ?? loadStoredPosition() ?? defaultTogglePosition(toggleSize));
        }
      },
      { threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [boundaryRef, toggleSize]);

  function ensurePosition() {
    if (position) return position;
    const stored = loadStoredPosition();
    const next = stored ?? defaultTogglePosition(toggleSize);
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
        x: clampToMargin(rawX, toggleSize),
        y: clamp(rawY, EDGE_MARGIN, window.innerHeight - toggleSize - EDGE_MARGIN),
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
      // 지역 전환으로 대화가 비워진 뒤 도착한 늦은 콜백은 무시한다 -- 없으면 빈 배열의
      // [-1]에 쓰는 셈이 된다.
      if (prev.length === 0) return prev;
      const next = [...prev];
      const i = next.length - 1;
      next[i] = { ...next[i], ...(typeof patch === "function" ? patch(next[i]) : patch) };
      return next;
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    submitQuestion(input.trim());
  }

  async function submitQuestion(question) {
    if (!question || loading) return;

    // 각 이력 항목에 지역을 함께 실어 보낸다 -- 서버(api/query.js)가 현재 조회 지역과
    // 다른 지역의 이력을 버리는 2차 방어선의 입력이다.
    const history = messages
      .slice(-MAX_HISTORY_MESSAGES)
      .map((m) => ({ role: m.role, content: m.content, region: m.region ?? region }));
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question, region },
      { role: "assistant", content: "", streaming: true, region },
    ]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region, regionLabel, question, history }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.error ?? `HTTP ${res.status}`);
      }

      // Server streams newline-delimited JSON: {type:"token",text} while
      // the answer is being written, then one {type:"done", results,
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
            patchLastMessage({
              // 구버전 서버(results 없음)와도 호환되게 usedDataTypes에서 되살린다.
              results:
                evt.results ??
                evt.usedDataTypes?.map((dataType) => ({
                  dataType,
                  status: evt.envelopes?.[dataType] ? "ok" : "unsupported",
                })),
              envelopes: evt.envelopes,
              streaming: false,
            });
          } else if (evt.type === "error") {
            serverError = evt.error;
          }
        }
      }

      if (serverError) throw new Error(serverError);
    } catch (err) {
      // 지역 전환/언마운트로 우리가 끊은 요청은 에러가 아니다 -- 대화창은 이미 비워졌다.
      if (err.name !== "AbortError") {
        patchLastMessage({
          content: `지금은 답변할 수 없습니다 (${err.message}). 잠시 후 다시 시도해주세요.`,
          isError: true,
          streaming: false,
        });
      }
    } finally {
      // 지역 전환으로 이 요청이 이미 폐기됐다면(abortRef가 다른 컨트롤러이거나 null)
      // 새 지역의 로딩 상태를 건드리지 않는다.
      if (abortRef.current === controller) {
        abortRef.current = null;
        patchLastMessage((m) => (m.streaming ? { streaming: false } : {}));
        setLoading(false);
      }
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
  const openPosition = floating && !isNarrow && position ? clampToViewport(position, PANEL_WIDTH, PANEL_HEIGHT_OPEN) : null;
  // 좁은 화면에서 "물어보기"로 띄운 하단 시트. 위치/크기는 CSS가 잡으므로 인라인 좌표를 주지 않는다.
  const asSheet = isNarrow && sheetOpen;
  const panelStyle = openPosition
    ? { position: "fixed", left: openPosition.x, top: openPosition.y, width: PANEL_WIDTH }
    : !floating && !asSheet && maxHeight
      ? { height: maxHeight, maxHeight }
      : undefined;
  const panelClass = `chat-widget ${asSheet ? "chat-widget--sheet" : floating ? "chat-widget--floating" : "chat-widget--docked"}`;
  const draggable = floating && !isNarrow;

  // 좁은 화면에서 AREA0가 화면 밖으로 나갔는데 시트도 닫혀 있으면 대화창은 아무 데도
  // 그리지 않는다 -- 예전의 떠다니는 아이콘이 있던 자리다.
  if (isNarrow && floating && !sheetOpen) return null;

  return (
    <div className={`chat-widget-slot${floating && !asSheet ? " chat-widget-slot--floating" : ""}${asSheet ? " chat-widget-slot--sheet" : ""}`}>
      {asSheet && <div className="chat-widget__scrim" onClick={onSheetClose} />}
      {floating && !isNarrow && !open ? (
        <button
          className="chat-widget__toggle"
          style={
            position
              ? { position: "fixed", left: clampToMargin(position.x, toggleSize), top: position.y }
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
            onPointerDown={draggable ? handlePointerDown : undefined}
            onPointerMove={draggable ? handlePointerMove : undefined}
            onPointerUp={draggable ? handlePointerUp : undefined}
          >
            <p className="section-title" style={{ margin: 0 }}>
              지역 상황 물어보기
            </p>
            {/* 답변의 기준 지역을 대화창 안에서도 못 놓치게 한다 -- 지역 전환 시 대화가
                리셋되는 동작과 짝이 되는 표시. */}
            <span className="chat-widget__region">{regionLabel ?? region}</span>
            {asSheet ? (
              <button type="button" className="chat-widget__collapse" onClick={onSheetClose}>
                닫기
              </button>
            ) : (
              draggable && (
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
              )
            )}
          </div>

          <div className="chat-widget__messages" ref={messagesRef}>
            {messages.length === 0 && (
              <>
                <p className="chat-widget__hint">
                  {regionLabel ?? region} 데이터만 근거로 답합니다. 지역을 바꾸면 대화가 새로 시작됩니다.
                </p>
                {/* 빈 입력창 앞에서 "무엇을 물어봐도 되는지" 모르는 게 첫 사용자의 가장 큰 벽이다.
                    눌러서 바로 보내지는 예시를 준다. */}
                <div className="chat-widget__suggestions">
                  {SUGGESTIONS.map((q) => {
                    const text = q.replace("{지역}", regionLabel ?? region);
                    return (
                      <button
                        key={q}
                        type="button"
                        className="chat-suggestion"
                        onClick={() => submitQuestion(text)}
                        disabled={loading}
                      >
                        {text}
                      </button>
                    );
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
                    // normalizeMarkdown: 한글 뒤에 조사가 붙는 **강조**가 별표째로
                    // 노출되던 문제를 렌더 전에 정리한다 (lib/markdown.js).
                    <ReactMarkdown>{normalizeMarkdown(m.content)}</ReactMarkdown>
                  ) : (
                    <p>{m.content}</p>
                  )}
                  <ChatSources results={m.results} envelopes={m.envelopes} />
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
