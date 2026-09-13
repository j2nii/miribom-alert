import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import PerformanceReport from "../components/area4-performance/PerformanceReport.jsx";
import LeadTimeTimeline from "../components/area4-performance/LeadTimeTimeline.jsx";

export default function Area4Performance({ region }) {
  const beforeAfter = useRegionData("before_after", region);
  const timeline = useRegionData("timeline", region);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">AREA 4 · 성과 리포트</p>
        <h2>성과 리포트</h2>
        <p className="panel-subtitle">조기 감지가 실제 대응·개선으로 이어졌는지 리드타임과 전후 지표로 봅니다.</p>
      </div>

      <MockBanner isMock={beforeAfter.status === "ok" && beforeAfter.envelope._mock} />

      <div className="section-block">
        <p className="section-title">리드타임</p>
        <DataState
          result={timeline}
          render={({ envelope }) => (
            <>
              <LeadTimeTimeline timelineData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="section-block">
        <p className="section-title">조치 전후 비교</p>
        <DataState
          result={beforeAfter}
          render={({ envelope }) => (
            <>
              <PerformanceReport beforeAfterData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>
    </>
  );
}
