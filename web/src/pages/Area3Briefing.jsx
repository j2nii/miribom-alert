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
        <p className="panel-eyebrow">
          <span className="panel-eyebrow__code">AREA 3</span>
          오늘 할 일
        </p>
        <h2>정책 브리핑</h2>
        <p className="panel-subtitle">오늘 무엇을 할지 고르고 보고문까지 받아 가는 화면입니다. 매뉴얼 근거가 달린 구간별 조치 목록, 유사 지역 선례, 복사·저장 가능한 정책 브리핑 순입니다.</p>
      </div>

      <MockBanner isMock={checklist.status === "ok" && checklist.envelope._mock} />

      <div className="section-block">
        <p className="section-title">정책 대응 체크리스트</p>
        <DataState
          result={checklist}
          render={({ envelope }) => (
            <>
              <ChecklistPanel checklistData={envelope.data} region={region} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="section-block">
        <p className="section-title">선례</p>
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
      </div>

      <div className="section-block">
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
      </div>
    </>
  );
}
