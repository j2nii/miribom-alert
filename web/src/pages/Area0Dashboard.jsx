import { useEffect, useRef, useState } from "react";
import { useRegionData } from "../hooks/useRegionData.js";
import { useMediaQuery, NARROW_QUERY } from "../hooks/useMediaQuery.js";
import { getRegionCoverage } from "../data/manifest.js";
import { useRegionLabel } from "../data/regionIndex.js";
import RegionSearch from "../components/area0-dashboard/RegionSearch.jsx";
import AnalysisTierCard from "../components/area0-dashboard/AnalysisTierCard.jsx";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import ChatWidget from "../components/common/ChatWidget.jsx";
import SignalStatusPanel from "../components/area0-dashboard/SignalStatusPanel.jsx";
import LifecyclePanel from "../components/area0-dashboard/LifecyclePanel.jsx";
import TodayActionCard from "../components/area0-dashboard/TodayActionCard.jsx";

export default function Area0Dashboard({ region, onRegionChange, askOpen, onAskClose }) {
  const signalStatus = useRegionData("signal_status", region);
  const forecast = useRegionData("forecast", region);
  // 오늘의 결론 카드용. 둘 다 정적 JSON이라 AREA3와 중복 요청이 되지만 브라우저 캐시가
  // 받아주고, 대신 AREA0가 AREA3의 결론을 먼저 보여줄 수 있게 된다.
  const checklist = useRegionData("checklist", region);
  const briefing = useRegionData("briefing", region);
  const regionLabel = useRegionLabel(region);
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
  // 이 측정값의 목적은 "옆 칼럼과 높이를 맞추는 것"이다. 좁은 화면에서는 두 칼럼이
  // 위아래로 쌓여 옆 칼럼이라는 개념 자체가 없어지는데, 그래도 높이를 넘기면 대화창이
  // 게이지 패널만큼(수백 px) 빈 채로 세로를 차지한다 -- QA의 "빈 대화창이 화면 절반을
  // 먹는다"가 그 증상이다. 좁은 화면에서는 높이 강제를 끄고 내용만큼만 차지하게 한다.
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const coverage = getRegionCoverage(region);

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
        <p className="panel-eyebrow">
          <span className="panel-eyebrow__code">AREA 0</span>
          지금 상황
        </p>
        <h2>관제 대시보드</h2>
        <p className="panel-subtitle">담당 지역의 오늘 경보 단계를 확인하고, 옆 대화창으로 근거를 되물어보는 화면입니다. 여기서 바꾼 지역은 화면 전체(AREA1~4)와 대화창에 함께 적용됩니다.</p>
      </div>

      <div className="scan-form">
        <RegionSearch region={region} onRegionChange={onRegionChange} />
        {/* 지역마다 준비된 데이터 종류가 달라 어떤 화면은 비어 있다. 그 이유를 고르는
            자리에서 바로 알려 준다 -- 빈 화면을 고장으로 읽지 않도록. */}
        <span className="region-coverage" title="9종 데이터 계약 중 이 지역에 준비된 수">
          데이터 {coverage.available}/{coverage.total}종
          <span className="region-coverage__real">실측 {coverage.real}</span>
        </span>
      </div>

      <AnalysisTierCard region={region} onRegionChange={onRegionChange} />

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

          <TodayActionCard
            region={region}
            checklist={checklist}
            briefing={briefing}
            alertLevel={
              signalStatus.status === "ok" ? signalStatus.envelope.data.alert_level : null
            }
          />
        </div>

        <ChatWidget
          region={region}
          regionLabel={regionLabel}
          boundaryRef={layoutRef}
          maxHeight={isNarrow ? null : mainHeight}
          sheetOpen={askOpen}
          onSheetClose={onAskClose}
        />
      </div>
    </>
  );
}
