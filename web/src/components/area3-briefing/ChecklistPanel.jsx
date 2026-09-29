import { useEffect, useState } from "react";
import ManualRefCite from "../common/ManualRefCite.jsx";
import { readChecklistDone, writeChecklistDone } from "../../lib/checklistDone.js";

// 알려진 단계는 운영 순서대로 표시하고, 새 단계는 데이터에 나타난 순서로 덧붙인다.
const PHASE_ORDER = ["사전(예보 대응)", "오전(준비)", "운영 중(모니터링)", "비상 대응", "마감(평가)"];
// 구간당 먼저 보여 줄 건수. 나머지는 "더보기"로 편다 -- 영월은 한 구간이 9건까지 간다.
const PAGE_SIZE = 5;

// 이 지역이 어떤 조건에 걸려 이 목록이 뽑혔는지. checklist.matched_for를 읽는 코드가
// 지금까지 화면에 하나도 없었다.
function MatchedFor({ matchedFor }) {
  if (!matchedFor) return null;
  const parts = [
    matchedFor.alert_level && `경보 ${matchedFor.alert_level}`,
    `혼잡도 ${matchedFor.congestion_level ?? "미측정"}`,
    matchedFor.spatial_type,
    matchedFor.content_type,
    matchedFor.profile_tags?.length ? matchedFor.profile_tags.join(", ") : null,
  ].filter(Boolean);
  return <p className="info-box policy-checklist-matched">이 조건으로 매칭됨 — {parts.join(" · ")}</p>;
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

function ChecklistRow({ item, checked, onToggle }) {
  return (
    <li className={`briefing-item${checked ? " is-complete" : ""}`}>
      <div className="policy-checklist-item-top">
        <label className="policy-checklist-action">
          <input type="checkbox" checked={checked} onChange={() => onToggle(item.id)} />
          <span className="briefing-item-label">{item.action}</span>
        </label>
        <span className={`priority-tag priority-${item.priority}`}>{item.priority}</span>
      </div>
      <div className="briefing-item-owner">
        담당: <span className="dept-chip">{item.owner}</span>
      </div>
      {/* 왜 이 조치가 뽑혔는지. 데이터에 있는데 전체 체크리스트에서는 보여 준 적이 없다. */}
      {item.match_reason && <p className="policy-checklist-reason">{item.match_reason}</p>}
      <ManualRefCite manualRef={item.manual_ref} alwaysVisible />
    </li>
  );
}

export function FullChecklist({ checklistData, storageKey = checklistData.region?.code ?? "region" }) {
  const { items, excluded_count } = checklistData;
  const [completed, setCompleted] = useState(() => readChecklistDone(storageKey));
  // AREA0 "오늘의 결론"이 같은 키를 읽는다. 저장과 함께 같은 탭에도 알린다.
  useEffect(() => {
    writeChecklistDone(storageKey, completed);
  }, [completed, storageKey]);

  const [expanded, setExpanded] = useState({});
  const activeItems = items.filter((item) => item.status === "발동");
  // 조건을 아직 만족하지 않은 조치. 지금까지는 아예 렌더하지 않아 "왜 이것만 나오지?"에
  // 답할 수가 없었다. 구간 끝에 접어 둔다.
  const waitingItems = items.filter((item) => item.status === "대기");
  const byRank = (a, b) => a.rank - b.rank;
  const phases = [...PHASE_ORDER, ...new Set([...activeItems, ...waitingItems].map((item) => item.phase).filter((phase) => !PHASE_ORDER.includes(phase)))];
  const byPhase = phases.map((phase) => ({
    phase,
    items: activeItems.filter((item) => item.phase === phase).sort(byRank),
    waiting: waitingItems.filter((item) => item.phase === phase).sort(byRank),
  })).filter((g) => g.items.length > 0 || g.waiting.length > 0);
  const completedCount = activeItems.filter((item) => completed.includes(item.id)).length;
  const progress = activeItems.length ? Math.round((completedCount / activeItems.length) * 100) : 0;
  const toggleCompleted = (id) => setCompleted((current) => current.includes(id)
    ? current.filter((entry) => entry !== id)
    : [...current, id]);

  return (
    <div className="policy-checklist">
      <div className="policy-checklist-progress">
        <span>선정된 조치 {activeItems.length}건</span>
        <strong>{completedCount}건 완료 · {progress}%</strong>
        <span className="policy-checklist-progress__bar"><span className="policy-checklist-progress__fill" style={{ width: `${progress}%` }} /></span>
        <span className="policy-checklist-progress__note">체크 상태는 이 브라우저에만 저장됩니다.</span>
      </div>
      <MatchedFor matchedFor={checklistData.matched_for} />

      {byPhase.map((group) => {
        const showAll = expanded[group.phase];
        const visible = showAll ? group.items : group.items.slice(0, PAGE_SIZE);
        const groupDone = group.items.filter((item) => completed.includes(item.id)).length;
        return (
          <section className="policy-checklist-phase" key={group.phase}>
            <h4>{group.phase}{group.items.length > 0 && <small>{groupDone}/{group.items.length}</small>}</h4>
            <ul className="briefing-list">
              {visible.map((item) => (
                <ChecklistRow key={item.id} item={item} checked={completed.includes(item.id)} onToggle={toggleCompleted} />
              ))}
            </ul>
            {group.items.length > PAGE_SIZE && (
              <button type="button" className="footer-link-btn" aria-expanded={Boolean(showAll)}
                onClick={() => setExpanded((current) => ({ ...current, [group.phase]: !showAll }))}>
                {showAll ? "접기" : `더보기 (${group.items.length - PAGE_SIZE}건)`}
              </button>
            )}
            {group.waiting.length > 0 && (
              <details className="compact-details">
                <summary>지금은 해당 없음 {group.waiting.length}건 (조건 미충족)</summary>
                <ul className="briefing-list">
                  {group.waiting.map((item) => (
                    <ChecklistRow key={item.id} item={item} checked={completed.includes(item.id)} onToggle={toggleCompleted} />
                  ))}
                </ul>
              </details>
            )}
          </section>
        );
      })}

      <p className="policy-checklist-excluded">
        매뉴얼 조건 불일치로 제외된 항목 {excluded_count}건
      </p>
    </div>
  );
}
