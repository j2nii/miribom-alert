import { useRegionData } from "../hooks/useRegionData.js";
import { useRegionLabel } from "../data/regionIndex.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import { FullChecklist } from "../components/area3-briefing/ChecklistPanel.jsx";
import PrecedentCards from "../components/area3-briefing/PrecedentCards.jsx";
import BriefingGenerator from "../components/area3-briefing/BriefingGenerator.jsx";

function PolicyOverview({ envelope, regionLabel }) {
  const data = envelope.data;
  const active = (data.items ?? []).filter((item) => item.status === "발동");
  const priority = active.filter((item) => ["사전(예보 대응)", "오전(준비)"].includes(item.phase))
    .slice().sort((a, b) => a.rank - b.rank).slice(0, 3);
  const matched = data.matched_for ?? {};
  return <>
    <div className="policy-report-summary">
      <span>{regionLabel} · {envelope.period?.end?.replaceAll("-", ".") ?? "기준일 미제공"} 자료</span>
      <h3>정책 브리핑</h3>
      <p>경보 <strong>{matched.alert_level ?? "자료 없음"}</strong> · {matched.spatial_type ?? "장소 유형 미제공"} · {matched.content_type ?? "콘텐츠 유형 미제공"} 조건에서 대응 항목 <strong>{active.length}건</strong>이 선정됐습니다.</p>
      {priority.length > 0 && <ol>{priority.map((item) => <li key={item.id}><strong>{item.action}</strong><span>{item.owner}</span></li>)}</ol>}
    </div>
    <SourceBadge envelope={envelope} />
  </>;
}

export default function AreaPolicyReport({ region }) {
  const checklist = useRegionData("checklist", region);
  const precedent = useRegionData("precedent", region);
  const briefing = useRegionData("briefing", region);
  const regionLabel = useRegionLabel(region);

  return <>
    <div className="panel-head"><h2>정책 브리핑과 대응 근거</h2><p>위 브리핑의 우선 조치를 전체 매뉴얼 항목과 연결해 확인합니다.</p></div>
    <DataState result={checklist} render={({ envelope }) => <>
      <PolicyOverview envelope={envelope} regionLabel={regionLabel} />
      <section className="analysis-report-block policy-checklist-section">
        <div className="analysis-block-heading"><span>05 · 대응</span><h3>전체 조치와 선정 근거</h3><p>단계별 조치, 담당 부서와 매뉴얼 근거를 확인합니다.</p></div>
        <FullChecklist key={region} checklistData={envelope.data} />
      </section>
    </>} />
    {briefing.status !== "unsupported" && <section className="analysis-report-block policy-generated-section">
      <div className="analysis-block-heading"><span>06 · 보고문</span><h3>작성된 정책 보고문</h3></div>
      <DataState result={briefing} render={({ envelope }) => <><BriefingGenerator briefingData={envelope.data} regionLabel={regionLabel} /><SourceBadge envelope={envelope} /></>} />
    </section>}
    {precedent.status !== "unsupported" && <details className="compact-details policy-precedents">
      <summary>유사 지역 선례 보기</summary>
      <DataState result={precedent} render={({ envelope }) => <><PrecedentCards precedentData={envelope.data} /><SourceBadge envelope={envelope} /></>} />
    </details>}
  </>;
}
