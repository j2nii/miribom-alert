import { useState } from "react";
import VideoCard from "./VideoCard.jsx";
import { contentRelevance } from "../../lib/contentRelevance.js";

export default function UploadVideoList({ contentTypeData }) {
  const [showAll, setShowAll] = useState(false);
  const [includeOther, setIncludeOther] = useState(false);
  const regionName = contentTypeData.region?.name ?? "";
  const orderedItems = contentTypeData.items
    .filter((item) => includeOther || contentRelevance(item, regionName).confirmed)
    .slice().sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? "") || a.video_id.localeCompare(b.video_id));
  const groups = Object.values(orderedItems.reduce((result, item) => {
    const place = item.poi_mentioned?.[0] || "지역 전반";
    const key = `place:${place.replace(/\s/g, "").replace(/오일장/g, "5일장")}`;
    result[key] ??= { place, items: [] };
    result[key].items.push(item);
    return result;
  }, {}));

  return (
    <div>
          <div className="content-feed-toolbar"><span>수집 자료 내 최신순</span><label><input type="checkbox" checked={includeOther} onChange={(e) => { setIncludeOther(e.target.checked); setShowAll(false); }} />전체 수집 영상</label></div>
          <p className="content-evidence-caption">{includeOther ? "전체 수집 영상" : "지역명 언급이 확인된 영상"} · 대표 언급 장소별 묶음 · 묶음별 최신 영상 먼저</p>
          <div className="content-feed-grid">{(showAll ? groups : groups.slice(0, 3)).map((group) => (
            <section className="content-topic" key={group.place}>
              <h3 className="content-topic-title">{group.place}<small>{group.items.length}개 영상</small></h3>
              {(showAll ? group.items : group.items.slice(0, 1)).map((item) => <VideoCard key={item.video_id} item={item} regionName={regionName} />)}
            </section>
          ))}</div>
          {!orderedItems.length && <p className="content-evidence-caption">지역명이 확인된 영상이 없습니다. 전체 수집 영상을 확인해 주세요.</p>}
          {orderedItems.length > Math.min(groups.length, 3) && <button type="button" className="footer-link-btn" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>{showAll ? "접기" : `수집 영상 전체 보기 (${orderedItems.length}건)`}</button>}
    </div>
  );
}
