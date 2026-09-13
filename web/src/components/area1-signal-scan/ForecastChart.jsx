const WIDTH = 640;
const HEIGHT = 180;
const PAD = 8;

export default function ForecastChart({ forecastData }) {
  const { daily, model, weekday_concentration, peak_days } = forecastData;

  const values = daily.flatMap((d) => [d.lower, d.upper]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const xStep = (WIDTH - PAD * 2) / (daily.length - 1);
  const y = (v) => HEIGHT - PAD - ((v - min) / (max - min)) * (HEIGHT - PAD * 2);
  const x = (i) => PAD + i * xStep;

  const bandPath =
    daily.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.upper)}`).join(" ") +
    " " +
    daily
      .slice()
      .reverse()
      .map((d, i) => `L${x(daily.length - 1 - i)},${y(d.lower)}`)
      .join(" ") +
    " Z";
  const linePath = daily.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.predicted)}`).join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ width: "100%", height: "auto" }}>
        <path d={bandPath} fill="var(--teal)" opacity="0.12" />
        <path d={linePath} fill="none" stroke="var(--teal)" strokeWidth="2" />
        {daily.map(
          (d, i) =>
            d.is_holiday && (
              <circle key={i} cx={x(i)} cy={y(d.predicted)} r="3" fill="var(--amber)" />
            )
        )}
      </svg>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
        예측 기간 {daily[0].date} ~ {daily[daily.length - 1].date} · 음영 = 검증 잔차 80% 구간 · 점 = 공휴일
      </div>

      <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 13, flexWrap: "wrap" }}>
        <span>
          모델 <strong>{model.name}</strong>
        </span>
        <span>
          {model.metric.name} <strong>{model.metric.value}</strong>
        </span>
        <span style={{ color: "var(--muted)" }}>
          검증기간 {model.metric.validation_period.start}~{model.metric.validation_period.end}
        </span>
      </div>

      <div style={{ marginTop: 12 }}>
        <p style={{ fontSize: 13, fontWeight: 700, margin: "0 0 6px" }}>요일별 집중도</p>
        <div style={{ display: "flex", gap: 6 }}>
          {weekday_concentration.map((w) => (
            <div key={w.weekday} style={{ textAlign: "center", fontSize: 12 }}>
              <div
                style={{
                  width: 24,
                  height: Math.max(4, w.ratio * 300),
                  background: "var(--teal)",
                  borderRadius: 3,
                  marginBottom: 4,
                }}
              />
              {w.weekday}
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <p style={{ fontSize: 13, fontWeight: 700, margin: "0 0 6px" }}>피크 예상일 Top {peak_days.length}</p>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {peak_days.map((p) => (
            <li key={p.date}>
              {p.date} — {p.predicted.toLocaleString()}명, 예상 경보 {p.expected_alert_level} ({p.reason})
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
