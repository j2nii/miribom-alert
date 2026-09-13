import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SignalStatusPanel from "../components/area0-dashboard/SignalStatusPanel.jsx";
import LifecyclePanel from "../components/area0-dashboard/LifecyclePanel.jsx";

export default function Area0Dashboard({ region }) {
  const signalStatus = useRegionData("signal_status", region);
  const forecast = useRegionData("forecast", region);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">AREA 0 · CONTROL DASHBOARD</p>
        <h2>관제 대시보드</h2>
        <p className="panel-subtitle">현재 지역의 경보 상태를 한눈에 확인합니다.</p>
      </div>

      <MockBanner isMock={signalStatus.status === "ok" && signalStatus.envelope._mock} />
      <DataState
        result={signalStatus}
        render={({ envelope }) =>
          // Geoje follows the alert_level schema; other regions (currently
          // only 충주) carry a different, schema-independent lifecycle shape
          // -- branch on which fields are actually present rather than on
          // the region key, so a future real region just needs the right
          // shape of file, no code change here.
          envelope.data.alert_level ? (
            <SignalStatusPanel
              envelope={envelope}
              forecastEnvelope={forecast.status === "ok" ? forecast.envelope : null}
            />
          ) : (
            <LifecyclePanel envelope={envelope} />
          )
        }
      />
    </>
  );
}
