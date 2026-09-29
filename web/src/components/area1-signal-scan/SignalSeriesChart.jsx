import { alignedSignalSeries } from "../../lib/alignedSignalSeries.js";

const WIDTH = 640;
const HEIGHT = 100;
const PAD = 8;

function MiniLine({ rows, field, color, label, asOf, threshold }) {
  const values = rows.map((row) => row[field]).filter((value) => typeof value === "number");
  if (!values.length) return null;
  const max = Math.max(threshold, ...values, 1.2) * 1.08;
  const x = (index) => PAD + index * (WIDTH - PAD * 2) / Math.max(1, rows.length - 1);
  const y = (value) => HEIGHT - PAD - value / max * (HEIGHT - PAD * 2);
  let path = "";
  let drawing = false;
  rows.forEach((row, index) => {
    const value = row[field];
    if (typeof value !== "number") { drawing = false; return; }
    path += `${drawing ? " L" : " M"}${x(index)},${y(value)}`;
    drawing = true;
  });
  const latest = [...rows].reverse().find((row) => typeof row[field] === "number");
  return (
    <div className="series-row">
      <div className="series-label"><strong>{label}</strong><span>{asOf} 기준 · 최근 {latest?.[field]?.toFixed(2)}배</span></div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${label} 전년 같은 요일 대비 추이`} className="series-plot">
        <line x1={PAD} x2={WIDTH - PAD} y1={y(1)} y2={y(1)} stroke="#d6d1de" strokeDasharray="4 4" />
        <line x1={PAD} x2={WIDTH - PAD} y1={y(threshold)} y2={y(threshold)} stroke="#d8a06f" strokeDasharray="4 4" />
        <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

export default function SignalSeriesChart({ seriesData }) {
  const { daily, commonEnd } = alignedSignalSeries(seriesData);
  const rows = daily.slice(-90);
  if (!rows.length) return <p>추이 자료가 없습니다.</p>;
  return (
    <div className="series-view">
      <p className="forecast-caption">검색·방문 공통 기준 최근 90일 · 전년 같은 요일 대비 변화 · {rows[0].date} ~ {rows.at(-1).date}</p>
      <MiniLine rows={rows} field="search_stat" color="#007fbe" label="지역 검색" asOf={commonEnd} threshold={seriesData.thresholds.search} />
      <MiniLine rows={rows} field="visitors_stat" color="#2383aa" label="외지인 방문" asOf={commonEnd} threshold={seriesData.thresholds.visitors} />
      <p className="forecast-caption">점선은 비교 기준(1배)과 검토 임계선입니다. 검색 추이는 방문 증가를 미리 예측하는 지표가 아닙니다.</p>
    </div>
  );
}
