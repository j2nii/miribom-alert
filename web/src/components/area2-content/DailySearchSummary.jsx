const EXAMPLES = {
  yeongwol: { keyword: "영월 여행", values: [30, 34, 40, 55, 62, 72, 90] },
  geoje: { keyword: "거제 여행", values: [85, 68, 52, 40, 33, 31, 30] },
  chungju: { keyword: "충주 여행", values: [38, 42, 41, 48, 52, 57, 63] },
};

export default function DailySearchSummary({ region }) {
  const sample = EXAMPLES[region];
  if (!sample) return null;
  const last = sample.values.at(-1);
  const previous = sample.values.at(-2);
  const difference = last - previous;
  const x = i => 28 + i * 49;
  const y = value => 124 - value;
  return <section className="report-evidence" aria-label="네이버 일별 검색지수 예시">
    <h3 className="report-channel">네이버 · 일별 검색 추이</h3>
    <div className="morning-meta"><span>목업 · 실제 API 미연결</span><span>예시 기준 2026.09.26</span></div>
    <h3>{region === "geoje" ? "검색 관심이 잦아들고 있어요" : "검색 관심이 전날보다 늘었어요"}</h3>
    <div className="report-search-value"><strong>{last}<small>지수</small></strong><span>전일 {previous} → {last} · {difference > 0 ? "+" : ""}{difference}p</span></div>
    <svg className="report-search-chart" viewBox="0 0 350 150" role="img" aria-label={`검색지수 목업. 9월 20일부터 26일까지 ${sample.values.join(', ')}. 검색 건수가 아닙니다.`}>
      {[0, 50, 100].map(value => <g key={value}><line x1="28" x2="322" y1={y(value)} y2={y(value)} stroke="#e9e2f0" /><text x="22" y={y(value) + 4} textAnchor="end" fontSize="10" fill="#756589">{value}</text></g>)}
      <polyline points={sample.values.map((value, i) => `${x(i)},${y(value)}`).join(' ')} fill="none" stroke="#8777bb" strokeWidth="3" />
      {sample.values.map((value, i) => <g key={i}><circle cx={x(i)} cy={y(value)} r="3" fill="#65519d" /><text x={x(i)} y="143" textAnchor="middle" fontSize="10" fill="#756589">09/{20 + i}</text></g>)}
    </svg>
    <p className="morning-window">검색어 예시 ‘{sample.keyword}’ · 0~100 상대지수이며 검색 건수가 아닙니다. 실제 비교 시 동일한 조회 범위의 일별 값을 사용합니다.</p>
  </section>;
}
