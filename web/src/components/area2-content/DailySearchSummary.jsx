import { alignedSignalSeries } from "../../lib/alignedSignalSeries.js";

function MonthlySearchSummary({ result }) {
  if (result.status !== "ok") return <section className="report-evidence"><h3 className="report-channel">지역 검색 추이</h3><p className="morning-window">월별 검색 자료를 불러오는 중입니다.</p></section>;

  const alignedDaily = alignedSignalSeries(result.envelope.data).daily;
  const searchField = alignedDaily.some((row) => Number.isFinite(row.search_index)) ? "search_index" : "search_stat";
  const isRatio = searchField === "search_stat";
  const daily = alignedDaily.filter((row) => Number.isFinite(row[searchField]));
  const groups = new Map();
  for (const row of daily) {
    const month = row.date.slice(0, 7);
    const group = groups.get(month) ?? { month, total: 0, days: 0 };
    group.total += row[searchField];
    group.days += 1;
    groups.set(month, group);
  }
  const months = [...groups.values()].slice(-6).map((group) => ({
    month: group.month,
    average: group.total / group.days,
  }));
  if (!months.length) return <section className="report-evidence"><h3 className="report-channel">지역 검색 추이</h3><p className="morning-window">표시할 월별 검색 자료가 없습니다.</p></section>;

  const last = months.at(-1);
  const lastDate = daily.at(-1).date;
  const monthEnd = new Date(Date.UTC(Number(lastDate.slice(0, 4)), Number(lastDate.slice(5, 7)), 0)).getUTCDate();
  const partialMonth = Number(lastDate.slice(8, 10)) < monthEnd;
  const roughStep = Math.max(...months.map((row) => row.average), 1) * 1.15 / 3;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const step = [1, 2, 5, 10].find((multiple) => multiple * magnitude >= roughStep) * magnitude;
  const scaleMax = step * 3;
  const chartBottom = 165;
  const y = (value) => chartBottom - value / scaleMax * 135;
  const barX = (index) => 50 + index * 59;

  return <section className="report-evidence" aria-label="지역 검색 추이 월별 평균">
    <h3 className="report-channel">지역 검색 추이</h3>
    <div className="morning-meta"><span>자료 기준 {lastDate}</span></div>
    <h3>최근 6개월 검색 흐름</h3>
    <div className="report-search-value"><strong>{last.average.toFixed(isRatio ? 2 : 1)}<small>{isRatio ? "배" : "지수"}</small></strong><span>{Number(last.month.slice(5))}월 평균{partialMonth ? ` · ${Number(lastDate.slice(8, 10))}일까지` : ""}</span></div>
    <svg className="report-search-chart report-monthly-search-chart" viewBox="0 0 410 210" role="img" aria-label={`${months[0].month}부터 ${last.month}까지 월평균 ${isRatio ? "전년 같은 요일 대비 검색 배율의 7일 중앙값" : "지역 검색지수"}. 최근 ${last.average.toFixed(isRatio ? 2 : 1)}.${partialMonth ? ` ${last.month}은 ${Number(lastDate.slice(8, 10))}일까지 집계.` : ""}`}>
      {[0, step, step * 2, scaleMax].map((value) => <g key={value}>
        <line x1="32" x2="400" y1={y(value)} y2={y(value)} stroke="#dceaf1" />
        <text x="26" y={y(value) + 4} textAnchor="end">{isRatio ? value.toFixed(1) : value}</text>
      </g>)}
      {months.map((row, index) => <g key={row.month}>
        <rect x={barX(index)} y={y(row.average)} width="32" height={chartBottom - y(row.average)} rx="2" className={index === months.length - 1 ? "is-latest" : ""} />
        <text x={barX(index) + 16} y={y(row.average) - 7} textAnchor="middle" className="report-monthly-value">{row.average.toFixed(isRatio ? 2 : 1)}</text>
        <text x={barX(index) + 16} y="188" textAnchor="middle">{Number(row.month.slice(5))}월</text>
      </g>)}
    </svg>
    <p className="morning-window">{isRatio ? "전년 같은 요일 대비 검색 배율(7일 중앙값)의 월평균" : "일별 상대 검색지수의 월평균"}{partialMonth ? ` · ${Number(last.month.slice(5))}월은 ${Number(lastDate.slice(8, 10))}일까지 집계` : ""}</p>
  </section>;
}

export default function DailySearchSummary({ signalSeries }) {
  if (signalSeries) return <MonthlySearchSummary result={signalSeries} />;
  return <section className="report-evidence"><h3 className="report-channel">지역 검색 추이</h3><p className="morning-window">월별 검색 자료가 연결되지 않았습니다.</p></section>;
}
