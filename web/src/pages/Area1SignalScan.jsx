import { useRegionData } from "../hooks/useRegionData.js";
import { REGIONS } from "../data/manifest.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import CrossValidationLights from "../components/area1-signal-scan/CrossValidationLights.jsx";
import ForecastChart from "../components/area1-signal-scan/ForecastChart.jsx";
import HotspotRanking from "../components/area1-signal-scan/HotspotRanking.jsx";
import VisitorProfileCard from "../components/area1-signal-scan/VisitorProfileCard.jsx";

export default function Area1SignalScan({ region, onRegionChange }) {
  const signalStatus = useRegionData("signal_status", region);
  const forecast = useRegionData("forecast", region);
  const hotspots = useRegionData("hotspots", region);
  const visitorProfile = useRegionData("visitor_profile", region);
  const contentType = useRegionData("content_type", region);

  const deadZonePois =
    contentType.status === "ok" ? contentType.envelope.data.zone_signals?.데드존_지점 ?? [] : [];

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">AREA 1 · SIGNAL SCAN</p>
        <h2>바이럴 신호 스캔</h2>
        <p className="panel-subtitle">지역을 선택해 3중 교차검증·예측·핫스팟·방문객 프로파일을 확인합니다.</p>
      </div>

      <div className="scan-form">
        <div className="scan-input-wrap">
          <select value={region} onChange={(e) => onRegionChange(e.target.value)}>
            {REGIONS.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="section-block">
        <p className="section-title">3중 교차검증 신호등</p>
        <DataState
          result={signalStatus}
          render={({ envelope }) => (
            <>
              <CrossValidationLights signalStatusData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="section-block">
        <p className="section-title">90일 방문객 예측</p>
        <DataState
          result={forecast}
          render={({ envelope }) => (
            <>
              <ForecastChart forecastData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="section-block">
        <p className="section-title">인기 관광지 랭킹</p>
        <DataState
          result={hotspots}
          render={({ envelope }) => (
            <>
              <HotspotRanking hotspotsData={envelope.data} deadZonePois={deadZonePois} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>

      <div className="section-block">
        <p className="section-title">방문객 프로파일</p>
        <DataState
          result={visitorProfile}
          render={({ envelope }) => (
            <>
              <VisitorProfileCard profileData={envelope.data} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </div>
    </>
  );
}
