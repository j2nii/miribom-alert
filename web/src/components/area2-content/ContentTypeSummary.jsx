export default function ContentTypeSummary({ data }) {
  const { summary, unclassified_count, zone_signals } = data;
  const maxRatio = Math.max(...summary.map((s) => s.ratio));

  return (
    <div>
      {summary
        .slice()
        .sort((a, b) => b.ratio - a.ratio)
        .map((s) => (
          <div key={s.content_type} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>{s.content_type}</span>
              <span>
                {(s.ratio * 100).toFixed(1)}% · {s.count}건 · 조회 {s.total_views.toLocaleString()}
              </span>
            </div>
            <div style={{ background: "var(--mist)", borderRadius: 4, height: 8 }}>
              <div
                style={{
                  width: `${(s.ratio / maxRatio) * 100}%`,
                  background: "var(--portal-accent)",
                  height: "100%",
                  borderRadius: 4,
                }}
              />
            </div>
          </div>
        ))}

      <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 12 }}>
        분류 제외(신뢰도 미달·관광무관) {unclassified_count}건 — 집계에서 뺐지만 건수는 항상 표시합니다.
      </p>

      {zone_signals && (
        <p style={{ fontSize: 13, marginTop: 8 }}>
          핫존 신호 {zone_signals.핫존}건 · 데드존 신호 {zone_signals.데드존}건
          {zone_signals.데드존_지점?.length > 0 && (
            <> — 분산 후보지: {zone_signals.데드존_지점.join(", ")}</>
          )}
        </p>
      )}
    </div>
  );
}
