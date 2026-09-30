// 없을 때 대신 볼 곳을 알려준다 -- 빈 화면만 보여주면 고장으로 오해한다.
const FALLBACK_HINT = {
  forecast: "지금 단계 판정은 AREA 0에서 볼 수 있습니다.",
  precedent: "대응 근거는 AREA 3의 체크리스트 매뉴얼 인용으로 확인하세요.",
  before_after: "리드타임은 같은 화면 위쪽에서 볼 수 있습니다.",
  briefing: "조치 목록은 AREA 3의 체크리스트에 그대로 있습니다.",
  checklist: "경보 단계와 판단 근거는 AREA 0·1에서 볼 수 있습니다.",
};

// Shared loading/error/unsupported rendering for a useRegionData() result.
// Pass a render function that receives { envelope, kind } once status "ok".
const DATA_LABELS = {
  daily_peak: "일별 언급량",
  signal_status: "신호 상태",
  signal_series: "검색·방문 추이",
  outlook: "6개월 방문객 전망",
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
    const label = DATA_LABELS[result.dataType] ?? result.dataType;
    // 전국 시군구(지역코드)는 기본 분석 지역이라 크롤링 기반 항목이 원래 없다 -- 고장이 아니라 범위 밖임을 알린다
    const hint = /^\d{5}$/.test(result.region ?? "")
      ? "심층 분석 항목이라 이 지역은 준비 중입니다. 지금은 영월·거제·여수·속초·인제·울릉 6곳에서 볼 수 있습니다."
      : FALLBACK_HINT[result.dataType];
    return (
      <div className="unsupported-state">
        <strong>이 지역은 아직 {label} 데이터가 없습니다.</strong>
        {hint && <span className="unsupported-state__hint">{hint}</span>}
      </div>
    );
  }
  if (result.status === "error") {
    return <div className="error-state">데이터를 불러오지 못했습니다 ({result.error}).</div>;
  }
  return render(result);
}
