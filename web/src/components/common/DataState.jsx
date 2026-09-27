// 데이터 계약별 한글 이름. "이 지역은 before_after 데이터가 준비되지 않았습니다"처럼
// 스키마 이름을 그대로 보여주면 처음 온 담당자는 무엇이 없다는 건지 알 수 없다.
const DATA_LABELS = {
  signal_status: "신호 상태",
  forecast: "7일 방문객 예측",
  signal_series: "신호 추이",
  visitor_profile: "방문객 프로파일",
  hotspots: "인기 관광지 랭킹",
  content_type: "콘텐츠 유형 분류",
  checklist: "정책 대응 체크리스트",
  precedent: "유사 지역 선례",
  before_after: "조치 전후 비교",
  timeline: "확산 타임라인",
};

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
export default function DataState({ result, render }) {
  if (result.status === "loading") {
    return <div className="loading-state">불러오는 중…</div>;
  }
  if (result.status === "unsupported") {
    const label = DATA_LABELS[result.dataType] ?? result.dataType;
    const hint = FALLBACK_HINT[result.dataType];
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
