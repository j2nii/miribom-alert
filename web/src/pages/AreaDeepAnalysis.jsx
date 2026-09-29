import { useRegionData } from "../hooks/useRegionData.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import ManualRefCite from "../components/common/ManualRefCite.jsx";
import HotspotRanking from "../components/area1-signal-scan/HotspotRanking.jsx";
import VisitorProfileCard from "../components/area1-signal-scan/VisitorProfileCard.jsx";

const STAGE_NAMES = { 관심: "온라인 관심", 의도: "방문지 검색", 실현: "실제 방문" };
const dateLabel = (date) => date?.replaceAll("-", ".") ?? "기준일 미제공";

function signalValue(value, unit, missingReason) {
  if (Number.isFinite(value)) return `${value.toLocaleString("ko-KR")}${unit ?? ""}`;
  // 왜 비었는지가 "자료 없음"보다 훨씬 쓸모 있다. 데이터에 사유가 있으면 그걸 쓴다.
  return missingReason ?? "자료 없음";
}

// 누적 조회수는 자릿수가 커서 그대로 쓰면 칸을 넘긴다. 만 단위로 접는다.
function compactViews(value) {
  if (!Number.isFinite(value)) return null;
  return value >= 10000 ? `${Math.round(value / 10000).toLocaleString("ko-KR")}만회` : `${value.toLocaleString("ko-KR")}회`;
}

function SignalEvidence({ envelope }) {
  const data = envelope.data;
  const signals = data.cross_validation ?? [];
  if (!signals.length) return <p className="regional-empty">이 지역은 교차검증 자료가 없습니다.</p>;
  return <>
    <div className="analysis-evidence-lead">
      <div>
        <span>월별 경보 판정 · {dateLabel(data.as_of)}</span>
        <strong>{data.alert_level} 단계</strong>
        {data.previous_alert_level && data.previous_alert_level !== data.alert_level
          && <span>직전 {data.previous_alert_level} → {data.alert_level}</span>}
      </div>
      <p>독립 지표 {data.agreement?.total ?? signals.length}개 중 {data.agreement?.exceeded_count ?? signals.filter((signal) => signal.exceeded).length}개가 기준을 넘었습니다.</p>
    </div>
    <div className="analysis-signal-list">
      {signals.map((signal) => <div key={signal.stage}>
        <div><span className="analysis-signal-stage">{STAGE_NAMES[signal.stage] ?? signal.stage}</span><strong>{signal.exceeded ? "증가 신호" : signal.value == null ? "자료 없음" : "기준 미만"}</strong></div>
        <p>{signal.signal}</p>
        <small>관측 {signalValue(signal.value, signal.unit, signal.missing_reason)} · 기준 {signalValue(signal.threshold, signal.unit)}{signal.trend ? ` · ${signal.trend}` : ""}</small>
        {signal.provider && <small>출처 {signal.provider}</small>}
      </div>)}
    </div>
    <EscalationNote data={data} />
    <SourceBadge envelope={envelope} />
    <CaveatNote envelope={envelope} />
  </>;
}

// 경보가 어떻게 올라가고 내려가는지는 데이터가 이미 문장으로 들고 있다(escalation.note,
// D-05 원문). 규칙을 화면에 새로 쓰지 않고 그대로 인용한다.
function EscalationNote({ data }) {
  const escalation = data.escalation;
  if (!escalation && !data.basis && !data.manual_ref) return null;
  return <details className="compact-details">
    <summary>이 단계는 어떻게 정해졌나요?</summary>
    {data.basis && <p>{data.basis}</p>}
    {escalation && <p>
      다음 단계는 {escalation.next_level}입니다 — 독립 지표 {escalation.required_exceeded}개가 기준을 넘어야 하고,
      지금은 {escalation.current_exceeded}개로 {escalation.met ? "조건을 채웠습니다" : "아직 미치지 않습니다"}.
    </p>}
    {escalation?.note && <p>{escalation.note}</p>}
    <ManualRefCite manualRef={data.manual_ref} />
  </details>;
}

function ContentBreakdown({ envelope, recent, zoneSource }) {
  const rows = (envelope.data.summary ?? []).slice().sort((a, b) => b.count - a.count);
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  return <>
    <p className="analysis-data-date">{recent ? `${dateLabel(envelope.period?.start)}~${dateLabel(envelope.period?.end)} 게시 · 제목 기준 분류` : `${dateLabel(envelope.period?.end)}까지 분류`} · 관광 관련 영상 {total.toLocaleString("ko-KR")}건</p>
    <ol className="analysis-type-list">
      {rows.map((row) => <li key={row.content_type}>
        <span>{row.content_type}</span>
        <div className="analysis-type-track"><span style={{ width: `${Math.max(2, row.ratio * 100)}%` }} /></div>
        <strong>{row.count}건</strong>
        <small>{(row.ratio * 100).toFixed(1)}%{compactViews(row.total_views) && <><br />조회 {compactViews(row.total_views)}</>}</small>
      </li>)}
    </ol>
    {!rows.length && <p className="regional-empty">분류된 콘텐츠가 없습니다.</p>}
    <ZoneSignalSummary data={zoneSource} />
    <SourceBadge envelope={envelope} />
    <CaveatNote envelope={envelope} />
  </>;
}

// 분류에서 빠진 건수와 핫존/데드존 집계. 셋 다 데이터에는 있는데 화면이 없었다.
function ZoneSignalSummary({ data }) {
  if (!data) return null;
  const zones = data.zone_signals;
  const excluded = data.unclassified_count;
  // 0건뿐이면 줄을 만들지 않는다 -- "제외 0건"만 떠 있으면 잡음이다.
  if (!zones && !excluded) return null;
  const deadZonePois = zones?.["데드존_지점"] ?? [];
  return <p className="analysis-data-date">
    {excluded > 0 && `관광과 무관해 분류에서 제외 ${excluded.toLocaleString("ko-KR")}건`}
    {zones && `${excluded > 0 ? " · " : ""}핫존 신호 ${zones["핫존"] ?? 0}건 · 데드존 신호 ${zones["데드존"] ?? 0}건`}
    {deadZonePois.length > 0 && ` · 분산 후보지 ${deadZonePois.join(", ")}`}
  </p>;
}

export default function AreaDeepAnalysis({ region }) {
  const signalStatus = useRegionData("signal_status", region);
  const hotspots = useRegionData("hotspots", region);
  const visitorProfile = useRegionData("visitor_profile", region);
  const contentType = useRegionData("content_type", region);
  const recentContentType = useRegionData("recent_content_type", region);
  const contentAnalysis = recentContentType.status === "unsupported" ? contentType : recentContentType;
  // 분산 후보지(데드존) 칩은 content_type 계약에만 있다. HotspotRanking은 이 prop을
  // 받도록 돼 있었는데 아무도 넘기지 않아 칩이 한 번도 뜨지 않았다.
  // recent_content_type에는 zone_signals가 없으므로 원본 content_type에서만 읽는다.
  const deadZonePois = contentType.status === "ok"
    ? contentType.envelope.data.zone_signals?.["데드존_지점"] ?? []
    : [];

  return <div className="deep-analysis-body">
    <section className="analysis-report-block" id="signal-evidence">
      <div className="analysis-block-heading"><span>01 · 신호 근거</span><h3>경보는 어떤 자료로 판정했나요?</h3><p>월별 경보를 만드는 세 지표의 관측값과 기준을 나란히 확인합니다.</p></div>
      <DataState result={signalStatus} render={({ envelope }) => <SignalEvidence envelope={envelope} />} />
    </section>

    {(hotspots.status !== "unsupported" || visitorProfile.status !== "unsupported") && <div className="analysis-report-pair">
      {hotspots.status !== "unsupported" && <section className="analysis-report-block" id="place-analysis">
        <div className="analysis-block-heading"><h3>어느 관광지로 몰렸나요?</h3><p>상위 관광지의 입장객, 전년 대비 변화와 장소 특성을 봅니다.</p></div>
        <DataState result={hotspots} render={({ envelope }) => <><p className="analysis-data-date">{dateLabel(envelope.period?.end)} 월별 입장객</p><HotspotRanking hotspotsData={envelope.data} deadZonePois={deadZonePois} /><SourceBadge envelope={envelope} /></>} />
      </section>}
      {visitorProfile.status !== "unsupported" && <section className="analysis-report-block" id="audience-analysis">
        <div className="analysis-block-heading"><h3>누가 방문했나요?</h3><p>거주지, 이동 거리, 소비와 동행 유형의 분포를 확인합니다.</p></div>
        <DataState result={visitorProfile} render={({ envelope }) => <><p className="analysis-data-date">{dateLabel(envelope.period?.end)} 방문객 구성</p><VisitorProfileCard profileData={envelope.data} /><SourceBadge envelope={envelope} /></>} />
      </section>}
    </div>}

    {contentAnalysis.status !== "unsupported" && <section className="analysis-report-block" id="content-analysis">
      <div className="analysis-block-heading"><span>04 · 콘텐츠</span><h3>어떤 콘텐츠가 관심을 모았나요?</h3><p>관광 관련 영상의 유형을 집계해 방문 흐름과 함께 살펴봅니다.</p></div>
      <DataState result={contentAnalysis} render={({ envelope }) => <ContentBreakdown envelope={envelope} recent={contentAnalysis === recentContentType} zoneSource={contentType.status === "ok" ? contentType.envelope.data : null} />} />
    </section>}
  </div>;
}
