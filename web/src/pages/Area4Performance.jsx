import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import PerformanceReport from "../components/area4-performance/PerformanceReport.jsx";
import LeadTimeTimeline from "../components/area4-performance/LeadTimeTimeline.jsx";
import Term from "../components/common/Term.jsx";

export default function Area4Performance({ region }) {
  const beforeAfter = useRegionData("before_after", region);
  const timeline = useRegionData("timeline", region);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">
          <span className="panel-eyebrow__code">AREA 4</span>
          성과 점검
        </p>
        <h2>성과 리포트</h2>
        <p className="panel-subtitle">신호를 조치로 연결하는 데 며칠 걸렸는지, 조치 후 지표가 실제로 움직였는지 점검하는 화면입니다. 다음 회차 대응 속도를 정하는 근거로 씁니다.</p>
      </div>

      <MockBanner isMock={beforeAfter.status === "ok" && beforeAfter.envelope._mock} />

      <div className="section-block">
        <p className="section-title">
          <Term name="리드타임">리드타임</Term>
        </p>
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
