import SourceBadge from "../common/SourceBadge.jsx";
import InterestChart from "./InterestChart.jsx";
import { summarizeSignals, selectRegionalVideos } from "../../lib/regionSummary.js";

const SIGNAL_LABELS = [
  ["관심", "온라인 관심", "SNS에서 지역을 언급하는 흐름"],
  ["의도", "방문지 검색", "내비게이션에서 목적지를 찾는 흐름"],
  ["실현", "실제 방문", "외지인 방문자 수의 변화"],
];

export default function RegionSummary({ envelope, contentResult, timelineResult, regionLabel }) {
  const data = envelope.data;
  const summary = summarizeSignals(data);
  const content = contentResult.status === "ok" ? contentResult.envelope : null;
  const videos = selectRegionalVideos(content, 2, regionLabel);
  const date = data.as_of ?? envelope.period?.end;

  return (
    <div className="region-summary">
      <div className="region-summary-meta">
        <span>{envelope._mock ? "예시 데이터" : "수집 데이터 기준"} · {date ?? "기준일 미제공"}</span>
        {data.alert_level && <span className="summary-alert">분석 경보: {data.alert_level}</span>}
      </div>
      <div className="summary-lead">
        <p className="summary-eyebrow">우리 지역, 어떤 상황인가요?</p>
        <h3>{summary.headline}</h3>
        <p>{summary.description}</p>
      </div>
      {data.alert_level && <div className="summary-signals">
        {SIGNAL_LABELS.map(([stage, label, help]) => {
          const signal = data.cross_validation?.find((item) => item.stage === stage);
          const known = typeof signal?.exceeded === "boolean";
          return <div key={stage} className={`summary-signal${signal?.exceeded ? " is-detected" : ""}`}>
            <span>{label}</span>
            <strong>{!known ? "자료 확인 필요" : signal.exceeded ? "증가 신호 감지" : "감지 기준 미만"}</strong>
            <small>{help}</small>
          </div>;
        })}
      </div>}
      <SourceBadge envelope={envelope} />
      <InterestChart signalEnvelope={envelope} timelineResult={timelineResult} />

      <div className="summary-work-grid">
        <section className="summary-content" aria-labelledby="summary-content-heading">
          <div className="summary-section-head"><h3 id="summary-content-heading">어떤 콘텐츠를 봐야 할까요?</h3><a href="#area2">전체 보기 →</a></div>
          {content && <p className="summary-caption">{content._mock ? "예시 영상" : "수집한 지역 관련 영상 중 조회수 상위"} · 게시 기간 {content.period?.start ?? "미제공"} ~ {content.period?.end ?? "미제공"}</p>}
          {videos.map((video) => <article className="summary-video" key={video.video_id}>
            <div className="summary-video-meta"><span>{video.content_type}</span><span>{Number.isFinite(video.view_count) ? `${video.view_count.toLocaleString("ko-KR")}회 조회` : "조회수 미제공"}</span></div>
            <h4>{!content._mock && /^[\w-]{11}$/.test(video.video_id) ? <a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noreferrer">{video.title}<span className="sr-only"> (새 탭)</span> ↗</a> : video.title}</h4>
            <p>{video.channel} · 게시 {video.published_at ?? "일자 미제공"}</p>
          </article>)}
          {!videos.length && <p className="summary-empty">{contentResult.status === "loading" ? "지역 관련 영상을 확인하고 있습니다…" : contentResult.status === "error" ? "영상 자료를 불러오지 못했습니다. 아래 콘텐츠 분석에서 상태를 확인해 주세요." : contentResult.status === "unsupported" ? "이 지역의 영상 자료는 아직 준비되지 않았습니다." : "수집 자료에서 소개할 지역 관련 영상을 찾지 못했습니다."}</p>}
          {content && <SourceBadge envelope={content} />}
        </section>
        <section className="summary-actions" aria-labelledby="summary-actions-heading">
          <div className="summary-section-head"><h3 id="summary-actions-heading">담당자는 무엇부터 하면 될까요?</h3></div>
          <p className="summary-caption">현장 확인 전, 먼저 살펴볼 업무입니다.</p>
          <a href="#area2"><span className="summary-action-number">1</span><div><strong>영상 속 장소와 내용을 확인하세요</strong><p>우리 지역의 어떤 장소·먹거리가 소개됐는지 확인</p></div><span aria-hidden="true">→</span></a>
          <a href="#area1"><span className="summary-action-number">2</span><div><strong>방문 흐름과 현장 문의를 대조하세요</strong><p>관광지별 자료를 살펴보고 현장 담당자에게 확인</p></div><span aria-hidden="true">→</span></a>
          <a href="#area3"><span className="summary-action-number">3</span><div><strong>관광 안내와 대응 항목을 점검하세요</strong><p>운영시간·교통·주차 안내와 대응 체크리스트 확인</p></div><span aria-hidden="true">→</span></a>
        </section>
      </div>
    </div>
  );
}
