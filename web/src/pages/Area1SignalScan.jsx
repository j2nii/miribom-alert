import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import CrossValidationLights from "../components/area1-signal-scan/CrossValidationLights.jsx";
import HotspotRanking from "../components/area1-signal-scan/HotspotRanking.jsx";
import VisitorProfileCard from "../components/area1-signal-scan/VisitorProfileCard.jsx";
import Term from "../components/common/Term.jsx";

export default function Area1SignalScan({ region }) {
  const signalStatus = useRegionData("signal_status", region);
  const hotspots = useRegionData("hotspots", region);
  const visitorProfile = useRegionData("visitor_profile", region);
  const contentType = useRegionData("content_type", region);

  const deadZonePois =
    contentType.status === "ok" ? contentType.envelope.data.zone_signals?.데드존_지점 ?? [] : [];

  return (
    <>
      <div className="panel-head">
        <p className="panel-eyebrow">
          <span className="panel-eyebrow__code">AREA 1</span>
          신호 확인
        </p>
        <h2>바이럴 신호 스캔</h2>
        <p className="panel-subtitle">지금 올라온 신호가 믿을 만한지 판단하는 화면입니다. 신호등·급증 지점·방문객 구성 순으로 봅니다. 신호가 실제로 튄 모습과 7일 예측은 바로 위 '추이·예측'에 있습니다. 지역 변경은 AREA0에서 합니다.</p>
      </div>

      <div className="section-block">
        <p className="section-title">
          <Term name="3중 교차검증">3중 교차검증</Term> 신호등
        </p>
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
