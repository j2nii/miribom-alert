import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import ChecklistPanel from "../components/area3-briefing/ChecklistPanel.jsx";

export default function Area3Briefing({ region }) {
  const checklist = useRegionData("checklist", region);

  return (
    <>
      <div className="panel-head">
        <h2>우선 대응 사항</h2>
      </div>

      <MockBanner isMock={checklist.status === "ok" && checklist.envelope._mock} />

      <div>
        <DataState
          result={checklist}
          render={({ envelope }) => (
            <>
              <p className="policy-now-period">자료 기준 {envelope.period?.end ?? "미제공"} · 사전 준비 우선순위</p>
              <ChecklistPanel key={region} checklistData={envelope.data} showDetails={false} />
              <a className="policy-report-link" href="#policy-report">대응 체크리스트 보기 <span aria-hidden="true">→</span></a>
              <details className="compact-details"><summary>출처 보기</summary>
              <SourceBadge envelope={envelope} />
              </details>
            </>
          )}
        />
      </div>

    </>
  );
}
