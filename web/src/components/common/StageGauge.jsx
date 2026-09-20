const CX = 100;
const CY = 95;
const R = 75;
const STROKE = 14;
const LABEL_R = R + 17;

function polar(angleDeg, radius) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: CX + radius * Math.cos(rad), y: CY - radius * Math.sin(rad) };
}

// Semicircle gauge with N labeled stages and a needle -- used for both
// alert_level (관심/주의/경계/심각) and the lifecycle taxonomy
// (발화/확산/피크/쇠퇴). No chart library: same hand-rolled-SVG approach as
// the rest of the app's charts.
export default function StageGauge({ stages, currentKey }) {
  const n = stages.length;
  const span = 180 / n;
  const currentIndex = Math.max(
    0,
    stages.findIndex((s) => s.key === currentKey)
  );
  const needleAngle = 180 - (currentIndex + 0.5) * span;
  const needleTip = polar(needleAngle, R - 22);

  return (
    <svg viewBox="0 0 200 128" style={{ width: "100%", maxWidth: 260, display: "block", margin: "0 auto" }}>
      {stages.map((s, i) => {
        const p1 = polar(180 - i * span, R);
        const p2 = polar(180 - (i + 1) * span, R);
        return (
          <path
            key={s.key}
            d={`M ${p1.x} ${p1.y} A ${R} ${R} 0 0 1 ${p2.x} ${p2.y}`}
            stroke={s.color}
            strokeWidth={STROKE}
            fill="none"
            opacity={s.key === currentKey ? 1 : 0.45}
          />
        );
      })}
      <line
        x1={CX}
        y1={CY}
        x2={needleTip.x}
        y2={needleTip.y}
        stroke="var(--ink)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx={CX} cy={CY} r="6" fill="var(--ink)" />
      {stages.map((s, i) => {
        const p = polar(180 - (i + 0.5) * span, LABEL_R);
        const active = s.key === currentKey;
        return (
          <text
            key={s.key}
            x={p.x}
            y={p.y + 4}
            textAnchor="middle"
            fontSize="10"
            fontWeight={active ? 800 : 600}
            fill={active ? s.color : "var(--ink-soft)"}
          >
            {s.label}
          </text>
        );
      })}
    </svg>
  );
}
