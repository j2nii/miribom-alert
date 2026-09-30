import { useEffect, useState } from "react";
import { useRegionData } from "../../hooks/useRegionData.js";
import { CHECKLIST_DONE_EVENT, checklistStorageKey, readChecklistDone } from "../../lib/checklistDone.js";

// 오늘의 결론. develop TodayActionCard가 보여주던 것을 AREA0 기존 카드 안
// 접기 하나로 옮긴다 -- 새 카드를 만들면 브리핑 카드와 두 덩어리가 된다.
//
// 완료 건수는 정책 보고서의 전체 체크리스트와 같은 저장소를 읽는다.
// develop의 useChecklistDone(날짜 키)을 되살리면 두 화면이 서로 다른 키를 봐서
// 한쪽에서 체크한 게 다른 쪽에 안 보인다.
export default function TodayConclusion({ region }) {
  const checklist = useRegionData("checklist", region);
  const briefing = useRegionData("briefing", region);
  if (checklist.status !== "ok") return null;
  return <Conclusion
    region={region}
    envelope={checklist.envelope}
    briefingData={briefing.status === "ok" ? briefing.envelope.data : null}
  />;
}

function Conclusion({ region, envelope, briefingData }) {
  const data = envelope.data;
  const storageKey = checklistStorageKey(region, envelope.period?.end);
  const [done, setDone] = useState(() => readChecklistDone(storageKey));

  // 정책 보고서에서 체크하면 여기 완료 수도 따라 움직여야 한다.
  useEffect(() => {
    const sync = () => setDone(readChecklistDone(storageKey));
    sync();
    window.addEventListener(CHECKLIST_DONE_EVENT, sync);
    window.addEventListener("focus", sync);
    return () => {
      window.removeEventListener(CHECKLIST_DONE_EVENT, sync);
      window.removeEventListener("focus", sync);
    };
  }, [storageKey]);

  const active = data.items.filter((item) => item.status === "발동");
  if (!active.length) return null;
  const urgent = active.filter((item) => item.priority === "높음");
  const doneCount = active.filter((item) => done.includes(item.id)).length;
  const situations = data.assessment?.situation_types ?? [];

  // 브리핑이 있으면 그 쪽 "왜"가 문장이 낫다. 없는 지역은 체크리스트 선정 사유로 대신한다.
  const top = briefingData?.actions?.length
    ? briefingData.actions.slice(0, 3).map((action) => ({ action: action.action, why: action.why }))
    : [...active].sort((a, b) => a.rank - b.rank).slice(0, 3).map((item) => ({ action: item.action, why: item.match_reason }));

  return (
    <details className="compact-details today-conclusion">
      <summary>오늘의 결론 · 조치 {active.length}건 중 긴급 {urgent.length}건 · 완료 {doneCount}건</summary>

      {situations.length > 0 && <div className="today-conclusion__situations">
        {situations.map((situation) => <div key={situation.type}>
          <span className="dept-chip">{situation.type}</span>
          <p>{situation.evidence}</p>
        </div>)}
      </div>}

      <ol className="today-conclusion__actions">
        {top.map((item, index) => <li key={item.action}>
          <span className="policy-now-number">{index + 1}</span>
          <div><strong>{item.action}</strong>{item.why && <p>{item.why}</p>}</div>
        </li>)}
      </ol>

      <a className="policy-report-link" href="#policy-report">대응 체크리스트 전체 보기 →</a>
    </details>
  );
}
