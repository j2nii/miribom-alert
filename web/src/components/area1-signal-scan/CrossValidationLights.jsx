import ConfidenceBox from "../common/ConfidenceBox.jsx";

// agents 브랜치 계약 변경: cross_validation[].value/threshold가 null일 수
// 있다 (측정 불가한 신호) -- 그대로 보간하면 "null%p"처럼 표시되므로 감싼다.
function formatMetric(value, unit) {
  return value != null ? `${value}${unit}` : "측정 안 됨";
}

// The 3-way cross-validation traffic light (D-05): 관심(SNS 언급량) ->
// 의도(내비게이션 검색) -> 실현(이동통신 방문자수). Replaces the old demo's
// single mention-chart-based stage judgment.
export default function CrossValidationLights({ signalStatusData }) {
  const { cross_validation: signals = [], agreement } = signalStatusData;

  return (
    <div>
      <ConfidenceBox
        matchedCount={agreement.exceeded_count}
        totalCount={agreement.total}
        lines={signals.map(
          (s) =>
            `${s.signal} ${formatMetric(s.value, s.unit)} (임계 ${formatMetric(s.threshold, s.unit)}, ${s.trend}, ${s.exceeded ? "초과" : "미달"})`
        )}
        note="1/3 초과 시 관심→주의, 2/3 시 주의→경계, 3/3 시 경계→심각으로 승격합니다(단계적 승격 규칙, D-05). 서로 출처가 다른 지표만 독립 신호로 센다."
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {signals.map((s, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 12px",
              borderRadius: 8,
              background: s.exceeded ? "var(--teal-tint-bg)" : "var(--mist)",
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: s.exceeded ? "var(--teal)" : "var(--pin-neutral)",
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, fontSize: 13 }}>
              <strong>{s.signal}</strong>
              <div style={{ color: "var(--ink-soft)" }}>{s.provider}</div>
            </div>
            <div style={{ fontSize: 13, textAlign: "right" }}>
              {formatMetric(s.value, s.unit)} / 임계 {formatMetric(s.threshold, s.unit)}
              <div style={{ color: "var(--ink-soft)" }}>{s.trend}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
