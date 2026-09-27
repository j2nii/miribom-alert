import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import MockBanner from "../components/common/MockBanner.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import UploadVideoList from "../components/area2-content/UploadVideoList.jsx";
import MorningBriefing from "../components/area2-content/MorningBriefing.jsx";

export default function Area2Content({ region }) {
  const contentType = useRegionData("content_type", region);
  const signalStatus = useRegionData("signal_status", region);

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">02 · 관련 콘텐츠</p>
        <h2>오늘의 지역 보고서</h2>
      </div>

      <MorningBriefing region={region} signalStatus={signalStatus} />
      <details className="summary-details" key={`archive-${region}`}>
      <summary>업로드 영상 목록</summary>
      <div className="summary-details-body">
      <MockBanner isMock={contentType.status === "ok" && contentType.envelope._mock} />
      <DataState
        result={contentType}
        render={({ envelope }) => (
          <>
            <p className="content-scope">유튜브 수집 자료 · 기준 {envelope.period?.end ?? "미제공"} · 위 보고서 목업과 별도 자료</p>
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
