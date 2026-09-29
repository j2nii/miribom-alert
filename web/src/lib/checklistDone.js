// 체크리스트 완료 상태의 단일 저장소. AREA0 "오늘의 결론"과 정책 보고서의 전체
// 체크리스트가 같은 키를 읽고 쓴다 -- 저장소를 둘로 나누면 한쪽에서 체크한 것이
// 다른 쪽에 보이지 않는다.
export const CHECKLIST_DONE_EVENT = "tourism-radar:checklist-done";

export function checklistStorageKey(region, periodEnd) {
  return `${region}-${periodEnd ?? "latest"}`;
}

export function readChecklistDone(storageKey) {
  try {
    const value = JSON.parse(window.localStorage.getItem(`tourism-radar-checklist:${storageKey}`) ?? "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export function writeChecklistDone(storageKey, ids) {
  try {
    window.localStorage.setItem(`tourism-radar-checklist:${storageKey}`, JSON.stringify(ids));
    // storage 이벤트는 다른 탭에만 간다. 같은 탭의 다른 패널에도 알려야 한다.
    window.dispatchEvent(new CustomEvent(CHECKLIST_DONE_EVENT, { detail: { storageKey } }));
  } catch {
    // 저장이 막힌 환경에서도 체크는 계속 쓸 수 있어야 한다.
  }
}
