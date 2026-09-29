import { useState } from "react";
import SourceBadge from "../common/SourceBadge.jsx";
import CaveatNote from "../common/CaveatNote.jsx";
import { alignedSignalSeries } from "../../lib/alignedSignalSeries.js";
import { summarizeVisitorSignal } from "../../lib/visitorSignal.js";
import { svgFit } from "../../lib/svgViewport.js";

const WIDTH = 360;
const HEIGHT = 108;
const RANGES = [
  { days: 7, label: "1주" },
  { days: 30, label: "1개월" },
  { days: 180, label: "6개월" },
];

const labelDate = (date) => date?.slice(5).replace("-", "/") ?? "—";
const formatCount = (value) => Math.round(value).toLocaleString("ko-KR");

// 마우스 위치를 데이터 인덱스로 바꾸고, 그 지점을 툴팁 wrap div 기준 px로
// 옮기는 데 쓸 스케일·여백도 함께 반환한다. svgFit이 실제 렌더 박스와
// viewBox 사이의 letterbox/pillarbox 여백을 반영해준다 -- 박스 크기만 보고
// 비율로 계산하면 max-height 등으로 눌린 차트에서 좌표가 어긋난다.
function pointFromMouse(event, rowsLength, left, right) {
  const box = event.currentTarget.getBoundingClientRect();
  const { scale, offsetX, offsetY } = svgFit(box.width, box.height, WIDTH, HEIGHT);
  const localX = (event.clientX - box.left - offsetX) / scale;
  const ratio = (localX - left) / (WIDTH - left - right);
  const index = Math.max(0, Math.min(rowsLength - 1, Math.round(ratio * (rowsLength - 1))));
  return { index, scale, offsetX, offsetY };
}

function ChartGrid({ left, right, top, height }) {
  const plotWidth = WIDTH - left - right;
  return <g aria-hidden="true" stroke="#dbe6eb" strokeWidth="1">
    {[0, 1, 2, 3, 4, 5, 6].map((step) => <line key={`vertical-${step}`} x1={left + plotWidth * step / 6} x2={left + plotWidth * step / 6} y1={top} y2={top + height} />)}
    {[0, 1, 2, 3].map((step) => <line key={`horizontal-${step}`} x1={left} x2={WIDTH - right} y1={top + height * step / 3} y2={top + height * step / 3} />)}
  </g>;
}

function percentChange(current, previous) {
  return Number.isFinite(current) && Number.isFinite(previous) && previous > 0 ? (current / previous - 1) * 100 : null;
}

function changeLabel(change) {
  if (change === null) return "비교 자료 부족";
  if (Math.abs(change) < 0.05) return "거의 같음";
  return `${Math.abs(change).toFixed(1)}% ${change > 0 ? "증가" : "감소"}`;
}

function compactChangeLabel(change) {
  if (change === null) return "자료 없음";
  if (Math.abs(change) < 0.05) return "변화 없음";
  return `${change > 0 ? "+" : "−"}${Math.abs(change).toFixed(1)}%`;
}

function VisitorCountChart({ rows, previousAverage }) {
  const [hover, setHover] = useState(null);
  const left = 45;
  const right = 8;
  const top = 21;
  const height = 78;
  const peak = Math.max(1, ...rows.map((row) => row.visitors), previousAverage ?? 0);
  const ceiling = Math.ceil(peak * 1.12 / 1000) * 1000;
  const x = (index) => left + index * (WIDTH - left - right) / Math.max(1, rows.length - 1);
  const y = (value) => top + height * (1 - value / ceiling);
  const path = rows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(row.visitors).toFixed(1)}`).join(" ");
  const hoverRow = hover != null ? rows[hover.index] : null;
  return <div className="daily-peak-chart-wrap">
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="daily-peak-svg"
      role="img"
      aria-label={`${rows[0].date}부터 ${rows.at(-1).date}까지 일별 외지인 방문자 수. 최근 ${formatCount(rows.at(-1).visitors)}명.`}
      onMouseMove={(event) => setHover(pointFromMouse(event, rows.length, left, right))}
      onMouseLeave={() => setHover(null)}
    >
      <ChartGrid left={left} right={right} top={top} height={height} />
      {[0, 1].map((fraction) => <text key={fraction} x={left - 6} y={y(ceiling * fraction) + 3} textAnchor="end" fill="#75828b" fontSize="9">{formatCount(ceiling * fraction)}</text>)}
      {Number.isFinite(previousAverage) && <line x1={left} x2={WIDTH - right} y1={y(previousAverage)} y2={y(previousAverage)} stroke="#bc9279" strokeDasharray="5 5" />}
      <path d={path} fill="none" stroke="#287da6" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      {hoverRow && <line x1={x(hover.index)} x2={x(hover.index)} y1={top} y2={top + height} stroke="#9aa7ad" strokeDasharray="3 3" />}
      {hoverRow && <rect x={x(hover.index) - 3.6} y={y(hoverRow.visitors) - 3.6} width="7.2" height="7.2" fill="#287da6" stroke="white" strokeWidth="1.2" />}
      <circle cx={x(rows.length - 1)} cy={y(rows.at(-1).visitors)} r="5" fill="#287da6" stroke="white" strokeWidth="2" />
    </svg>
    {hoverRow && <div className="daily-peak-tooltip" style={{ left: hover.offsetX + x(hover.index) * hover.scale, top: hover.offsetY + y(hoverRow.visitors) * hover.scale }}>
      <strong>{hoverRow.date}</strong>
      <span>{formatCount(hoverRow.visitors)}명</span>
    </div>}
  </div>;
}

function SearchIndexChart({ rows, previousAverage, field, isRatio }) {
  const [hover, setHover] = useState(null);
  const left = 40;
  const right = 8;
  const top = 21;
  const height = 78;
  const values = rows.map((row) => row[field]);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const padding = Math.max((maximum - minimum) * 0.25, isRatio ? 0.05 : 2);
  const floor = Math.max(0, minimum - padding);
  const ceiling = maximum + padding;
  const x = (index) => left + index * (WIDTH - left - right) / Math.max(1, rows.length - 1);
  const y = (value) => top + height * (1 - (value - floor) / (ceiling - floor));
  const digits = isRatio ? 2 : 1;
  const metricLabel = isRatio ? "전년 같은 요일 대비 검색 배율의 7일 중앙값" : "지역 검색지수";
  const path = rows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(row[field]).toFixed(1)}`).join(" ");
  const hoverRow = hover != null ? rows[hover.index] : null;
  return <div className="daily-peak-chart-wrap">
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="daily-peak-svg"
      role="img"
      aria-label={`${rows[0].date}부터 ${rows.at(-1).date}까지 일별 ${metricLabel}. 최근 ${rows.at(-1)[field].toFixed(digits)}.${previousAverage == null ? " 직전 7일 비교 자료 없음." : ` 점선은 직전 7일 평균 ${previousAverage.toFixed(digits)}.`}`}
      onMouseMove={(event) => setHover(pointFromMouse(event, rows.length, left, right))}
      onMouseLeave={() => setHover(null)}
    >
      <ChartGrid left={left} right={right} top={top} height={height} />
      {[floor, ceiling].map((value) => <text key={value} x={left - 8} y={y(value) + 4} textAnchor="end" fill="#67808e" fontSize="10">{value.toFixed(isRatio ? 1 : 0)}</text>)}
      {Number.isFinite(previousAverage) && previousAverage >= floor && previousAverage <= ceiling && <line x1={left} x2={WIDTH - right} y1={y(previousAverage)} y2={y(previousAverage)} stroke="#7ebbd6" strokeDasharray="4 5" />}
      <path d={path} fill="none" stroke="#007fbe" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      {hoverRow && <line x1={x(hover.index)} x2={x(hover.index)} y1={top} y2={top + height} stroke="#9aa7ad" strokeDasharray="3 3" />}
      {hoverRow && <rect x={x(hover.index) - 3.6} y={y(hoverRow[field]) - 3.6} width="7.2" height="7.2" fill="#007fbe" stroke="white" strokeWidth="1.2" />}
      <circle cx={x(rows.length - 1)} cy={y(rows.at(-1)[field])} r="5" fill="#007fbe" stroke="white" strokeWidth="2" />
    </svg>
    {hoverRow && <div className="daily-peak-tooltip" style={{ left: hover.offsetX + x(hover.index) * hover.scale, top: hover.offsetY + y(hoverRow[field]) * hover.scale }}>
      <strong>{hoverRow.date}</strong>
      <span>{hoverRow[field].toFixed(digits)}{isRatio ? "배" : ""}</span>
    </div>}
  </div>;
}

function alertAt(data, asOf) {
  const history = data?.history ?? [];
  const records = data?.as_of && data?.alert_level ? [...history, data] : history;
  return records.reduce((latest, record) => record.as_of <= asOf && record.alert_level
    && (!latest || record.as_of > latest.as_of) ? record : latest, null);
}

function ForecastSummary({ envelope, statusEnvelope, statusAsOf, visitorIncreaseSignal }) {
  const days = envelope?.data?.daily ?? [];
  const daySeven = days.at(-1);
  const busiestDay = days.length ? days.reduce((best, day) => day.predicted > best.predicted ? day : best, days[0]) : null;
  const alert = alertAt(statusEnvelope?.data, statusAsOf);
  return <div className="brief-forecast-summary">
    <span>지금 우리 지역은?</span>
    <div className="brief-status-line">
      <strong>{alert ? `${alert.alert_level} 상태` : "판정 자료 없음"}</strong>
      {alert && <span className="brief-alert-asof">{labelDate(alert.as_of)} 판정</span>}
      {visitorIncreaseSignal !== null && <em className={`brief-observed-signal${visitorIncreaseSignal ? " is-detected" : ""}`}>실측 방문 · {visitorIncreaseSignal ? "증가 신호 감지" : "평소 수준"}</em>}
    </div>
    <small>{daySeven ? `${labelDate(days[0].date)}~${labelDate(daySeven.date)} 방문 전망 · 최다 예상 ${labelDate(busiestDay.date)} ${formatCount(busiestDay.predicted)}명` : "방문 예측 자료 연결 전"}</small>
  </div>;
}

export default function DailySignalChart({ envelope, forecastEnvelope, statusEnvelope }) {
  const [rangeDays, setRangeDays] = useState(7);
  const data = envelope.data;
  const { daily } = alignedSignalSeries(data);
  const valid = daily.filter((row) => Number.isFinite(row.visitors));
  if (!valid.length) return <div className="daily-peak">외지인 방문 추이 자료가 없습니다.</div>;
  const visitorRows = valid.slice(-rangeDays);
  const latest = valid.at(-1);
  const visitorIncreaseSignal = summarizeVisitorSignal(data).detected;
  const previousDate = new Date(`${latest.date}T00:00:00Z`);
  previousDate.setUTCDate(previousDate.getUTCDate() - 7);
  const previousDay = daily.find((row) => row.date === previousDate.toISOString().slice(0, 10) && Number.isFinite(row.visitors));
  const recentWeek = valid.slice(-7);
  const previousWeek = valid.slice(-14, -7);
  const lastFourteen = valid.slice(-14);
  const completeWeeks = lastFourteen.length === 14 && lastFourteen.every((row, index) => index === 0
    || Date.parse(`${row.date}T00:00:00Z`) - Date.parse(`${lastFourteen[index - 1].date}T00:00:00Z`) === 86400000);
  const recentTotal = completeWeeks ? recentWeek.reduce((sum, row) => sum + row.visitors, 0) : null;
  const previousTotal = completeWeeks ? previousWeek.reduce((sum, row) => sum + row.visitors, 0) : null;
  const weekChange = percentChange(recentTotal, previousTotal);
  const dayChange = percentChange(latest.visitors, previousDay?.visitors);
  const searchField = daily.some((row) => Number.isFinite(row.search_index)) ? "search_index" : "search_stat";
  const searchIsRatio = searchField === "search_stat";
  const searchValid = daily.filter((row) => Number.isFinite(row[searchField]));
  const searchRows = searchValid.slice(-rangeDays);
  const search = searchRows.at(-1);
  const searchLastFourteen = searchValid.slice(-14);
  const completeSearchWeeks = searchLastFourteen.length === 14 && searchLastFourteen.every((row, index) => index === 0
    || Date.parse(`${row.date}T00:00:00Z`) - Date.parse(`${searchLastFourteen[index - 1].date}T00:00:00Z`) === 86400000);
  const searchWeekAverage = completeSearchWeeks ? searchLastFourteen.slice(-7).reduce((sum, row) => sum + row[searchField], 0) / 7 : null;
  const previousSearchAverage = completeSearchWeeks ? searchLastFourteen.slice(0, 7).reduce((sum, row) => sum + row[searchField], 0) / 7 : null;
  const searchWeekChange = percentChange(searchWeekAverage, previousSearchAverage);
  const searchPreviousWeekday = completeSearchWeeks ? searchLastFourteen[6] : null;
  const searchDayChange = percentChange(search?.[searchField], searchPreviousWeekday?.[searchField]);
  const searchMovement = searchWeekChange === null ? "최근 검색 흐름을 확인하세요" : `최근 7일 검색 관심 ${changeLabel(searchWeekChange)}`;

  return <section className="daily-peak actual-signal" aria-label="오늘의 방문·검색 브리핑">
    <div className="daily-peak-meta"><span className="daily-peak-mock">검색·방문 현황</span><span>자료 기준 {latest.date}</span></div>
    <div className="daily-peak-heading"><h3>{searchMovement}</h3><div className="daily-peak-range" role="group" aria-label="추이 기간 선택">{RANGES.map((range) => <button key={range.days} type="button" className={rangeDays === range.days ? "is-active" : ""} aria-pressed={rangeDays === range.days} onClick={() => setRangeDays(range.days)}>{range.label}</button>)}</div></div>
    <div className="daily-peak-stats briefing-stats">
      <span>{searchIsRatio ? "지역 검색 배율" : "지역 검색지수"} <strong>{search ? `${search[searchField].toFixed(searchIsRatio ? 2 : 1)}${searchIsRatio ? "배" : ""}` : "—"}</strong><small>전주 동요일 {compactChangeLabel(searchDayChange)} · 최근 7일 {compactChangeLabel(searchWeekChange)}</small></span>
      <span>외지인 방문 <strong>{formatCount(latest.visitors)}명</strong><small>전주 동요일 {compactChangeLabel(dayChange)} · 최근 7일 {compactChangeLabel(weekChange)}</small></span>
      <ForecastSummary envelope={forecastEnvelope} statusEnvelope={statusEnvelope} statusAsOf={latest.date} visitorIncreaseSignal={visitorIncreaseSignal} />
    </div>
    <div className="brief-chart-grid">
      {searchRows.length > 0 && <div className="brief-chart-card search-chart-card"><div className="brief-chart-title"><strong>지역 검색 추이</strong><span>{searchIsRatio ? "전년 같은 요일 대비 · 7일 중앙값" : "일별 상대 검색지수"}</span></div><SearchIndexChart rows={searchRows} previousAverage={previousSearchAverage} field={searchField} isRatio={searchIsRatio} /></div>}
      <div className="brief-chart-card visitor-chart-card"><div className="brief-chart-title"><strong>외지인 방문 추이</strong><span>일별 방문자 · 명</span></div><VisitorCountChart rows={visitorRows} previousAverage={previousTotal === null ? null : previousTotal / 7} /></div>
    </div>
    <div className={forecastEnvelope?.data?.daily?.length ? "daily-peak-next has-forecast" : "daily-peak-next"}>
      <a href="#area2"><span><strong>관련 콘텐츠 확인</strong><small>지역 관련 콘텐츠의 수집 결과를 살펴보세요.</small></span><span aria-hidden="true">→</span></a>
      {forecastEnvelope?.data?.daily?.length > 0 && <a href="#forecast"><span><strong>7일 예측 확인</strong><small>앞으로 7일간의 방문 예측을 살펴보세요.</small></span><span aria-hidden="true">→</span></a>}
      <a href="#area1"><span><strong>심층 보고서</strong><small>방문 신호의 근거와 대응 체크리스트를 살펴보세요.</small></span><span aria-hidden="true">→</span></a>
    </div>
    <div className="actual-signal-source"><SourceBadge envelope={envelope} /><CaveatNote envelope={envelope} /></div>
  </section>;
}
