import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import CrossValidationLights from "../components/area1-signal-scan/CrossValidationLights.jsx";
import ForecastChart from "../components/area1-signal-scan/ForecastChart.jsx";
import HotspotRanking from "../components/area1-signal-scan/HotspotRanking.jsx";
import VisitorProfileCard from "../components/area1-signal-scan/VisitorProfileCard.jsx";

export default function Area1SignalScan({ region }) {
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
        <p className="panel-eyebrow">04 · 참고자료</p>
        <h2>방문 흐름과 지역 현황</h2>
      </div>

      <div className="section-block">
        <p className="section-title">관심이 방문으로 이어지나요?</p>
        <DataState
          result={signalStatus}
          render={({ envelope }) =>
            // 충주처럼 alert_level/cross_validation 스키마가 아니라 생애주기
            // 스키마(lifecycle_stage 등)인 지역은 CrossValidationLights가
            // 기대하는 필드(특히 agreement)가 아예 없어 그대로 넘기면
            // 크래시한다(흰 화면 -- Area0Dashboard.jsx와 같은 기준으로 분기).
            // 이런 지역은 3중 교차검증 자체가 없고 SNS 언급량 단일 신호로만
            // 판단하므로, AREA0에 이미 뜬 게이지·추이 그래프(LifecyclePanel)를
            // 여기서 또 통째로 재렌더링하면 완전 중복이라 짧은 안내로 대체.
            envelope.data.alert_level ? (
              <>
                <CrossValidationLights signalStatusData={envelope.data} />
                <SourceBadge envelope={envelope} />
                <CaveatNote envelope={envelope} />
              </>
            ) : (
              <>
                <div className="info-box">
                  이 지역은 3중 교차검증 대상이 아닙니다(SNS 언급량 기반 단일 생애주기 판단). 게이지·추이 그래프는 AREA0 관제 대시보드에서 확인하세요.
                </div>
                <SourceBadge envelope={envelope} />
                <CaveatNote envelope={envelope} />
              </>
            )
          }
        />
      </div>

      <details className="section-block compact-details" key={`forecast-${region}`}>
        <summary>90일 방문객 예측{forecast.status === "unsupported" ? " · 준비 중" : " 보기"}</summary>
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
      </details>

      <details className="section-block compact-details" key={`ranking-${region}`}>
        <summary>인기 관광지 랭킹</summary>
        <DataState
          result={hotspots}
          render={({ envelope }) => (
            <>
              <HotspotRanking key={region} hotspotsData={envelope.data} deadZonePois={deadZonePois} />
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </details>

      <details className="section-block compact-details" key={`profile-${region}`}>
        <summary>방문객 구성</summary>
        <DataState
          result={visitorProfile}
          render={({ envelope }) => (
            <>
              <VisitorProfileCard key={region} profileData={envelope.data} spendingLabel={envelope.caveat?.some((note) => note.includes("외국인 방문객의 소비")) ? "외국인 소비" : "소비"} />
              <p className="profile-period">자료 기간 {envelope.period?.start ?? "미제공"} ~ {envelope.period?.end ?? "미제공"}</p>
              <SourceBadge envelope={envelope} />
              <CaveatNote envelope={envelope} />
            </>
          )}
        />
      </details>
    </>
  );
}
