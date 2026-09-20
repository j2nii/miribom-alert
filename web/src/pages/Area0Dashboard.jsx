import { useEffect, useRef, useState } from "react";
import { useRegionData } from "../hooks/useRegionData.js";
import { REGIONS } from "../data/manifest.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import ChatWidget from "../components/common/ChatWidget.jsx";
import SignalStatusPanel from "../components/area0-dashboard/SignalStatusPanel.jsx";
import LifecyclePanel from "../components/area0-dashboard/LifecyclePanel.jsx";

export default function Area0Dashboard({ region, onRegionChange }) {
  const signalStatus = useRegionData("signal_status", region);
  const forecast = useRegionData("forecast", region);
  const regionLabel = REGIONS.find((r) => r.key === region)?.label ?? region;
  // Watched by ChatWidget: as long as any part of this row is still on
  // screen, the chat stays docked in its 2-column spot -- only once the
  // whole row (both columns) has scrolled fully past does it switch to
  // floating. Passing the row itself (not a 1px marker at its top) is what
  // makes that "fully past", not "just started scrolling past".
  const layoutRef = useRef(null);
  const mainRef = useRef(null);
  // CSS-only ("stretch this column to match that one's height") turned out
  // unreliable here -- a flex/grid item whose child needs to fill its
  // *stretched* height (not its natural content height) runs into a
  // circular sizing question the auto-track algorithm doesn't resolve the
  // way you'd expect, so the chat panel just kept growing past AREA0
  // instead of capping and scrolling. Measuring the left column's actual
  // rendered height in JS and applying it as an explicit pixel height is
  // unambiguous -- ChatWidget then has a real height to overflow against.
  const [mainHeight, setMainHeight] = useState(null);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect?.height;
      if (height) setMainHeight(height);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">AREA 0 · CONTROL DASHBOARD</p>
        <h2>관제 대시보드</h2>
        <p className="panel-subtitle">지역을 선택해 경보 상태를 한눈에 확인합니다. 여기서 바꾸는 지역은 화면 전체(AREA1~4)에 적용됩니다.</p>
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

      <div className="area0-layout" ref={layoutRef}>
        <div className="area0-layout__main" ref={mainRef}>
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
        </div>

        <ChatWidget region={region} regionLabel={regionLabel} boundaryRef={layoutRef} maxHeight={mainHeight} />
      </div>
    </>
  );
}
