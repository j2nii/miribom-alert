const WIDTH = 720;
const HEIGHT = 250;
const LEFT = 56;
const RIGHT = 24;
const TOP = 26;
const BOTTOM = 205;
const number = new Intl.NumberFormat("ko-KR");

function curve(points) {
  if (!points.length) return "";
  return points.reduce((path, point, index) => {
    if (!index) return `M${point.x},${point.y}`;
    const previous = points[index - 1];
    const control = (previous.x + point.x) / 2;
    return `${path} C${control},${previous.y} ${control},${point.y} ${point.x},${point.y}`;
  }, "");
}

function axisValue(value) {
  return value >= 10000 ? `${number.format(value / 10000)}만` : number.format(value);
}

export default function ForecastChart({ forecastData, period }) {
  const daily = forecastData.daily ?? [];
  if (!daily.length) return <p>예측 값이 없습니다.</p>;

  const upperMax = Math.max(...daily.map((day) => day.upper));
  const ceiling = Math.ceil(upperMax / 10000) * 10000;
  const scale = (value) => BOTTOM - value / ceiling * (BOTTOM - TOP);
  const x = (index) => LEFT + index * (WIDTH - LEFT - RIGHT) / Math.max(1, daily.length - 1);
  const point = (field) => daily.map((day, index) => ({ x: x(index), y: scale(day[field]) }));
  const predicted = point("predicted");
  const upper = point("upper");
  const lower = point("lower");
  const upperPath = curve(upper);
  const lowerPath = curve(lower.slice().reverse());
  const band = `${upperPath} L${lower.at(-1).x},${lower.at(-1).y} ${lowerPath.replace(/^M[^C]*/, "")} Z`;
  const peakIndex = daily.reduce((best, day, index) => day.predicted > daily[best].predicted ? index : best, 0);
  const peak = daily[peakIndex];
  const basis = new Date(`${daily[0].date}T00:00:00Z`);
  basis.setUTCDate(basis.getUTCDate() - 1);
  const tickStep = Math.max(10000, Math.floor(ceiling / 3 / 10000) * 10000);
  const ticks = Array.from({ length: Math.floor(ceiling / tickStep) + 1 }, (_, index) => index * tickStep);

  return (
    <div className="forecast-view">
      <div className="forecast-heading">
        <div><strong>7일 방문 예측</strong><span>{basis.toISOString().slice(0, 10)} 기준 · {period?.start ?? daily[0].date} ~ {period?.end ?? daily.at(-1).date}</span></div>
        <div className="forecast-peak-summary"><span>최고 예측일 · {peak.date.slice(5).replace("-", "/")}</span><strong>{number.format(peak.predicted)}<small>명</small></strong></div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`일별 방문 예측. ${peak.date} 최고 ${number.format(peak.predicted)}명. 연한 영역은 80% 예측 구간.`} className="forecast-plot">
        <defs>
          <linearGradient id="forecast-band-gradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#8cd4ef" stopOpacity=".48" />
            <stop offset="100%" stopColor="#8cd4ef" stopOpacity=".15" />
          </linearGradient>
        </defs>
        {ticks.map((value) => <g key={value} className="forecast-grid">
          <line x1={LEFT} x2={WIDTH - RIGHT} y1={scale(value)} y2={scale(value)} />
          <text x={LEFT - 11} y={scale(value) + 4} textAnchor="end">{axisValue(value)}</text>
        </g>)}
        <path d={band} fill="url(#forecast-band-gradient)" />
        <path d={curve(predicted)} className="forecast-line" />
        {daily.map((day, index) => <g key={day.date}>
          {index === peakIndex && <circle cx={x(index)} cy={scale(day.predicted)} r="10" className="forecast-peak-ring" />}
          <circle cx={x(index)} cy={scale(day.predicted)} r={index === peakIndex ? 5 : 4} className={index === peakIndex ? "forecast-dot is-peak" : "forecast-dot"} />
          <text x={x(index)} y={HEIGHT - 13} textAnchor="middle" className="forecast-date">{day.date.slice(5).replace("-", "/")}</text>
          <circle cx={x(index)} cy={scale(day.predicted)} r="15" fill="transparent">
            <title>{day.date} · 예상 {number.format(day.predicted)}명 · 80% 범위 {number.format(day.lower)}~{number.format(day.upper)}명</title>
          </circle>
        </g>)}
        <text x={Math.min(x(peakIndex) + 13, WIDTH - RIGHT - 60)} y={Math.max(scale(peak.predicted) - 15, TOP + 2)} className="forecast-peak-label">{number.format(peak.predicted)}명</text>
      </svg>
      <div className="forecast-legend">
        <span><i className="forecast-legend-line" />예측 방문자</span>
        <span><i className="forecast-legend-band" />80% 예측 구간</span>
      </div>
    </div>
  );
}
