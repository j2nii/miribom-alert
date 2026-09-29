import { useState } from "react";
import VideoCard from "./VideoCard.jsx";
import ContentTypeSummary from "./ContentTypeSummary.jsx";

// `substitute`: 이 탭 전용 데이터가 아직 스키마에 없어서 AREA1의 다른 계약을 끌어다 대신
// 보여주는 탭. 회색 본문 문장만으로 알리면 훑어보며 놓치고 "AREA2도 실측 수치"라고
// 오해하게 되므로(QA 피드백), 탭 버튼에 "준비 중" 배지를, 본문 머리에 경고 톤 박스를 둔다.
const TABS = [
  { key: "youtube", label: "유튜브" },
  { key: "sns", label: "SNS 언급량", substitute: true },
  { key: "places", label: "실제 검색 장소", substitute: true },
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
            {t.substitute && <span className="tab-btn__badge">준비 중</span>}
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
          <p className="substitute-note">
            <strong>전용 데이터 준비 중</strong> — 지점별로 세분화된 SNS 언급량 데이터는 아직 스키마에
            없습니다. AREA 0/1의 3중 교차검증에 쓰이는 신호 중 SNS·언급량 계열만 다시 보여줍니다.
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
          <p className="substitute-note">
            <strong>전용 데이터 준비 중</strong> — 검색 의도 기준 장소별 세분화 데이터가 없어, AREA 1의
            방문 기준 랭킹(인기 관광지)으로 대신 표시합니다. 검색량이 아니라 실제 방문자 수입니다.
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
