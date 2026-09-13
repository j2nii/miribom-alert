import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import ContentTypeTabs from "../components/area2-content/ContentTypeTabs.jsx";

export default function Area2Content({ region }) {
  const contentType = useRegionData("content_type", region);
  const signalStatus = useRegionData("signal_status", region);
  const hotspots = useRegionData("hotspots", region);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">AREA 2 · CONTENT SOURCES</p>
        <h2>콘텐츠 분석</h2>
        <p className="panel-subtitle">바이럴을 일으킨 콘텐츠와 실제 검색·방문 데이터를 함께 봅니다.</p>
      </div>

      <MockBanner isMock={contentType.status === "ok" && contentType.envelope._mock} />
      <DataState
        result={contentType}
        render={({ envelope }) => (
          <>
            <ContentTypeTabs
              contentTypeData={envelope.data}
              crossValidationSignals={
                signalStatus.status === "ok" ? signalStatus.envelope.data.cross_validation : []
              }
              hotspotsData={hotspots.status === "ok" ? hotspots.envelope.data : null}
            />
            <SourceBadge envelope={envelope} />
            <CaveatNote envelope={envelope} />
          </>
        )}
      />
    </>
  );
}
