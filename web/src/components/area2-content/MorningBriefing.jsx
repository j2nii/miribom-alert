import { MORNING_BRIEFINGS } from "../../data/morningBriefing.js";
import DataState from "../common/DataState.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import DailySearchSummary from "./DailySearchSummary.jsx";
import RealMorningBriefing from "./RealMorningBriefing.jsx";

export default function MorningBriefing({ region, signalStatus, signalSeries, contentType, recentYoutube }) {
  if (region !== "chungju") {
    if (contentType.status !== "ok" || contentType.envelope._mock) return null;
    if (recentYoutube.status === "loading") return null;
    return <RealMorningBriefing region={region} signalStatus={signalStatus} signalSeries={signalSeries} contentType={contentType} recentYoutube={recentYoutube} />;
  }
  const briefing = MORNING_BRIEFINGS[region];
  if (!briefing) return null;
  return <section className="morning-briefing" aria-label="유튜브와 네이버 지역 보고서">
    <p className="report-intro">새 영상과 월별 검색 흐름을 함께 확인하세요.</p>
    <div className="report-evidence-grid">
    <section className="report-evidence" aria-label="유튜브 게시 변화 예시">
    <h3 className="report-channel">유튜브 · 새 영상</h3>
    <div className="morning-meta"><span>목업</span><span>예시 수집 2026.09.27 08:00 KST</span></div>
    <h3>{briefing.headline}</h3>
    <div className="youtube-comparison" aria-label="유튜브 게시 수 비교">
      {[
        { label: "지난 24시간", value: briefing.published },
        { label: "직전 24시간", value: briefing.previous },
        { label: "이전 7일 일평균", value: briefing.average },
      ].map((item, index) => <div className="youtube-comparison-row" key={item.label}>
        <div><span>{item.label}</span><strong>{item.value}<small>건</small></strong></div>
        <div className="youtube-comparison-track" aria-hidden="true"><span className={index === 0 ? "is-current" : ""} style={{ width: `${item.value / Math.max(briefing.published, briefing.previous, briefing.average, 1) * 100}%` }} /></div>
      </div>)}
    </div>
    <p className="morning-window">게시 기준 09/26 08:00~09/27 08:00 · 뒤늦게 발견한 이전 영상 {briefing.discoveredOlder}건은 제외</p>
    </section>
    <DailySearchSummary />
    </div>
    <p className="report-comparison-note">유튜브 게시 변화는 목업이며, 월별 검색 자료는 아직 연결되지 않았습니다.</p>
    <details className="compact-details report-monthly" key={`sns-${region}`}>
    <summary>SNS 언급량 · 월별 참고자료</summary>
    <section className="report-evidence" aria-label="SNS 언급량 지표">
      <h3 className="report-channel">SNS · 언급량 변화</h3>
      <DataState result={signalStatus} render={({ envelope }) => {
        const sns = envelope.data.cross_validation?.find(signal => signal.signal?.includes("SNS 언급량"));
        if (!sns) return <p className="report-intro">비교 가능한 SNS 월별 지표가 아직 연결되지 않았습니다.</p>;
        return <>
          <div className="morning-meta"><span className="report-observed">{envelope._mock ? "목업" : "실측 기반"} · 월별 참고</span><span>기준 {envelope.data.as_of ?? envelope.period?.end ?? "미제공"}</span></div>
          <h3>{sns.exceeded ? "SNS 증가 기준을 넘었어요" : "SNS 증가 기준 미만이에요"}</h3>
          <div className="report-sns-value"><strong>{sns.value > 0 ? "+" : ""}{sns.value}<small>{sns.unit}</small></strong><span>판정 기준 {sns.threshold}{sns.unit}</span></div>
          <p className="morning-window">전년 동월 대비 언급량 증가율에서 전국 중앙값을 뺀 값입니다. 언급 건수나 오늘의 증감률은 아닙니다.</p>
          <SourceBadge envelope={envelope} />
        </>;
      }} />
    </section>
    </details>
    <div className="report-topics-heading"><h3>어떤 이야기가 늘었나요?</h3><span>유튜브 주제·수치·영상 제목은 예시</span></div>
    <div className="morning-topics">
      {briefing.topics.map(topic => <article className="morning-topic" key={topic.name}>
        <div className="morning-topic-meta"><span>{topic.count > topic.previous ? "게시 증가" : topic.count < topic.previous ? "게시 감소" : "변화 없음"}</span><span>전일 {topic.previous}건 → <strong>{topic.count}건</strong></span></div>
        <h4>{topic.name}</h4>
        <p className="morning-action"><b>확인할 일</b> {topic.action}</p>
        <p className="morning-video-label">대표 영상 · 가상 제목</p>
        <ul>{topic.videos.map(title => <li key={title}>{title}</li>)}</ul>
      </article>)}
    </div>
    <p className="morning-window">영상 게시 수의 변화입니다. 조회수 확산이나 실제 방문 증가를 뜻하지 않습니다.</p>
  </section>;
}
