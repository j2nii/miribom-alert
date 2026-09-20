export default function ZoneSignalBadge({ zoneSignal }) {
  if (!zoneSignal) return null;
  const isDeadZone = zoneSignal === "데드존";
  return (
    <span
      style={{
        fontSize: 11,
        padding: "1px 6px",
        borderRadius: 999,
        marginLeft: 6,
        background: isDeadZone ? "#e6eef7" : "#fdeee0",
        color: isDeadZone ? "#2b5a8c" : "#a3521f",
      }}
    >
      {isDeadZone ? "데드존 · 분산 후보" : "핫존"}
    </span>
  );
}
