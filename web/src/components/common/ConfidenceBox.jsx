// "지금 확신할 수 있을까요?" callout -- a matched/total signal-count badge
// plus the per-signal lines behind it. Reused for both Geoje's real 3-way
// cross-validation (AREA 1) and Chungju's single-signal illustrative case
// (AREA 0), which is exactly the contrast the project wants to make visible:
// one signal alone is low-confidence, independent signals agreeing is not.
export default function ConfidenceBox({ matchedCount, totalCount, lines, note }) {
  const ratio = totalCount > 0 ? matchedCount / totalCount : 0;
  const level = ratio >= 1 ? "높음" : ratio > 0 ? "보통" : "낮음";
  const [bg, color] =
    ratio >= 1
      ? ["var(--teal-tint-bg)", "var(--teal)"]
      : ratio > 0
      ? ["var(--amber-tint-bg)", "var(--amber-tint-text)"]
      : ["var(--crimson-tint-bg)", "var(--crimson-tint-text)"];

  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 14, margin: "12px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <strong style={{ fontSize: 13 }}>지금 확신할 수 있을까요?</strong>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "2px 10px",
            borderRadius: 999,
            background: bg,
            color,
            whiteSpace: "nowrap",
          }}
        >
          확신도 {level} · {matchedCount}/{totalCount} 지표 일치
        </span>
      </div>
      <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        {lines.map((l, i) => (
          <li key={i} style={{ fontSize: 12, display: "flex", gap: 6 }}>
            <span style={{ color: "var(--ink-soft)" }}>○</span>
            <span>{l}</span>
          </li>
        ))}
      </ul>
      {note && (
        <p style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 10, marginBottom: 0, lineHeight: 1.6 }}>{note}</p>
      )}
    </div>
  );
}
