import { useRegionData } from "../hooks/useRegionData.js";
import { REGIONS } from "../data/manifest.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import ChecklistPanel from "../components/area3-briefing/ChecklistPanel.jsx";
import PrecedentCards from "../components/area3-briefing/PrecedentCards.jsx";
import BriefingGenerator from "../components/area3-briefing/BriefingGenerator.jsx";

export default function Area3Briefing({ region }) {
  const checklist = useRegionData("checklist", region);
  const precedent = useRegionData("precedent", region);
  const briefing = useRegionData("briefing", region);
  const regionLabel = REGIONS.find((r) => r.key === region)?.label ?? region;

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">03 · 대응 준비</p>
        <h2>지금 먼저 할 일</h2>
      </div>

      <MockBanner isMock={checklist.status === "ok" && checklist.envelope._mock} />

      <div>
        <DataState
          result={checklist}
          render={({ envelope }) => (
            <>
              <p className="policy-now-period">자료 기준 {envelope.period?.end ?? "미제공"} · 사전 준비 우선순위</p>
              <ChecklistPanel key={region} checklistData={envelope.data} />
              <details className="compact-details"><summary>출처·데이터 유의사항</summary>
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
              </details>
            </>
          )}
        />
      </div>

      <details className="compact-details" key={`precedent-${region}`}>
        <summary>선례 보기{precedent.status === "unsupported" ? " · 준비 중" : ""}</summary>
        <DataState
          result={precedent}
          render={({ envelope }) => (
            <>
              <PrecedentCards precedentData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </details>

      <details className="compact-details" key={`briefing-${region}`}>
        <summary>상세 브리핑{briefing.status === "unsupported" ? " · 준비 중" : ""}</summary>
        <DataState
          result={briefing}
          render={({ envelope }) => (
            <>
              <BriefingGenerator briefingData={envelope.data} regionLabel={regionLabel} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </details>
    </>
  );
}
