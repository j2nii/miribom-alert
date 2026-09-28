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
        <h2>지난 이슈와 대응 기록</h2>
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

      {beforeAfter.status !== "unsupported" && <div className="section-block">
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
      </div>}
    </>
  );
}
