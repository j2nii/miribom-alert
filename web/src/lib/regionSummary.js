// Summaries describe detected signals, never infer a causal link or today's news.
export function summarizeSignals(data) {
  const signals = Array.isArray(data.cross_validation) ? data.cross_validation : [];
  const detected = (stage) => signals.find((signal) => signal.stage === stage)?.exceeded === true;
  if (!data.alert_level) {
    return {
      headline: "온라인 관심의 흐름을 살펴보는 참고 사례입니다",
      description: "예시 데이터입니다. 실제 지역 현황이나 방문 증가를 판단하는 자료로 사용할 수 없습니다.",
    };
  }
  if (detected("실현")) return {
    headline: "지역 방문 증가 신호가 감지됐습니다",
    description: "집계 기간의 방문 지표가 감지 기준을 넘었습니다. 어느 관광지에 사람이 몰리는지 현장 상황을 함께 확인하세요.",
  };
  if (detected("의도")) return {
    headline: "방문지를 찾는 검색 움직임이 감지됐습니다",
    description: "방문지 검색 지표가 감지 기준을 넘었습니다. 실제 방문 증가 여부는 별도로 확인해야 합니다.",
  };
  if (detected("관심")) return {
    headline: "온라인에서 지역을 언급하는 움직임이 감지됐습니다",
    description: "온라인 관심 지표가 감지 기준을 넘었습니다. 어떤 콘텐츠가 주목받는지 살펴보고 관광 안내 정보를 점검하세요.",
  };
  return {
    headline: signals.length ? "현재 자료에서 뚜렷한 증가 신호는 확인되지 않았습니다" : "지역 변화 판단에 필요한 자료를 확인해 주세요",
    description: "증가 신호가 없다고 현장이 한산하다는 뜻은 아닙니다. 지역 콘텐츠와 현장 문의를 함께 살펴보세요.",
  };
}

export function selectRegionalVideos(envelope, limit = 2) {
  return (envelope?.data?.items ?? [])
    .filter((item) => item.content_type && item.content_type !== "관광무관" && Number.isFinite(item.confidence) && item.confidence >= 0.6)
    .slice()
    .sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
    .slice(0, limit);
}
