import { useState } from "react";
import ManualRefCite from "../common/ManualRefCite.jsx";

const PHASE_ORDER = ["오전(준비)", "운영 중(모니터링)", "비상 대응", "마감(평가)"];
const PAGE_SIZE = 5;

export default function ChecklistPanel({ checklistData }) {
  const { matched_for, items, excluded_count } = checklistData;
  const [expanded, setExpanded] = useState({});

  const byPhase = PHASE_ORDER.map((phase) => ({
    phase,
    items: items.filter((i) => i.phase === phase).sort((a, b) => a.rank - b.rank),
  })).filter((g) => g.items.length > 0);

  return (
    <div>
      <div className="info-box">
        이 조건으로 매칭됨 — 경보 {matched_for.alert_level} · 혼잡도 {matched_for.congestion_level} ·{" "}
        {matched_for.spatial_type} · {matched_for.content_type}
        {matched_for.profile_tags?.length > 0 && <> · {matched_for.profile_tags.join(", ")}</>}
      </div>

      {byPhase.map((group) => {
        const showAll = expanded[group.phase];
        const visible = showAll ? group.items : group.items.slice(0, PAGE_SIZE);
        return (
          <div key={group.phase} style={{ marginBottom: 16 }}>
            <p style={{ fontWeight: 700, fontSize: 14, margin: "0 0 8px" }}>{group.phase}</p>
            <ul className="briefing-list">
              {visible.map((item) => (
                <li key={item.id} className="briefing-item">
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <span className="briefing-item-label">{item.action}</span>
                    <span className={`priority-tag priority-${item.priority}`}>{item.priority}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>
                    담당: <span className="dept-chip">{item.owner}</span> · {item.match_reason}
                  </div>
                  <ManualRefCite manualRef={item.manual_ref} />
                </li>
              ))}
            </ul>
            {group.items.length > PAGE_SIZE && (
              <button
                onClick={() => setExpanded((e) => ({ ...e, [group.phase]: !showAll }))}
                className="footer-link-btn"
              >
                {showAll ? "접기" : `더보기 (${group.items.length - PAGE_SIZE}건)`}
              </button>
            )}
          </div>
        );
      })}

      <p style={{ fontSize: 12, color: "var(--ink-soft)" }}>
        매뉴얼 조건 불일치로 제외된 항목 {excluded_count}건
      </p>
    </div>
  );
}
