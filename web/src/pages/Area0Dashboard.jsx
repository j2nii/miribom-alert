import { useRegionData } from "../hooks/useRegionData.js";
import { useRegionLabel } from "../data/regionIndex.js";
import DataState from "../components/common/DataState.jsx";
import DailyPeakChart from "../components/area0-dashboard/DailyPeakChart.jsx";
import DailySignalChart from "../components/area0-dashboard/DailySignalChart.jsx";
import TodayConclusion from "../components/area0-dashboard/TodayConclusion.jsx";

export default function Area0Dashboard({ region }) {
  // Reset expanded details and chat history when switching to another region.
  return <DashboardContent key={region} region={region} />;
}

function DashboardContent({ region }) {
  const forecast = useRegionData("forecast", region);
  const signalSeries = useRegionData("signal_series", region);
  const signalStatus = useRegionData("signal_status", region);
  const regionLabel = useRegionLabel(region);

  return (
    <div>
      <div className="panel-head">
        <h2>{regionLabel} 오늘의 브리핑</h2>
      </div>
      {region === "chungju"
        ? <DailyPeakChart region={region} />
        : <DataState result={signalSeries} render={({ envelope }) => <DailySignalChart envelope={envelope} forecastEnvelope={forecast.status === "ok" ? forecast.envelope : null} statusEnvelope={signalStatus.status === "ok" ? signalStatus.envelope : null} />} />}
      <TodayConclusion region={region} />
    </div>
  );
}
