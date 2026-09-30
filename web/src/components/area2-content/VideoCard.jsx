import { contentRelevance } from "../../lib/contentRelevance.js";

// 분류 근거·감성·신뢰도·지점 신호는 content_type 계약에 있는데 카드가 읽지 않았다.
// ui 카드 디자인은 그대로 두고 접기 하나만 덧붙인다.
function ClassificationBasis({ item, places }) {
  const hasConfidence = Number.isFinite(item.confidence);
  if (!item.evidence && !item.sentiment && !hasConfidence && !item.zone_signal && places.length <= 2) return null;
  return (
    <details className="compact-details">
      <summary>분류 근거</summary>
      <p>
        {item.content_type ?? "유형 미분류"}
        {hasConfidence && ` · 분류 신뢰도 ${Math.round(item.confidence * 100)}%`}
        {item.zone_signal && <span className="dept-chip">{item.zone_signal === "데드존" ? "데드존 · 분산 후보" : item.zone_signal}</span>}
      </p>
      {item.evidence && <p>근거 · {item.evidence}</p>}
      {item.sentiment && <p>감성 · {item.sentiment}</p>}
      {places.length > 0 && <p>언급 장소 · {places.join(", ")}</p>}
    </details>
  );
}

export default function VideoCard({ item, regionName }) {
  const relevance = contentRelevance(item, regionName);
  const allPlaces = [...new Set(item.poi_mentioned ?? [])];
  const places = allPlaces.slice(0, 2);
  const hasDescription = typeof item.description === "string" && item.description.trim().length > 0;
  const hasTags = relevance.tags.length > 0;
  const description = hasDescription ? item.description : places.length
    ? `${places.join(" · ")}의 여행 포인트를 소개하는 영상입니다.`
    : "지역 여행의 볼거리와 분위기를 소개하는 콘텐츠 예시입니다.";
  const tags = hasTags ? relevance.tags : [...new Set([...places, item.content_type].filter(Boolean))];
  const mock = !hasDescription || !hasTags;
  return (
    <article className="content-video-card content-feed-card">
      <div className="content-feed-date"><span>{item.published_at ?? "게시일 미제공"}</span><span>{Number.isFinite(item.view_count) ? `${item.view_count.toLocaleString("ko-KR")}회` : "조회수 미제공"}</span></div>
      <h3>{/^[\w-]{11}$/.test(item.video_id) ? <a href={`https://www.youtube.com/watch?v=${item.video_id}`} target="_blank" rel="noreferrer">{item.title}<span className="sr-only"> (새 탭)</span></a> : item.title}</h3>
      <p className="content-feed-channel">{item.channel ?? "채널 미제공"}</p>
      <p className="content-feed-description" title={description}>{description}</p>
      <div className="content-feed-tags">{tags.slice(0, 3).map((tag) => <span key={tag}>#{tag.replace(/^#/, "")}</span>)}</div>
      {mock && <p className="content-feed-mock">{!hasDescription && !hasTags ? "설명·태그 목업" : !hasDescription ? "설명 목업" : "태그 목업"} · 원문 연결 예정</p>}
      {!relevance.confirmed && <p className="content-feed-mock">{relevance.label}</p>}
      <ClassificationBasis item={item} places={allPlaces} />
    </article>
  );
}
