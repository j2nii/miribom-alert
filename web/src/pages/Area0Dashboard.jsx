import { useRegionData } from "../hooks/useRegionData.js";
import { REGIONS } from "../data/manifest.js";
import DataState from "../components/common/DataState.jsx";
import SignalStatusPanel from "../components/area0-dashboard/SignalStatusPanel.jsx";
import LifecyclePanel from "../components/area0-dashboard/LifecyclePanel.jsx";
import RegionSummary from "../components/area0-dashboard/RegionSummary.jsx";
import DailyPeakChart from "../components/area0-dashboard/DailyPeakChart.jsx";

export default function Area0Dashboard({ region }) {
  // Reset expanded details and chat history when switching to another region.
  return <DashboardContent key={region} region={region} />;
}

function DashboardContent({ region }) {
  const signalStatus = useRegionData("signal_status", region);
  const forecast = useRegionData("forecast", region);
  const content = useRegionData("content_type", region);
  const timeline = useRegionData("timeline", region);
  const selectedRegion = REGIONS.find((r) => r.key === region);
  const regionLabel = selectedRegion?.label ?? region;

  return (
    <div>
      <div className="panel-head">
        <p className="panel-eyebrow">01 · 이슈 브리핑</p>
        <h2>{regionLabel} 온라인 이슈</h2>
      </div>
      <DailyPeakChart region={region} />
      <details className="summary-details">
        <summary>별도 기준의 지역 자료·과거 사례 보기</summary>
        <div className="summary-details-body">
      <DataState result={signalStatus} render={({ envelope }) => <>
        <RegionSummary envelope={envelope} contentResult={content} timelineResult={timeline} />
        <details className="summary-details">
          <summary>분석 근거와 데이터 유의사항 자세히 보기</summary>
          <div className="summary-details-body">
            {envelope.data.alert_level
              ? <SignalStatusPanel envelope={envelope} forecastEnvelope={forecast.status === "ok" ? forecast.envelope : null} />
              : <LifecyclePanel envelope={envelope} />}
          </div>
        </details>
      </>} />
        </div>
      </details>
    </div>
  );
}
