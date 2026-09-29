import { useState } from "react";
import SourceBadge from "../common/SourceBadge.jsx";

const fmt = (value) => value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });

function MentionTrend({ envelope }) {
  const points = envelope.data.lifecycle_series ?? [];
  const [selected, setSelected] = useState(null);
  const valid = points.length >= 4 && points.every((p) => Number.isFinite(p.mentions) && p.mentions >= 0);
  if (!valid) return <p className="summary-caption">언급량 비교에 필요한 월별 자료가 부족합니다.</p>;
  const last = points.at(-1);
  const average = points.slice(-4, -1).reduce((sum, p) => sum + p.mentions, 0) / 3;
  const change = average > 0 ? (last.mentions / average - 1) * 100 : null;
  const active = points[selected ?? points.length - 1];
  const ceiling = Math.max(1, ...points.map((p) => p.mentions)) * 1.15;
  const x = (i) => 64 + i * 608 / (points.length - 1);
  const y = (v) => 210 - v / ceiling * 180;
  const line = points.map((p, i) => `${x(i)},${y(p.mentions)}`).join(" ");
  return <>
    <div className="interest-chart-heading"><div><p className="summary-eyebrow">{envelope._mock ? "예시 데이터 · " : ""}SNS 언급량 추이</p><h3>{change === null ? "이전 평균이 0건으로 증감률을 계산할 수 없습니다" : `최근 언급량, 직전 3개월 평균보다 ${Math.abs(change).toFixed(1)}% ${change > 0 ? "증가" : change < 0 ? "감소" : "변화 없음"}`}</h3></div><strong>{fmt(last.mentions)}<small>건 · {last.month}</small></strong></div>
    <p className="summary-caption">직전 3개월({points.at(-4).month} ~ {points.at(-2).month}) 평균 {fmt(average)}건 · {envelope._mock ? "실제 현황이 아닌 화면 설명용 예시입니다." : "월별 수집 건수 기준입니다."}</p>
    <div className="interest-chart-readout" aria-live="polite">{active.month} · 언급량 <strong>{fmt(active.mentions)}건</strong></div>
    <svg className="interest-trend-svg" viewBox="0 0 720 250" role="group" aria-label="월별 SNS 언급량. 각 점에 마우스를 올리거나 키보드로 이동하면 건수를 확인할 수 있습니다.">
      {[0, 0.5, 1].map((n) => <g key={n}><line x1="64" x2="672" y1={y(ceiling * n)} y2={y(ceiling * n)} stroke="#e9e5f0" /><text x="55" y={y(ceiling * n) + 4} textAnchor="end" fontSize="11" fill="#746e7d">{Math.round(ceiling * n).toLocaleString("ko-KR")}</text></g>)}
      <polygon points={`64,210 ${line} 672,210`} fill="#f0eaf9" />
      <line x1="64" x2="672" y1={y(average)} y2={y(average)} stroke="#8c8396" strokeDasharray="5 5" />
      <polyline points={line} fill="none" stroke="#007fbe" strokeWidth="3" />
      {points.map((p, i) => <g key={p.month}>
        <circle cx={x(i)} cy={y(p.mentions)} r={i === (selected ?? points.length - 1) ? 7 : 5} fill="#007fbe" stroke="white" strokeWidth="2" tabIndex="0" role="img" aria-label={`${p.month} ${p.mentions}건`} onMouseEnter={() => setSelected(i)} onMouseLeave={() => setSelected(null)} onFocus={() => setSelected(i)} onBlur={() => setSelected(null)}><title>{p.month}: {fmt(p.mentions)}건</title></circle>
        <text x={x(i)} y="237" textAnchor="middle" fontSize="11" fill="#746e7d">{p.month.slice(5)}월</text>
      </g>)}
    </svg>
    <p className="summary-caption">실선: 월별 언급량 · 점선: 최근 월을 제외한 직전 3개월 평균 · 세로축: 건수(0부터 표시)</p>
    <SourceBadge envelope={envelope} />
  </>;
}

export default function InterestChart({ signalEnvelope, timelineResult }) {
  if (signalEnvelope.data.lifecycle_series) return <section className="interest-chart"><MentionTrend envelope={signalEnvelope} /></section>;
  const envelope = timelineResult.status === "ok" ? timelineResult.envelope : null;
  const checks = (envelope?.data?.signal_check ?? []).filter((item) => item.metric === "네이버 검색지수" && Number.isFinite(item.max_value) && item.max_value >= 0);
  if (!checks.length) return <div className="interest-chart"><h3>온라인 관심 추이</h3><p className="summary-caption">{timelineResult.status === "loading" ? "비교 자료를 확인하고 있습니다…" : "현재 연결된 자료에는 월별 SNS 언급량이 없습니다. 실제 건수 시계열이 연결되면 이전 기간과 비교할 수 있습니다."}</p></div>;
  const max = Math.max(1, ...checks.map((item) => item.max_value));
  const strongest = checks.reduce((a, b) => a.max_value > b.max_value ? a : b);
  const rows = [{ label: "전년 비교 기준", value: 1, note: "364일 전 같은 요일을 기준으로 한 배율" }, ...checks.map((item) => ({ label: item.note, value: item.max_value, note: `${item.window_start} ~ ${item.window_end} · 최고일 ${item.max_date}` }))];
  return <section className="interest-chart">
    <div className="interest-chart-heading"><div><p className="summary-eyebrow">{envelope._mock ? "예시 데이터" : "과거 사례"} · 검색 관심 비교</p><h3>검색 관심이 얼마나 커졌을까요?</h3></div><strong>{fmt(strongest.max_value)}배<small>분석 기간 중 최고 비교 배율</small></strong></div>
    <p className="summary-caption">{envelope.data.title} · 네이버 검색지수 비교</p>
    <div className="interest-bars" role="img" aria-label={rows.map((row) => `${row.label}: ${row.value}배`).join(". ")}>
      {rows.map((row, i) => <div className="interest-bar-row" key={i}><div className="interest-bar-label"><span>{row.label}</span><strong>{fmt(row.value)}배</strong></div><div className="interest-bar-track"><div className={i === 0 ? "interest-bar-baseline" : "interest-bar-value"} style={{ width: `${row.value / max * 100}%` }} /></div><p>{row.note}</p></div>)}
    </div>
    <SourceBadge envelope={envelope} />
  </section>;
}
