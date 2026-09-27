// 분석 단계 정의. 화면이 "이 지역에서 무엇을 볼 수 있나"를 말할 때 쓰는 하나의 기준표다.
//
//   기본 분석  공개 데이터(데이터랩·이동통신·검색지수)만으로 만든다 → 전국 226개 시군구
//   심층 분석  유튜브·기사 수집 자료 + 에이전트(콘텐츠 분류·매뉴얼 매칭·브리핑) → 사례 지역 6곳
//
// 어느 항목이 실제로 있는지는 지역 사전(regions/index.json)의 `has` 목록으로 판단한다 —
// 사례 지역이라도 체크리스트·브리핑이 없는 곳이 있어서, "6곳 모두 전부 된다"고 말하지 않는다.

export const BASIC_FEATURES = [
  { type: "signal_status", label: "경보 판정", desc: "관심·의도·실현 3중 교차검증" },
  { type: "signal_series", label: "신호 추이", desc: "검색·방문 급증과 지점 쏠림" },
  { type: "forecast", label: "7일 방문객 예측", desc: "80% 구간 포함" },
];

export const DEEP_FEATURES = [
  { type: "content_type", label: "콘텐츠 원인 분석", desc: "유튜브·SNS 콘텐츠 유형 분류" },
  { type: "timeline", label: "확산 타임라인", desc: "콘텐츠 확산 → 방문 급증 → 조치" },
  { type: "hotspots", label: "인기 관광지·방문객 구성", desc: "지점 랭킹, 연령·거주지 분포" },
  { type: "checklist", label: "매뉴얼 대응 체크리스트", desc: "상황별 조치와 매뉴얼 쪽수" },
  { type: "precedent", label: "유사 선례", desc: "연구보고서 사례 원문 인용" },
  { type: "briefing", label: "정책 브리핑", desc: "보고용 3문단 초안" },
];

// 심층 분석 사례 지역. 주 사례(영월)·대비 사례(거제) 먼저
export const CASE_REGIONS = [
  { key: "yeongwol", label: "영월", role: "주 사례" },
  { key: "geoje", label: "거제", role: "대비 사례" },
  { key: "yeosu", label: "여수" },
  { key: "sokcho", label: "속초" },
  { key: "inje", label: "인제" },
  { key: "ulleung", label: "울릉" },
];

export const CASE_NAMES = CASE_REGIONS.map((c) => c.label).join("·");

export function deepCoverage(entry) {
  const has = new Set(entry?.has ?? []);
  const items = DEEP_FEATURES.map((f) => ({ ...f, ready: has.has(f.type) }));
  return { items, ready: items.filter((i) => i.ready).length, total: items.length };
}
