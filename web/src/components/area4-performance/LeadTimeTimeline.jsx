export default function LeadTimeTimeline({ timelineData }) {
  const { title, spatial_type, content_type, lead_time_days, events } = timelineData;

  return (
    <div>
      <p style={{ fontSize: 14, fontWeight: 700 }}>{title}</p>
      <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
        {spatial_type} · {content_type}
      </p>

      <div
        style={{
          display: "inline-block",
          padding: "8px 16px",
          borderRadius: 8,
          background: "var(--teal)",
          color: "#fff",
          fontWeight: 700,
          marginBottom: 16,
        }}
      >
        콘텐츠 확산 → 조치 시행까지 리드타임: {lead_time_days}일
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
