import { useState } from "react";
import ManualRefCite from "../common/ManualRefCite.jsx";

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

export default function ChecklistPanel({ checklistData }) {
  const { matched_for, items, excluded_count } = checklistData;
  const [expanded, setExpanded] = useState({});

  const byPhase = PHASES.map((phase) => ({
    ...phase,
    items: items.filter((i) => i.phase === phase.name).sort((a, b) => a.rank - b.rank),
  })).filter((g) => g.items.length > 0);

  return (
    <div>
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
        return (
          <section key={group.name} className={`checklist-phase checklist-phase--${group.slug}`}>
            <div className="checklist-phase__head">
              <span className="checklist-phase__chip">{group.name}</span>
              <span className="checklist-phase__count">{group.items.length}건</span>
            </div>
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
                onClick={() => setExpanded((e) => ({ ...e, [group.name]: !showAll }))}
                className="footer-link-btn"
              >
                {showAll ? "접기" : `더보기 (${group.items.length - PAGE_SIZE}건)`}
              </button>
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
