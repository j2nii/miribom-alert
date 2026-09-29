const STATES = {
  normal: { label: "평상시", interpretation: "현재 판정에서 온라인 관심 후보와 방문 수요 이상이 선정되지 않았습니다." },
  online_watch: { label: "온라인 관심 후보", interpretation: "온라인 관심 후보가 포착됐습니다. 관련 콘텐츠를 확인할 단계이며 바이럴 확정이나 방문 증가 예측은 아닙니다." },
  demand_anomaly: { label: "방문 수요 확인 필요", interpretation: "방문 수요 이상이 포착됐습니다. 현장 상황과 다른 발생 요인을 확인해 주세요." },
  combined_alert: { label: "우선 검토 필요", interpretation: "온라인 관심 후보와 방문 수요 이상이 함께 포착됐습니다. 우선 검토가 필요하며 두 신호의 인과관계가 확인된 것은 아닙니다." },
};

export function reviewMatrixPresentation(state, freshness) {
  return {
    ...(STATES[state] ?? { label: "상태 확인 필요", interpretation: "지원하지 않는 검토 상태입니다. 원자료를 확인해 주세요." }),
    freshnessLabel: freshness?.stale === false ? "데이터 기준일 확인" : "최신 가용 데이터 기준",
  };
}
