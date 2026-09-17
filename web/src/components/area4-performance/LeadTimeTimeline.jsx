// agents 브랜치 계약 변경: spatial_type/content_type/lead_time_days 모두
// 생략 가능해졌고(스키마: "화면은 생략을 처리해야 한다"), lead_time_days의
// 정의도 "콘텐츠 확산 → 조치 시행"이 아니라 "콘텐츠 확산 → 방문 급증"으로
// 바뀌었다 -- "조치 시행까지"는 새 lags.content_to_action_days를 쓴다.
function LeadTimeBadge({ label, days }) {
  if (days == null) return null;
  return (
    <div
      style={{
        display: "inline-block",
        padding: "8px 16px",
        borderRadius: 8,
        background: "var(--teal)",
        color: "#fff",
        fontWeight: 700,
      }}
    >
      {label}: {days}일
    </div>
  );
}

export default function LeadTimeTimeline({ timelineData }) {
  const { title, spatial_type, content_type, lead_time_days, lags, events } = timelineData;
  const subtitle = [spatial_type, content_type].filter(Boolean).join(" · ");

  return (
    <div>
      <p style={{ fontSize: 14, fontWeight: 700 }}>{title}</p>
      {subtitle && <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>{subtitle}</p>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <LeadTimeBadge label="콘텐츠 확산 → 방문 급증" days={lead_time_days} />
        <LeadTimeBadge label="콘텐츠 확산 → 조치 시행" days={lags?.content_to_action_days} />
        {lags?.signal_to_action_days != null && (
          <div
            style={{
              display: "inline-block",
              padding: "8px 16px",
              borderRadius: 8,
              background: "var(--mist)",
              color: "var(--ink)",
              fontWeight: 700,
            }}
          >
            {lags.signal_to_action_days > 0
              ? `신호가 조치보다 ${lags.signal_to_action_days}일 앞섬`
              : lags.signal_to_action_days < 0
                ? `신호가 조치보다 ${Math.abs(lags.signal_to_action_days)}일 늦음`
                : "신호와 조치가 같은 날"}
          </div>
        )}
      </div>

      <div style={{ borderLeft: "2px solid var(--border)", marginLeft: 8, paddingLeft: 16 }}>
        {events.map((e, i) => (
          <div key={i} style={{ position: "relative", paddingBottom: 16 }}>
            <span
              style={{
                position: "absolute",
                left: -21,
                top: 2,
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: e.is_signal ? "var(--teal)" : "#fff",
                border: `2px solid ${e.is_signal ? "var(--teal)" : "var(--muted)"}`,
              }}
            />
            <div style={{ fontSize: 13 }}>
              <strong>{e.date}</strong> · {e.type}
            </div>
            <div style={{ fontSize: 13, color: "var(--muted)" }}>{e.description}</div>
            {e.value != null && (
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                값: {e.value}
                {e.unit}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
