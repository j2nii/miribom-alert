export default function PrecedentCards({ precedentData }) {
  const { matched_for, cases } = precedentData;

  return (
    <div>
      <div
        style={{
          fontSize: 12,
          color: "var(--muted)",
          marginBottom: 12,
          padding: "8px 12px",
          background: "var(--mist)",
          borderRadius: 8,
        }}
      >
        이 조건으로 매칭됨 — {matched_for.alert_level} · {matched_for.spatial_type} · {matched_for.content_type}
      </div>

      {cases.map((c) => (
        <div key={c.case_id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong>
              {c.region_name} ({c.year})
            </strong>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>유사도 {(c.similarity * 100).toFixed(0)}%</span>
          </div>
          <p style={{ fontSize: 13, margin: "6px 0" }}>{c.situation}</p>
          <ul style={{ fontSize: 13, margin: "0 0 6px", paddingLeft: 18 }}>
            {c.actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          <p style={{ fontSize: 13, margin: 0 }}>
            {c.outcome.summary}{" "}
            <span
              style={{
                fontSize: 11,
                padding: "1px 6px",
                borderRadius: 999,
                background: c.outcome.measured ? "#e1efe8" : "#f2f2f2",
                color: c.outcome.measured ? "var(--teal)" : "var(--muted)",
              }}
            >
              {c.outcome.measured ? "측정됨" : "보도 기준(미측정)"}
            </span>
          </p>
        </div>
      ))}
    </div>
  );
}
