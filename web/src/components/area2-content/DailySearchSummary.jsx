import { alignedSignalSeries } from "../../lib/alignedSignalSeries.js";

const EXAMPLES = {
  yeongwol: { keyword: "영월 여행", values: [30, 34, 40, 55, 62, 72, 90] },
  geoje: { keyword: "거제 여행", values: [30, 32, 29, 31, 30, 32, 31] },
  chungju: { keyword: "충주 여행", values: [38, 42, 41, 48, 52, 57, 63] },
};

function ObservedSearchSummary({ result }) {
  if (result.status !== "ok") return <section className="report-evidence"><h3 className="report-channel">지역 검색 추이</h3><p className="morning-window">일별 검색 자료를 불러오는 중입니다.</p></section>;
  const envelope = result.envelope;
  const valid = alignedSignalSeries(envelope.data).daily.filter((row) => Number.isFinite(row.search_index));
  const series = valid.slice(-7);
  if (!series.length) return <section className="report-evidence"><h3 className="report-channel">지역 검색 추이</h3><p className="morning-window">표시할 일별 검색 자료가 없습니다.</p></section>;
  const last = series.at(-1);
  const values = series.map((row) => row.search_index);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const padding = Math.max((maximum - minimum) * 0.25, 2);
  const floor = Math.max(0, minimum - padding);
  const ceiling = maximum + padding;
  const lastFourteen = valid.slice(-14);
  const completeWeeks = lastFourteen.length === 14 && lastFourteen.every((row, index) => index === 0
    || Date.parse(`${row.date}T00:00:00Z`) - Date.parse(`${lastFourteen[index - 1].date}T00:00:00Z`) === 86400000);
  const currentAverage = completeWeeks ? values.reduce((sum, value) => sum + value, 0) / 7 : null;
  const priorAverage = completeWeeks ? lastFourteen.slice(0, 7).reduce((sum, row) => sum + row.search_index, 0) / 7 : null;
  const change = currentAverage !== null && priorAverage > 0 ? (currentAverage / priorAverage - 1) * 100 : null;
  const x = (index) => 28 + index * 49;
  const y = (value) => 124 - (value - floor) / (ceiling - floor) * 100;
  return <section className="report-evidence" aria-label="지역 검색 추이">
    <h3 className="report-channel">지역 검색 추이</h3>
    <div className="morning-meta"><span className="report-observed">네이버 검색지수</span><span>자료 기준 {last.date}</span></div>
    <h3>최근 1주 검색 흐름</h3>
    <div className="report-search-value"><strong>{last.search_index.toFixed(1)}<small>지수</small></strong><span>{change === null ? "비교 자료 부족" : `최근 7일 ${change >= 0 ? "+" : "−"}${Math.abs(change).toFixed(1)}%`}</span></div>
    <svg className="report-search-chart" viewBox="0 0 350 150" role="img" aria-label={`${series[0].date}부터 ${last.date}까지 일별 지역 검색지수. 최근 ${last.search_index.toFixed(1)}.`}>
      {[floor, ceiling].map((value) => <g key={value}><line x1="28" x2="322" y1={y(value)} y2={y(value)} stroke="#dceaf1" /><text x="22" y={y(value) + 4} textAnchor="end" fontSize="10" fill="#67808e">{value.toFixed(0)}</text></g>)}
      {priorAverage !== null && priorAverage >= floor && priorAverage <= ceiling && <line x1="28" x2="322" y1={y(priorAverage)} y2={y(priorAverage)} stroke="#7ebbd6" strokeDasharray="4 5" />}
      <polyline points={series.map((row, index) => `${x(index)},${y(row.search_index)}`).join(" ")} fill="none" stroke="#007fbe" strokeWidth="3" />
      {series.map((row, index) => <g key={row.date}><circle cx={x(index)} cy={y(row.search_index)} r="3" fill="#007fbe" />{(index === 0 || index === series.length - 1) && <text x={x(index)} y="143" textAnchor="middle" fontSize="10" fill="#617b88">{row.date.slice(5).replace("-", "/")}</text>}</g>)}
    </svg>
    <p className="morning-window">지역명 검색량을 일별 상대지수로 표시합니다.</p>
  </section>;
}

export default function DailySearchSummary({ region, signalSeries }) {
  if (signalSeries) return <ObservedSearchSummary result={signalSeries} />;
  const sample = EXAMPLES[region];
  if (!sample) return null;
  const last = sample.values.at(-1);
  const previous = sample.values.at(-2);
  const difference = last - previous;
  const x = i => 28 + i * 49;
  const y = value => 124 - value;
  return <section className="report-evidence" aria-label="네이버 일별 검색지수 예시">
    <h3 className="report-channel">지역 검색 추이</h3>
    <div className="morning-meta"><span>목업</span><span>예시 기준 2026.09.26</span></div>
    <h3>{region === "geoje" ? "검색 관심은 평소 수준이에요" : "검색 관심이 전날보다 늘었어요"}</h3>
    <div className="report-search-value"><strong>{last}<small>지수</small></strong><span>전일 {previous} → {last} · {difference > 0 ? "+" : ""}{difference}p</span></div>
    <svg className="report-search-chart" viewBox="0 0 350 150" role="img" aria-label={`검색지수 목업. 9월 20일부터 26일까지 ${sample.values.join(', ')}. 검색 건수가 아닙니다.`}>
      {[0, 50, 100].map(value => <g key={value}><line x1="28" x2="322" y1={y(value)} y2={y(value)} stroke="#e9e2f0" /><text x="22" y={y(value) + 4} textAnchor="end" fontSize="10" fill="#756589">{value}</text></g>)}
      <polyline points={sample.values.map((value, i) => `${x(i)},${y(value)}`).join(' ')} fill="none" stroke="#007fbe" strokeWidth="3" />
      {sample.values.map((value, i) => <g key={i}><circle cx={x(i)} cy={y(value)} r="3" fill="#007fbe" /><text x={x(i)} y="143" textAnchor="middle" fontSize="10" fill="#617b88">09/{20 + i}</text></g>)}
    </svg>
    <p className="morning-window">검색어 예시 ‘{sample.keyword}’ · 0~100 상대지수</p>
  </section>;
}
