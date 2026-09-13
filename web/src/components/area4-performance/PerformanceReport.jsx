function isImprovement(metric) {
  const worse = metric.direction === "낮을수록좋음" ? metric.after > metric.before : metric.after < metric.before;
  return !worse;
}

export default function PerformanceReport({ beforeAfterData }) {
  const { intervention, comparison_window, metrics } = beforeAfterData;

  return (
    <div>
      <p style={{ fontSize: 14 }}>
        <strong>{intervention.name}</strong> · 시행일 {intervention.applied_at}
      </p>
      <ul style={{ fontSize: 13, margin: "4px 0 12px", paddingLeft: 18 }}>
        {intervention.actions.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
      <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
        비교 구간: {comparison_window.before.start}~{comparison_window.before.end} (전) vs{" "}
        {comparison_window.after.start}~{comparison_window.after.end} (후)
      </p>

      {metrics.map((m, i) => {
        const good = isImprovement(m);
        return (
          <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <strong>{m.kpi}</strong>
              <span
                style={{
                  fontSize: 11,
                  padding: "1px 8px",
                  borderRadius: 999,
                  background: "#e6eef7",
                  color: "#2b5a8c",
                }}
              >
                Tier {m.tier}
              </span>
            </div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              {m.before}
              {m.unit} → {m.after}
              {m.unit}{" "}
              <span style={{ color: good ? "var(--teal)" : "var(--crimson)", fontWeight: 700 }}>
                ({m.change_rate >= 0 ? "+" : ""}
                {(m.change_rate * 100).toFixed(0)}% {good ? "개선" : "악화"})
              </span>
            </div>
            {m.significance && (
              <p style={{ fontSize: 12, color: "var(--muted)", margin: "4px 0 0" }}>{m.significance}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
