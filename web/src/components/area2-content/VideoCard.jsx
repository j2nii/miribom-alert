import ZoneSignalBadge from "./ZoneSignalBadge.jsx";

export default function VideoCard({ item, selected, onSelect }) {
  return (
    <div
      onClick={onSelect}
      style={{
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${selected ? "var(--teal)" : "var(--border)"}`,
        marginBottom: 8,
        cursor: "pointer",
        background: selected ? "#f2f8f6" : "#fff",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
        <strong>{item.title}</strong>
        <span style={{ color: "var(--muted)" }}>{item.view_count.toLocaleString()}회</span>
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
        {item.channel} · {item.published_at} · {item.content_type} (신뢰도 {item.confidence})
        <ZoneSignalBadge zoneSignal={item.zone_signal} />
      </div>
      {selected && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          <p style={{ margin: "4px 0" }}>
            <strong>근거:</strong> {item.evidence}
          </p>
          <p style={{ margin: "4px 0" }}>
            <strong>감성:</strong> {item.sentiment}
          </p>
          {item.poi_mentioned?.length > 0 && (
            <p style={{ margin: "4px 0" }}>
              <strong>언급 장소:</strong> {item.poi_mentioned.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
