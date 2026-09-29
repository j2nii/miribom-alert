import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import UploadVideoList from "../components/area2-content/UploadVideoList.jsx";
import MorningBriefing from "../components/area2-content/MorningBriefing.jsx";

export default function Area2Content({ region }) {
  const contentType = useRegionData("content_type", region);
  const recentYoutube = useRegionData("recent_youtube", region);
  const signalStatus = useRegionData("signal_status", region);
  const signalSeries = useRegionData("signal_series", region);

  return (
    <>
      <div className="panel-head">
        <h2>오늘의 지역 보고서</h2>
      </div>

      <MorningBriefing region={region} signalStatus={signalStatus} signalSeries={signalSeries} contentType={contentType} recentYoutube={recentYoutube} />
      <details className="summary-details" key={`archive-${region}`}>
      <summary>기존 분류 영상 목록</summary>
      <div className="summary-details-body">
      <MockBanner isMock={contentType.status === "ok" && contentType.envelope._mock} />
      <DataState
        result={contentType}
        render={({ envelope }) => (
          <>
            <p className="content-scope">유튜브 분류 자료 · 기준 {envelope.period?.end ?? "미제공"}</p>
            <UploadVideoList
              key={region}
              contentTypeData={envelope.data}
            />
            <SourceBadge envelope={envelope} />
            <CaveatNote envelope={envelope} />
          </>
        )}
      />
      </div>
      </details>
    </>
  );
}
