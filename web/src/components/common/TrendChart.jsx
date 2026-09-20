const W = 640;
const H = 150;
const PAD = 10;

// Line chart with an optional dashed threshold line and per-segment color
// (crimson before a condition is met, teal after) -- native SVG <title>
// gives a hover tooltip per point without any charting library.
export default function TrendChart({ points, valueKey, labelKey, thresholdValue, thresholdLabel, isResolvedFn, tooltipFn }) {
  const values = points.map((p) => p[valueKey]);
  const min = Math.min(...values, thresholdValue ?? Infinity);
  const max = Math.max(...values, thresholdValue ?? -Infinity);
  const range = max - min || 1;
  const xStep = (W - PAD * 2) / Math.max(1, points.length - 1);
  const x = (i) => PAD + i * xStep;
  const y = (v) => H - PAD - ((v - min) / range) * (H - PAD * 2);

  return (
    <svg viewBox={`0 0 ${W} ${H + 20}`} style={{ width: "100%", height: "auto" }}>
      {thresholdValue != null && (
        <>
          <line
            x1={PAD}
            y1={y(thresholdValue)}
            x2={W - PAD}
            y2={y(thresholdValue)}
            stroke="var(--ink-soft)"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
          {thresholdLabel && (
            <text x={W - PAD} y={y(thresholdValue) - 4} textAnchor="end" fontSize="10" fill="var(--ink-soft)">
              {thresholdLabel}
            </text>
          )}
        </>
      )}

      {points.slice(1).map((p, i) => {
        const prev = points[i];
        const resolved = isResolvedFn ? isResolvedFn(p, i + 1) : false;
        return (
          <line
            key={i}
            x1={x(i)}
            y1={y(prev[valueKey])}
            x2={x(i + 1)}
            y2={y(p[valueKey])}
            stroke={resolved ? "var(--teal)" : "var(--crimson)"}
            strokeWidth="2.5"
          />
        );
      })}

      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(p[valueKey])}
          r="3.5"
          fill={isResolvedFn && isResolvedFn(p, i) ? "var(--teal)" : "var(--crimson)"}
        >
          <title>{tooltipFn ? tooltipFn(p, i) : `${p[labelKey]}: ${p[valueKey]}`}</title>
        </circle>
      ))}

      {points.map((p, i) => (
        <text key={i} x={x(i)} y={H + 14} textAnchor="middle" fontSize="9" fill="var(--ink-soft)">
          {p[labelKey]}
        </text>
      ))}
    </svg>
  );
}
