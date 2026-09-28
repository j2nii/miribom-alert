import { buildContentBriefing } from "../../lib/contentBriefing.js";
import DataState from "../common/DataState.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import DailySearchSummary from "./DailySearchSummary.jsx";

const formatDate = (date) => date?.replaceAll("-", ".") ?? "미제공";

export default function RealMorningBriefing({ region, signalStatus, signalSeries, contentType }) {
  const envelope = contentType.envelope;
  const briefing = buildContentBriefing(envelope);
  if (!briefing) return null;
  const comparisons = [
    { label: "기준일 게시", value: briefing.today },
    { label: "전일 게시", value: briefing.previous },
    { label: "이전 7일 일평균", value: briefing.previousAverage },
  ];
  const max = Math.max(...comparisons.map((item) => item.value), 1);

  return <section className="morning-briefing" aria-label="유튜브와 네이버 지역 보고서">
    <p className="report-intro">분류된 영상과 일별 검색 흐름을 각 자료의 기준일에 맞춰 확인하세요.</p>
    <div className="report-evidence-grid">
      <section className="report-evidence" aria-label="분류 영상 게시일 분포">
        <h3 className="report-channel">유튜브 · 분류 영상</h3>
        <div className="morning-meta"><span className="report-observed">수집 자료</span><span>게시 기준 {formatDate(briefing.end)}</span></div>
        <h3>기준일 분류 영상 {briefing.today}건</h3>
        <div className="youtube-comparison" aria-label="분류 대상 영상의 게시일별 건수">
          {comparisons.map((item, index) => <div className="youtube-comparison-row" key={item.label}>
            <div><span>{item.label}</span><strong>{Number.isInteger(item.value) ? item.value : item.value.toFixed(1)}<small>건</small></strong></div>
            <div className="youtube-comparison-track" aria-hidden="true"><span className={index === 0 ? "is-current" : ""} style={{ width: `${item.value / max * 100}%` }} /></div>
          </div>)}
        </div>
        <p className="morning-window">지역 관련 분류 영상 {briefing.total}건의 게시일을 집계했습니다.</p>
      </section>
      <DailySearchSummary region={region} signalSeries={signalSeries} />
    </div>
    <details className="compact-details report-monthly" key={`sns-${region}`}>
      <summary>SNS 언급량 · 월별 참고자료</summary>
      <section className="report-evidence" aria-label="SNS 언급량 지표">
        <h3 className="report-channel">SNS · 언급량 변화</h3>
        <DataState result={signalStatus} render={({ envelope: statusEnvelope }) => {
          const sns = statusEnvelope.data.cross_validation?.find((signal) => signal.signal?.includes("SNS 언급량"));
          if (!sns) return <p className="report-intro">비교 가능한 SNS 월별 지표가 아직 연결되지 않았습니다.</p>;
          return <>
            <div className="morning-meta"><span className="report-observed">{statusEnvelope._mock ? "목업" : "실측 기반"} · 월별 참고</span><span>기준 {statusEnvelope.data.as_of ?? statusEnvelope.period?.end ?? "미제공"}</span></div>
            <h3>{sns.exceeded ? "SNS 증가 기준을 넘었어요" : "SNS 증가 기준 미만이에요"}</h3>
            <div className="report-sns-value"><strong>{sns.value > 0 ? "+" : ""}{sns.value}<small>{sns.unit}</small></strong><span>판정 기준 {sns.threshold}{sns.unit}</span></div>
            <p className="morning-window">전년 동월 대비 언급량 증가율에서 전국 중앙값을 뺀 값입니다. 오늘의 언급 건수는 아닙니다.</p>
            <SourceBadge envelope={statusEnvelope} />
          </>;
        }} />
      </section>
    </details>
    <div className="report-topics-heading"><h3>어떤 영상이 올라왔나요?</h3><span>지역 관련성이 확인된 분류 영상 · 최신순</span></div>
    <div className="morning-topics">
      {briefing.topics.map((topic) => {
        const latest = topic.items[0];
        return <article className="morning-topic" key={topic.name}>
          <div className="morning-topic-meta"><span>최근 게시 {formatDate(topic.latest)}</span><span>전체 분류 <strong>{topic.items.length}건</strong></span></div>
          <h4>{topic.name}</h4>
          <p className="morning-action"><b>분류 근거</b> {latest.evidence || "영상 제목과 지역 관련성을 확인했습니다."}</p>
          <p className="morning-video-label">최근 영상 · {latest.channel}</p>
          <ul><li><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(latest.video_id)}`} target="_blank" rel="noopener noreferrer">{latest.title}</a></li></ul>
        </article>;
      })}
    </div>
    {!briefing.topics.length && <p className="morning-window">지역 관련성이 확인된 영상이 없습니다. 업로드 영상 목록에서 전체 수집본을 확인해 주세요.</p>}
  </section>;
}
