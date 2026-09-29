import { useRegionData } from "../hooks/useRegionData.js";
import { summarizeVisitorSignal } from "../lib/visitorSignal.js";
import DataState from "../components/common/DataState.jsx";
import SourceBadge from "../components/common/SourceBadge.jsx";
import CaveatNote from "../components/common/CaveatNote.jsx";
import AreaTrendForecast from "./AreaTrendForecast.jsx";

const number = new Intl.NumberFormat("ko-KR");
const dateLabel = (date) => date ? date.replaceAll("-", ".") : "기준일 미제공";

function VisitorSignal({ envelope }) {
  const { latest, detected, weekChange, threshold, duration } = summarizeVisitorSignal(envelope.data);
  const status = detected == null ? "판단 자료 확인 중" : detected ? "방문자 증가 신호 감지" : "방문 증가 신호 없음";
  return <>
    <div className={`regional-visitor-signal${detected ? " is-detected" : ""}`}>
      <div className="regional-signal-lead">
        <span>실측 방문 · {dateLabel(latest?.date)} 기준</span>
        <strong>{status}</strong>
        <p>{detected == null ? "방문 증가 여부를 판단할 자료를 확인하고 있습니다." : detected ? "방문 지표가 감지 기준을 연속으로 넘었습니다." : "현재 실측 방문은 평소 수준입니다."}</p>
      </div>
      <div className="regional-signal-facts">
        <div><span>최근 일별 방문</span><strong>{latest ? `${number.format(latest.visitors)}명` : "—"}</strong></div>
        <div><span>직전 7일 대비</span><strong>{weekChange == null ? "—" : `${weekChange > 0 ? "+" : ""}${weekChange.toFixed(1)}%`}</strong></div>
        <div><span>증가 신호</span><strong>{detected == null ? "확인 중" : detected ? "감지" : "평소 수준"}</strong></div>
      </div>
    </div>
    {Number.isFinite(threshold) && <p className="regional-signal-method">전년 같은 요일 대비 방문 배율의 7일 중앙값이 {threshold}배를 {duration}일 연속 넘으면 증가 신호로 표시합니다.</p>}
    <SourceBadge envelope={envelope} />
    <CaveatNote envelope={envelope} />
  </>;
}

function TopHotspots({ envelope }) {
  const ranking = (envelope.data.ranking ?? []).slice().sort((a, b) => a.rank - b.rank).slice(0, 3);
  return <>
    <p className="regional-data-period">{dateLabel(envelope.period?.end)} 월별 입장객</p>
    <ol className="regional-top-list">
      {ranking.map((place) => <li key={place.rank}>
        <span className="regional-rank">{place.rank}</span>
        <strong>{place.poi_name}</strong>
        <span>{number.format(place.visitors)}명</span>
      </li>)}
    </ol>
    {!ranking.length && <p className="regional-empty">표시할 관광지 자료가 없습니다.</p>}
    <SourceBadge envelope={envelope} />
    <CaveatNote envelope={envelope} />
  </>;
}

function TopProfile({ envelope }) {
  const data = envelope.data;
  const categories = [
    { label: "주요 연령·성별", rows: data.gender_age, name: (row) => `${row.gender} ${row.age_band}` },
    { label: "주요 이동 거리", rows: data.distance, name: (row) => row.band },
    { label: "주요 동행 유형", rows: data.companion, name: (row) => row.type },
  ];
  return <>
    <p className="regional-data-period">{dateLabel(envelope.period?.start)} ~ {dateLabel(envelope.period?.end)} · 방문객 비중</p>
    <div className="regional-profile-list">
      {categories.map(({ label, rows, name }) => {
        const top = (rows ?? []).filter((row) => Number.isFinite(row.ratio)).slice().sort((a, b) => b.ratio - a.ratio)[0];
        return <div key={label}>
          <span>{label}</span>
          <strong>{top ? name(top) : "자료 없음"}</strong>
          <b>{top ? `${(top.ratio * 100).toFixed(1)}%` : "—"}</b>
        </div>;
      })}
    </div>
    <SourceBadge envelope={envelope} />
    <CaveatNote envelope={envelope} />
  </>;
}

export default function Area1SignalScan({ region }) {
  const signalSeries = useRegionData("signal_series", region);
  const hotspots = useRegionData("hotspots", region);
  const visitorProfile = useRegionData("visitor_profile", region);

  return <>
    <div className="panel-head"><h2>방문 흐름과 지역 현황</h2></div>
    <section className="section-block" aria-labelledby="visitor-signal-title">
      <div className="regional-section-head">
        <div><span className="regional-step">01 · 지금</span><h3 id="visitor-signal-title">방문자 증가 신호</h3></div>
        <p>방문 실측으로 현재 변화를 확인합니다.</p>
      </div>
      <DataState result={signalSeries} render={({ envelope }) => <VisitorSignal envelope={envelope} />} />
    </section>

    <div className="regional-top-grid">
      {hotspots.status !== "unsupported" && <section className="section-block" aria-labelledby="hotspots-title">
        <div className="regional-section-head"><div><h3 id="hotspots-title">인기 관광지 상위</h3></div></div>
        <DataState result={hotspots} render={({ envelope }) => <TopHotspots envelope={envelope} />} />
      </section>}
      {visitorProfile.status !== "unsupported" && <section className="section-block" aria-labelledby="visitor-profile-title">
        <div className="regional-section-head"><div><h3 id="visitor-profile-title">방문객 구성 상위</h3></div></div>
        <DataState result={visitorProfile} render={({ envelope }) => <TopProfile envelope={envelope} />} />
      </section>}
    </div>

    <AreaTrendForecast region={region} />
  </>;
}
