import { useState } from "react";
import ManualRefCite from "../common/ManualRefCite.jsx";
import { useChecklistDone } from "../../hooks/useChecklistDone.js";

// agents 브랜치 계약 변경: "사전(예보 대응)"이 기존 4단계 앞에 추가됐다. 이
// 목록에 없는 phase 값을 가진 항목은 byPhase의 필터에서 조용히 빠지므로(에러
// 없이 화면에서 사라짐), 새 phase가 생길 때마다 여기도 같이 넓혀야 한다.
//
// `slug`는 구간별 색 토큰(index.css의 --phase-*)과 이어진다. 구간 구분이 텍스트
// 헤더뿐이라 스크롤하며 훑을 때 지금 어느 구간인지 놓친다는 QA 피드백 때문에, 각
// 구간에 왼쪽 컬러 바 + 같은 색 칩 헤더를 준다. 시간 순서(사전→운영→마감)를 차가운
// 색에서 뜨거운 색으로 흐르게 배치해 "지금 대응 중"인 구간이 가장 눈에 띈다.
const PHASES = [
  { name: "사전(예보 대응)", slug: "before" },
  { name: "오전(준비)", slug: "morning" },
  { name: "운영 중(모니터링)", slug: "operating" },
  { name: "비상 대응", slug: "emergency" },
  { name: "마감(평가)", slug: "closing" },
];
const PAGE_SIZE = 5;

function ChecklistItem({ item, checked, onToggle, muted }) {
  return (
    <li className={`briefing-item${checked ? " briefing-item--done" : ""}${muted ? " briefing-item--muted" : ""}`}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <label className="briefing-item-check">
          <input type="checkbox" checked={checked} onChange={() => onToggle(item.id)} />
          <span className="briefing-item-label">{item.action}</span>
        </label>
        <span className={`priority-tag priority-${item.priority}`}>{item.priority}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>
        담당: <span className="dept-chip">{item.owner}</span> · {item.match_reason}
      </div>
      <ManualRefCite manualRef={item.manual_ref} />
    </li>
  );
}

export default function ChecklistPanel({ checklistData, region }) {
  const { matched_for, items, excluded_count } = checklistData;
  const [expanded, setExpanded] = useState({});
  const { done, toggle } = useChecklistDone(region);

  // agent3가 매긴 status: "발동" = 지금 조건에 해당하는 조치, "대기" = 조건 미충족.
  // 예전에는 둘을 똑같은 무게로 한 줄에 섞어 22건을 쏟아내서, 처음 보는 사람은 무엇부터
  // 해야 하는지 고를 수 없었다. 발동만 앞에 세우고 대기는 구간 끝에 접어 둔다.
  const active = items.filter((i) => i.status !== "대기");
  const doneCount = active.filter((i) => done.has(i.id)).length;
  const progress = active.length > 0 ? Math.round((doneCount / active.length) * 100) : 0;

  const byPhase = PHASES.map((phase) => ({
    ...phase,
    items: active.filter((i) => i.phase === phase.name).sort((a, b) => a.rank - b.rank),
    waiting: items.filter((i) => i.status === "대기" && i.phase === phase.name).sort((a, b) => a.rank - b.rank),
  })).filter((g) => g.items.length > 0 || g.waiting.length > 0);

  return (
    <div>
      <div className="checklist-progress">
        <div className="checklist-progress__head">
          <strong>
            오늘 할 일 {active.length}건 중 <span className="checklist-progress__count">{doneCount}건</span> 완료
          </strong>
          <span className="checklist-progress__pct">{progress}%</span>
        </div>
        <div className="checklist-progress__bar">
          <div className="checklist-progress__fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="checklist-progress__note">
          체크 상태는 이 브라우저에만 저장되고 날짜가 바뀌면 새로 시작합니다.
        </p>
      </div>

      <div className="info-box">
        {/* signal_status.congestion_level처럼 matched_for.congestion_level도
            혼잡도 미측정 지역/시점에서는 생략될 수 있다. */}
        이 조건으로 매칭됨 — 경보 {matched_for.alert_level} · 혼잡도{" "}
        {matched_for.congestion_level != null ? matched_for.congestion_level : "미측정"} ·{" "}
        {matched_for.spatial_type} · {matched_for.content_type}
        {matched_for.profile_tags?.length > 0 && <> · {matched_for.profile_tags.join(", ")}</>}
      </div>

      {byPhase.map((group) => {
        const showAll = expanded[group.name];
        const visible = showAll ? group.items : group.items.slice(0, PAGE_SIZE);
        const groupDone = group.items.filter((i) => done.has(i.id)).length;
        return (
          <section key={group.name} className={`checklist-phase checklist-phase--${group.slug}`}>
            <div className="checklist-phase__head">
              <span className="checklist-phase__chip">{group.name}</span>
              <span className="checklist-phase__count">
                {groupDone}/{group.items.length}
              </span>
            </div>
            <ul className="briefing-list">
              {visible.map((item) => (
                <ChecklistItem key={item.id} item={item} checked={done.has(item.id)} onToggle={toggle} />
              ))}
            </ul>
            {group.items.length > PAGE_SIZE && (
              <button
                onClick={() => setExpanded((e) => ({ ...e, [group.name]: !showAll }))}
                className="footer-link-btn"
              >
                {showAll ? "접기" : `더보기 (${group.items.length - PAGE_SIZE}건)`}
              </button>
            )}
            {group.waiting.length > 0 && (
              <details className="checklist-waiting">
                <summary>지금은 해당 없음 {group.waiting.length}건 (조건 미충족)</summary>
                <ul className="briefing-list">
                  {group.waiting.map((item) => (
                    <ChecklistItem key={item.id} item={item} checked={done.has(item.id)} onToggle={toggle} muted />
                  ))}
                </ul>
              </details>
            )}
          </section>
        );
      })}

      <p style={{ fontSize: 12, color: "var(--ink-soft)" }}>
        매뉴얼 조건 불일치로 제외된 항목 {excluded_count}건
      </p>
    </div>
  );
}
