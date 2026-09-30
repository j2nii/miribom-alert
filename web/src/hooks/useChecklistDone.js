import { useCallback, useEffect, useState } from "react";

// 정책 대응 체크리스트의 "오늘 처리함" 표시를 브라우저에 보관한다.
//
// 날짜를 키에 넣는 이유: checklist envelope에는 as_of가 없고(generated_at/period만 있다),
// 이 목록의 성격 자체가 "오늘 할 일"이다. 날짜가 바뀌면 자동으로 빈 상태에서 시작하는 게
// 맞다 -- 어제 체크한 게 오늘 아침에 그대로 남아 있으면 오히려 착각을 부른다.
//
// AREA0의 오늘의 결론 카드와 AREA3의 체크리스트 패널이 같은 상태를 봐야 하므로, 쓰기가
// 일어나면 custom event로 같은 탭의 구독자 전체에게 알린다(다른 탭은 storage 이벤트).
const PREFIX = "checklistDone";
const SYNC_EVENT = "checklist-done-change";

function todayKey() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function storageKey(region) {
  return `${PREFIX}:${region}:${todayKey()}`;
}

// 지난 날짜의 키가 계속 쌓이지 않게 모듈 로드 시 한 번 치운다.
function pruneOldKeys() {
  try {
    const today = todayKey();
    const stale = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key?.startsWith(`${PREFIX}:`) && !key.endsWith(`:${today}`)) stale.push(key);
    }
    stale.forEach((key) => localStorage.removeItem(key));
  } catch {
    // per-viewer convenience only -- 실패해도 기능에 영향 없음
  }
}
pruneOldKeys();

function readDone(region) {
  try {
    const raw = localStorage.getItem(storageKey(region));
    const parsed = raw ? JSON.parse(raw) : null;
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function writeDone(region, set) {
  try {
    localStorage.setItem(storageKey(region), JSON.stringify([...set]));
  } catch {
    // 사생활 보호 모드 등 -- 저장 실패해도 화면 동작은 유지된다
  }
}

/**
 * @param {string} region
 * @returns {{ done: Set<string>, toggle: (id: string) => void, clear: () => void }}
 */
export function useChecklistDone(region) {
  const [done, setDone] = useState(() => readDone(region));

  useEffect(() => {
    setDone(readDone(region));
  }, [region]);

  useEffect(() => {
    const onSync = (e) => {
      if (!e.detail || e.detail.region === region) setDone(readDone(region));
    };
    const onStorage = (e) => {
      if (e.key === storageKey(region)) setDone(readDone(region));
    };
    window.addEventListener(SYNC_EVENT, onSync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SYNC_EVENT, onSync);
      window.removeEventListener("storage", onStorage);
    };
  }, [region]);

  // 로컬 state가 아니라 저장소를 먼저 읽고 쓴다 -- 두 화면이 동시에 켜져 있어도
  // 각자의 오래된 사본을 덮어쓰지 않는다.
  const mutate = useCallback(
    (fn) => {
      const next = readDone(region);
      fn(next);
      writeDone(region, next);
      window.dispatchEvent(new CustomEvent(SYNC_EVENT, { detail: { region } }));
    },
    [region]
  );

  const toggle = useCallback(
    (id) => mutate((set) => (set.has(id) ? set.delete(id) : set.add(id))),
    [mutate]
  );

  const clear = useCallback(() => mutate((set) => set.clear()), [mutate]);

  return { done, toggle, clear };
}
