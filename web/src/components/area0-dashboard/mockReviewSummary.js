const SUMMARIES = {
  online_watch: {
    label: "온라인 관심 후보",
    summary: "온라인 관심이 포착됐지만, 방문 수요 이상은 아직 나타나지 않은 상황입니다.",
    action: "어떤 콘텐츠가 퍼지고 있는지 확인하고, 방문 수요 변화를 함께 살펴보세요.",
  },
  normal: {
    label: "정기 관찰",
    summary: "온라인 관심이 평소 수준이며, 방문 수요 이상도 포착되지 않은 상황입니다.",
    action: "새로운 이슈가 생기는지 살펴보며 정기 모니터링을 유지하세요.",
  },
  demand_anomaly: {
    label: "방문 수요 확인 필요",
    summary: "온라인 관심 후보 없이 방문 수요 이상이 포착된 상황입니다.",
    action: "행사·계절 요인과 현장 상황을 먼저 확인하세요.",
  },
  combined_alert: {
    label: "우선 검토 필요",
    summary: "온라인 관심 후보와 방문 수요 이상이 함께 포착된 상황입니다. 두 신호의 인과관계가 확인된 것은 아닙니다.",
    action: "관련 콘텐츠와 현장 상황을 함께 검토하고 안내·수용 준비가 필요한지 확인하세요.",
  },
};

export function mockReviewSummary(envelope) {
  const scenario = envelope?.data?.review_matrix_example;
  if (!envelope?._mock || typeof scenario?.online_watch_active !== "boolean" || typeof scenario?.visitor_anomaly_active !== "boolean") return null;
  const state = scenario.online_watch_active
    ? scenario.visitor_anomaly_active ? "combined_alert" : "online_watch"
    : scenario.visitor_anomaly_active ? "demand_anomaly" : "normal";
  return { state, ...SUMMARIES[state] };
}
