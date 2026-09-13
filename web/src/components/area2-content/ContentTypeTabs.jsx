import { useState } from "react";
import VideoCard from "./VideoCard.jsx";
import ContentTypeSummary from "./ContentTypeSummary.jsx";

const TABS = [
  { key: "youtube", label: "유튜브" },
  { key: "sns", label: "SNS 언급량" },
  { key: "places", label: "실제 검색 장소" },
  { key: "summary", label: "콘텐츠 유형 요약" },
];

export default function ContentTypeTabs({ contentTypeData, crossValidationSignals, hotspotsData }) {
  const [tab, setTab] = useState("youtube");
  const [selectedId, setSelectedId] = useState(null);

  return (
    <div>
      <div className="tab-switch">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={"tab-btn" + (tab === t.key ? " is-active" : "")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "youtube" && (
        <div>
          {contentTypeData.items.map((item) => (
            <VideoCard
              key={item.video_id}
              item={item}
              selected={selectedId === item.video_id}
              onSelect={() => setSelectedId(selectedId === item.video_id ? null : item.video_id)}
            />
          ))}
        </div>
      )}

      {tab === "sns" && (
        <div>
          <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 8 }}>
            AREA 0/1의 3중 교차검증에 쓰이는 신호 중 SNS·언급량 계열만 다시 보여줍니다(별도 지점별 세분화
            데이터는 아직 스키마에 없음).
          </p>
          {crossValidationSignals
            ?.filter((s) => s.signal.includes("유튜브") || s.signal.includes("언급"))
            .map((s, i) => (
              <div key={i} style={{ fontSize: 13, marginBottom: 6 }}>
                {s.signal}: {s.value}
                {s.unit} (임계 {s.threshold}
                {s.unit}, {s.exceeded ? "초과" : "미달"})
              </div>
            ))}
        </div>
      )}

      {tab === "places" && (
        <div>
          <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 8 }}>
            검색 의도 기준 장소별 세분화 데이터는 아직 없어, 방문 기준 랭킹(AREA 1 인기 관광지)으로 대신
            표시합니다.
          </p>
          {hotspotsData?.ranking.slice(0, 5).map((p) => (
            <div key={p.rank} style={{ fontSize: 13, marginBottom: 4 }}>
              {p.rank}. {p.poi_name} — {p.visitors.toLocaleString()}명
            </div>
          ))}
        </div>
      )}

      {tab === "summary" && <ContentTypeSummary data={contentTypeData} />}
    </div>
  );
}
