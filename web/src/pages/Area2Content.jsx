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
        <p className="panel-eyebrow">
          <span className="panel-eyebrow__code">AREA 2</span>
          원인 콘텐츠
        </p>
        <h2>콘텐츠 분석</h2>
        <p className="panel-subtitle">어떤 콘텐츠가 사람을 부르고 있고 어느 지점이 비어 있는지 확인하는 화면입니다. 전용 데이터가 없는 탭은 '준비 중' 배지로 표시됩니다.</p>
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
