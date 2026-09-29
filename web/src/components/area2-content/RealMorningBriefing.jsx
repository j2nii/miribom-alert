import { buildContentBriefing } from "../../lib/contentBriefing.js";
import DataState from "../common/DataState.jsx";
import SourceBadge from "../common/SourceBadge.jsx";
import DailySearchSummary from "./DailySearchSummary.jsx";

const formatDate = (date) => date?.replaceAll("-", ".") ?? "미제공";

export default function RealMorningBriefing({ region, signalStatus, signalSeries, contentType, recentYoutube }) {
  const envelope = contentType.envelope;
  const liveEnvelope = recentYoutube.status === "ok" ? recentYoutube.envelope : null;
  const isRecentFeed = Boolean(liveEnvelope?.data?.videos);
  const briefing = liveEnvelope?.data?.videos
    ? { end: liveEnvelope.period?.end, recentVideos: liveEnvelope.data.videos }
    : buildContentBriefing(envelope);
  if (!briefing) return null;
  return <section className="morning-briefing" aria-label="유튜브와 네이버 지역 보고서">
    <p className="report-intro">최근 게시 영상과 월별 검색 흐름을 각 자료의 기준일에 맞춰 확인하세요.</p>
    <div className="report-evidence-grid">
      <section className="report-evidence youtube-video-report" aria-label="최근 7일 게시 영상">
        <h3 className="report-channel">유튜브 · 최근 영상</h3>
        <div className="morning-meta"><span>게시 기준 {formatDate(briefing.end)}</span></div>
        <div className="youtube-recent-total"><span>{isRecentFeed ? "최근 7일 인기 영상 · 조회수 순" : "최근 7일 게시 영상"}</span><strong>{briefing.recentVideos.length}<small>건</small></strong></div>
        {briefing.recentVideos.length ? <div className="youtube-video-list-wrap"><ul className="youtube-recent-videos" aria-label={isRecentFeed ? "최근 7일 인기 영상, 누적 조회수 순" : "최근 7일 게시 영상, 최신순"}>
          {briefing.recentVideos.map((video) => {
            const validId = /^[\w-]{11}$/.test(video.video_id ?? "");
            const details = <>
              <span className="youtube-recent-video-meta"><time dateTime={video.published_at}>{formatDate(video.published_at)}</time>{video.content_type ? ` · ${video.content_type}` : ""}{isRecentFeed && <span className="youtube-recent-video-views">조회수 {Number(video.view_count).toLocaleString("ko-KR")}회</span>}</span>
              <strong>{video.title}</strong>
              <span className="youtube-recent-video-channel">{video.channel}</span>
            </>;
            return <li key={video.video_id}>
              {validId ? <a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noopener noreferrer">
                <img src={`https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`} alt="" loading="lazy" />
                <span className="youtube-recent-video-details">{details}<span className="sr-only"> (새 탭)</span></span>
              </a> : <div className="youtube-recent-video-details">{details}</div>}
            </li>;
          })}
        </ul>{briefing.recentVideos.length > 3 && <span className="youtube-list-status" aria-hidden="true">목록 안에서 스크롤 ↓</span>}</div> : <p className="morning-window">최근 7일에 게시된 지역 관련 영상이 없습니다.</p>}
      </section>
      <DailySearchSummary signalSeries={signalSeries} />
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
  </section>;
}
