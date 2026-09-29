import { useEffect, useState } from "react";
import ManualRefCite from "../common/ManualRefCite.jsx";

// 알려진 단계는 운영 순서대로 표시하고, 새 단계는 데이터에 나타난 순서로 덧붙인다.
const PHASE_ORDER = ["사전(예보 대응)", "오전(준비)", "운영 중(모니터링)", "비상 대응", "마감(평가)"];

function storedCompleted(key) {
  try {
    const value = JSON.parse(window.localStorage.getItem(`tourism-radar-checklist:${key}`) ?? "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export default function ChecklistPanel({ checklistData, showDetails = true }) {
  const immediate = checklistData.items
    .filter((item) => item.status === "발동" && ["사전(예보 대응)", "오전(준비)"].includes(item.phase))
    .slice().sort((a, b) => a.rank - b.rank).slice(0, 3);
  const shortActions = {
    "CL-026": "혼잡 시간·동선 분산",
    "CL-046": "안내물·대기공간 준비",
    "CL-047": "주차·퇴장 안내 계획",
  };
  return <div>
    <ol className="policy-now-list">
      {immediate.map((item, index) => <li key={item.id}>
        <span className="policy-now-number">{index + 1}</span>
        <div><strong>{shortActions[item.id] ?? item.action}</strong><p>{item.owner}</p></div>
      </li>)}
    </ol>
    {!immediate.length && <p className="policy-now-note">지금 우선 안내할 사전 준비 항목이 없습니다. 전체 자료를 확인하세요.</p>}
    {showDetails && <details className="compact-details policy-full"><summary>전체 체크리스트·선정 근거</summary><FullChecklist checklistData={checklistData} /></details>}
  </div>;
}

export function FullChecklist({ checklistData, storageKey = checklistData.region?.code ?? "region" }) {
  const { items, excluded_count } = checklistData;
  const [completed, setCompleted] = useState(() => storedCompleted(storageKey));
  useEffect(() => {
    try {
      window.localStorage.setItem(`tourism-radar-checklist:${storageKey}`, JSON.stringify(completed));
    } catch {
      // The checklist remains usable when browser storage is unavailable.
    }
  }, [completed, storageKey]);

  const activeItems = items.filter((item) => item.status === "발동");
  const phases = [...PHASE_ORDER, ...new Set(activeItems.map((item) => item.phase).filter((phase) => !PHASE_ORDER.includes(phase)))];
  const byPhase = phases.map((phase) => ({
    phase,
    items: activeItems.filter((item) => item.phase === phase).sort((a, b) => a.rank - b.rank),
  })).filter((g) => g.items.length > 0);
  const completedCount = activeItems.filter((item) => completed.includes(item.id)).length;
  const toggleCompleted = (id) => setCompleted((current) => current.includes(id)
    ? current.filter((entry) => entry !== id)
    : [...current, id]);

  return (
    <div className="policy-checklist">
      <div className="policy-checklist-progress"><span>선정된 조치 {activeItems.length}건</span><strong>{completedCount}건 완료</strong></div>

      {byPhase.map((group) => {
        return (
          <section className="policy-checklist-phase" key={group.phase}>
            <h4>{group.phase}</h4>
            <ul className="briefing-list">
              {group.items.map((item) => (
                <li key={item.id} className={`briefing-item${completed.includes(item.id) ? " is-complete" : ""}`}>
                  <div className="policy-checklist-item-top">
                    <label className="policy-checklist-action">
                      <input type="checkbox" checked={completed.includes(item.id)} onChange={() => toggleCompleted(item.id)} />
                      <span className="briefing-item-label">{item.action}</span>
                    </label>
                    <span className={`priority-tag priority-${item.priority}`}>{item.priority}</span>
                  </div>
                  <div className="briefing-item-owner">
                    담당: <span className="dept-chip">{item.owner}</span>
                  </div>
                  <ManualRefCite manualRef={item.manual_ref} alwaysVisible />
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      <p className="policy-checklist-excluded">
        매뉴얼 조건 불일치로 제외된 항목 {excluded_count}건
      </p>
    </div>
  );
}
