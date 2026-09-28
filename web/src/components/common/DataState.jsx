// Shared loading/error/unsupported rendering for a useRegionData() result.
// Pass a render function that receives { envelope, kind } once status "ok".
const DATA_LABELS = {
  daily_peak: "일별 언급량",
  signal_status: "신호 상태",
  signal_series: "검색·방문 추이",
  forecast: "7일 방문 수요 예측",
  content_type: "콘텐츠 분석",
  checklist: "대응 체크리스트",
  precedent: "유사 선례",
  briefing: "상세 브리핑",
  before_after: "조치 전후 비교",
  hotspots: "관광지 자료",
  visitor_profile: "방문객 구성",
  timeline: "대응 기록",
};

export default function DataState({ result, render }) {
  if (result.status === "loading") {
    return <div className="loading-state">불러오는 중…</div>;
  }
  if (result.status === "unsupported") {
    return <div className="unsupported-state">이 지역의 {DATA_LABELS[result.dataType] ?? "해당"} 자료는 아직 준비되지 않았습니다.</div>;
  }
  if (result.status === "error") {
    return <div className="error-state">데이터를 불러오지 못했습니다 ({result.error}).</div>;
  }
  return render(result);
}
