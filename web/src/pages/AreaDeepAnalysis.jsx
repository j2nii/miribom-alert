import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import HotspotRanking from "../components/area1-signal-scan/HotspotRanking.jsx";
import VisitorProfileCard from "../components/area1-signal-scan/VisitorProfileCard.jsx";

const STAGE_NAMES = { 관심: "온라인 관심", 의도: "방문지 검색", 실현: "실제 방문" };
const dateLabel = (date) => date?.replaceAll("-", ".") ?? "기준일 미제공";

function signalValue(value, unit) {
  return Number.isFinite(value) ? `${value.toLocaleString("ko-KR")}${unit ?? ""}` : "자료 없음";
}

function SignalEvidence({ envelope }) {
  const data = envelope.data;
  const signals = data.cross_validation ?? [];
  if (!signals.length) return <p className="regional-empty">이 지역은 교차검증 자료가 없습니다.</p>;
  return <>
    <div className="analysis-evidence-lead">
      <div><span>월별 경보 판정 · {dateLabel(data.as_of)}</span><strong>{data.alert_level} 단계</strong></div>
      <p>독립 지표 {data.agreement?.total ?? signals.length}개 중 {data.agreement?.exceeded_count ?? signals.filter((signal) => signal.exceeded).length}개가 기준을 넘었습니다.</p>
    </div>
    <div className="analysis-signal-list">
      {signals.map((signal) => <div key={signal.stage}>
        <div><span className="analysis-signal-stage">{STAGE_NAMES[signal.stage] ?? signal.stage}</span><strong>{signal.exceeded ? "증가 신호" : signal.value == null ? "자료 없음" : "기준 미만"}</strong></div>
        <p>{signal.signal}</p>
        <small>관측 {signalValue(signal.value, signal.unit)} · 기준 {signalValue(signal.threshold, signal.unit)}</small>
      </div>)}
    </div>
    <SourceBadge envelope={envelope} />
  </>;
}

function ContentBreakdown({ envelope }) {
  const rows = (envelope.data.summary ?? []).slice().sort((a, b) => b.count - a.count);
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return <>
    <p className="analysis-data-date">{dateLabel(envelope.period?.end)}까지 분류 · 관광 관련 영상 {total.toLocaleString("ko-KR")}건</p>
    <ol className="analysis-type-list">
      {rows.map((row) => <li key={row.content_type}>
        <span>{row.content_type}</span>
        <div className="analysis-type-track"><span style={{ width: `${Math.max(2, row.ratio * 100)}%` }} /></div>
        <strong>{row.count}건</strong>
        <small>{(row.ratio * 100).toFixed(1)}%</small>
      </li>)}
    </ol>
    {!rows.length && <p className="regional-empty">분류된 콘텐츠가 없습니다.</p>}
    <SourceBadge envelope={envelope} />
  </>;
}

export default function AreaDeepAnalysis({ region }) {
  const signalStatus = useRegionData("signal_status", region);
  const hotspots = useRegionData("hotspots", region);
  const visitorProfile = useRegionData("visitor_profile", region);
  const contentType = useRegionData("content_type", region);

  return <div className="deep-analysis-body">
    <section className="analysis-report-block" id="signal-evidence">
      <div className="analysis-block-heading"><span>01 · 신호 근거</span><h3>경보는 어떤 자료로 판정했나요?</h3><p>월별 경보를 만드는 세 지표의 관측값과 기준을 나란히 확인합니다.</p></div>
      <DataState result={signalStatus} render={({ envelope }) => <SignalEvidence envelope={envelope} />} />
    </section>

    {(hotspots.status !== "unsupported" || visitorProfile.status !== "unsupported") && <div className="analysis-report-pair">
      {hotspots.status !== "unsupported" && <section className="analysis-report-block" id="place-analysis">
        <div className="analysis-block-heading"><h3>어느 관광지로 몰렸나요?</h3><p>상위 관광지의 입장객, 전년 대비 변화와 장소 특성을 봅니다.</p></div>
        <DataState result={hotspots} render={({ envelope }) => <><p className="analysis-data-date">{dateLabel(envelope.period?.end)} 월별 입장객</p><HotspotRanking hotspotsData={envelope.data} /><SourceBadge envelope={envelope} /></>} />
      </section>}
      {visitorProfile.status !== "unsupported" && <section className="analysis-report-block" id="audience-analysis">
        <div className="analysis-block-heading"><h3>누가 방문했나요?</h3><p>거주지, 이동 거리, 소비와 동행 유형의 분포를 확인합니다.</p></div>
        <DataState result={visitorProfile} render={({ envelope }) => <><p className="analysis-data-date">{dateLabel(envelope.period?.end)} 방문객 구성</p><VisitorProfileCard profileData={envelope.data} /><SourceBadge envelope={envelope} /></>} />
      </section>}
    </div>}

    {contentType.status !== "unsupported" && <section className="analysis-report-block" id="content-analysis">
      <div className="analysis-block-heading"><span>04 · 콘텐츠</span><h3>어떤 콘텐츠가 관심을 모았나요?</h3><p>관광 관련 영상의 유형을 집계해 방문 흐름과 함께 살펴봅니다.</p></div>
      <DataState result={contentType} render={({ envelope }) => <ContentBreakdown envelope={envelope} />} />
    </section>}
  </div>;
}
