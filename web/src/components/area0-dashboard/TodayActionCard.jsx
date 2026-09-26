import { useState } from "react";
import { useChecklistDone } from "../../hooks/useChecklistDone.js";

// 첫 화면에서 "그래서 오늘 뭘 하면 되나"에 답하는 카드.
//
// 여기 보이는 값은 하나도 새로 만든 게 아니다. 전부 agent가 이미 산출해 파일에 넣어뒀지만
// 화면이 꺼내 쓰지 않던 필드들이다:
//   - checklist.data.assessment.situation_types[]  상황 유형 + 근거 (미사용이었음)
//   - checklist.data.items[].status = 발동/대기      지금 해당하는 조치 (미사용이었음)
//   - briefing.data.actions[]                       핵심 조치 3건 + 왜 (미사용이었음)
// 결론이 AREA3까지 스크롤해야 나오던 것을, 판단 근거와 함께 첫 화면으로 끌어올린다.
export default function TodayActionCard({ region, checklist, briefing, alertLevel }) {
  const { done } = useChecklistDone(region);
  const [copied, setCopied] = useState(false);

  if (checklist.status !== "ok") return null;

  const data = checklist.envelope.data;
  const active = data.items.filter((i) => i.status !== "대기");
  if (active.length === 0) return null;

  const urgent = active.filter((i) => i.priority === "높음" || i.priority === "긴급");
  const doneCount = active.filter((i) => done.has(i.id)).length;
  const situations = data.assessment?.situation_types ?? [];

  // briefing이 있으면 agent5가 고른 핵심 3건(왜까지 붙어 있다)을 쓰고, 없는 지역은
  // 체크리스트 rank 상위 3건으로 대신한다.
  const briefingActions = briefing?.status === "ok" ? briefing.envelope.data.actions : null;
  const top = briefingActions?.length
    ? briefingActions.slice(0, 3).map((a) => ({ id: a.checklist_id, action: a.action, why: a.why }))
    : active
        .slice()
        .sort((a, b) => a.rank - b.rank)
        .slice(0, 3)
        .map((i) => ({ id: i.id, action: i.action, why: i.match_reason }));

  async function handleCopy() {
    const lines = [
      `[${alertLevel ?? "-"} 단계] 오늘 조치 ${active.length}건 (긴급 ${urgent.length}건)`,
      situations.length ? `상황 유형: ${situations.map((s) => s.type).join(" · ")}` : null,
      "",
      ...top.map((t, i) => `${i + 1}. ${t.action}${t.why ? `\n   - ${t.why}` : ""}`),
    ].filter((l) => l !== null);
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 클립보드 권한이 없는 환경 -- 아래 목록을 직접 긁어 복사하면 된다
    }
  }

  return (
    <section className="today-action">
      <div className="today-action__head">
        <p className="today-action__eyebrow">오늘의 결론</p>
        <p className="today-action__count">
          조치 <strong>{active.length}</strong>건
          {urgent.length > 0 && <> · 긴급 {urgent.length}건</>}
          {doneCount > 0 && <span className="today-action__done"> · {doneCount}건 완료</span>}
        </p>
      </div>

      {situations.length > 0 && (
        <div className="today-action__situations">
          {situations.map((s) => (
            <details key={s.type} className="today-action__situation">
              <summary>{s.type}</summary>
              <p>{s.evidence}</p>
            </details>
          ))}
        </div>
      )}

      <ol className="today-action__list">
        {top.map((t) => (
          <li key={t.id}>
            <span className="today-action__what">{t.action}</span>
            {t.why && <span className="today-action__why">{t.why}</span>}
          </li>
        ))}
      </ol>

      <div className="today-action__buttons">
        <a href="#area3" className="btn-primary">
          오늘 할 일 {active.length}건 보기
        </a>
        <button type="button" className="btn-ghost" onClick={handleCopy}>
          {copied ? "복사됨" : "요약 복사"}
        </button>
      </div>
    </section>
  );
}
