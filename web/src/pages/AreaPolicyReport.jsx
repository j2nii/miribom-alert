import { useRegionData } from "../hooks/useRegionData.js";
import { useRegionLabel } from "../data/regionIndex.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import { FullChecklist } from "../components/area3-briefing/ChecklistPanel.jsx";
import PrecedentCards from "../components/area3-briefing/PrecedentCards.jsx";
import BriefingGenerator from "../components/area3-briefing/BriefingGenerator.jsx";

export default function AreaPolicyReport({ region }) {
  const checklist = useRegionData("checklist", region);
  const precedent = useRegionData("precedent", region);
  const briefing = useRegionData("briefing", region);
  const regionLabel = useRegionLabel(region);

  return <>
    <div className="panel-head"><h2>정책 대응</h2><p>선정된 조치와 매뉴얼 근거를 확인합니다.</p></div>
    <DataState result={checklist} render={({ envelope }) => <>
      <section className="analysis-report-block policy-checklist-section">
        <div className="analysis-block-heading"><span>05 · 대응</span><h3>대응 체크리스트</h3><p>선정된 조치를 확인하고 완료한 항목에 표시하세요.</p></div>
        <FullChecklist key={`${region}-${envelope.period?.end ?? "latest"}`} checklistData={envelope.data} storageKey={`${region}-${envelope.period?.end ?? "latest"}`} />
        <SourceBadge envelope={envelope} />
        <CaveatNote envelope={envelope} />
      </section>
    </>} />
    {briefing.status !== "unsupported" && <section className="analysis-report-block policy-generated-section">
      <div className="analysis-block-heading"><span>06 · 보고문</span><h3>작성된 정책 보고문</h3></div>
      <DataState result={briefing} render={({ envelope }) => <><BriefingGenerator briefingData={envelope.data} regionLabel={regionLabel} /><SourceBadge envelope={envelope} /><CaveatNote envelope={envelope} /></>} />
    </section>}
    {precedent.status !== "unsupported" && <details className="compact-details policy-precedents">
      <summary>유사 지역 선례 보기</summary>
      <DataState result={precedent} render={({ envelope }) => <><PrecedentCards precedentData={envelope.data} /><SourceBadge envelope={envelope} /><CaveatNote envelope={envelope} /></>} />
    </details>}
  </>;
}
