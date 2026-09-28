import { useState } from "react";
import { useRegionData } from "../../hooks/useRegionData.js";
import DataState from "../common/DataState.jsx";
import { mockReviewSummary } from "./mockReviewSummary.js";

export default function DailyPeakChart({ region }) {
  const result = useRegionData("daily_peak", region);
  return <DataState result={result} render={({ envelope }) => <PeakPlot envelope={envelope} />} />;
}

function PeakPlot({ envelope }) {
  const [hovered, setHovered] = useState(null);
  const { points, baseline, as_of } = envelope.data;
  const review = mockReviewSummary(envelope);
  const last = points.at(-1);
  const previous = points.filter((point) => point.date >= baseline.start && point.date <= baseline.end && Number.isFinite(point.value));
  const average = previous.length ? previous.reduce((sum, point) => sum + point.value, 0) / previous.length : null;
  const peak = Number.isFinite(last.value) && last.value > baseline.upper;
  const pastPeakIndex = points.reduce((best, point, i) => (point.value ?? -Infinity) > (points[best].value ?? -Infinity) ? i : best, 0);
  const settled = Number.isFinite(last.value) && last.value >= baseline.lower && last.value <= baseline.upper && points[pastPeakIndex].value > baseline.upper;
  let normalDays = 0;
  for (let i = points.length - 1; i >= 0 && Number.isFinite(points[i].value) && points[i].value >= baseline.lower && points[i].value <= baseline.upper; i--) normalDays++;
  const ratio = average > 0 && Number.isFinite(last.value) ? last.value / average : null;
  let sustained = 0;
  for (let i = points.length - 1; i >= 0 && Number.isFinite(points[i].value) && points[i].value > baseline.upper; i--) sustained++;
  const startIndex = sustained ? points.length - sustained : -1;
  const max = Math.max(baseline.upper, ...points.map((p) => p.value ?? 0), 400) * 1.25;
  const x = (i) => 52 + i * 650 / Math.max(1, points.length - 1);
  const y = (value) => 232 - value / max * 200;
  const active = points[hovered ?? points.length - 1];
  const path = points.map((p, i) => Number.isFinite(p.value) ? `${i === 0 || !Number.isFinite(points[i - 1].value) ? "M" : "L"}${x(i)},${y(p.value)}` : "").join(" ");
  return <section className={`daily-peak${!peak ? " is-settled" : ""}`} aria-label="일별 SNS 언급량 변화 예시">
    <div className="daily-peak-meta"><span className="daily-peak-mock">{envelope._mock ? "목업 · 화면 설명용 예시" : "관측 데이터"}</span><span>{envelope._mock ? "예시 " : ""}기준일 {as_of}</span></div>
    <div className="daily-peak-heading"><div><h3>{!Number.isFinite(last.value) ? "자료 수집 대기" : peak ? "우리 지역 언급이 늘어나고 있어요" : settled ? "우리 지역 언급이 평소 수준으로 돌아왔어요" : "우리 지역 언급은 평소 수준이에요"}</h3></div><span className={`daily-peak-status${peak ? " is-peak" : ""}`}>{!Number.isFinite(last.value) ? "자료 미수집" : sustained > 1 ? `${sustained}일째 관심 증가` : peak ? "관심 증가" : settled ? `${normalDays}일째 평소 수준` : "평소 수준"}{envelope._mock && " · 예시"}</span></div>
    <div className="daily-peak-stats"><span>평소 <strong>{average == null ? "—" : Math.round(average).toLocaleString("ko-KR")}건</strong></span><span aria-hidden="true">→</span><span>{envelope._mock ? "예시 기준일" : "최근 관측일"} <strong>{last.value == null ? "—" : last.value.toLocaleString("ko-KR")}건</strong></span>{ratio != null && <b>평소의 {ratio.toFixed(1)}배</b>}</div>
    <div className="daily-peak-readout" aria-live="polite">{active.date.slice(5).replace("-", "/")} · SNS 언급량 {active.value == null ? "미수집" : `${active.value.toLocaleString("ko-KR")}건`}</div>
    <svg viewBox="0 0 760 275" className="daily-peak-svg" role="group" aria-label={`SNS 언급량 예시. 이전 평균 약 ${Math.round(average ?? 0)}건에서 증감을 거쳐 최근 ${last.value ?? '미수집'}건. ${settled ? `관심 상승 후 ${normalDays}일째 평소 수준.` : peak ? `${sustained}일 연속 평소 범위 초과.` : '현재 급증 없음.'}`}>
      {sustained > 1 && <rect x={x(startIndex)} y="24" width={702 - x(startIndex)} height="208" fill="#fff4ee" />}
      {[0, 200, 400, 600].filter((value) => value <= max).map((value) => <g key={value}><line x1="52" x2="702" y1={y(value)} y2={y(value)} stroke="#eeebf0" /><text x="42" y={y(value) + 4} textAnchor="end" fontSize="11" fill="#827b89">{value}</text></g>)}
      <rect x="52" y={y(baseline.upper)} width="650" height={y(baseline.lower) - y(baseline.upper)} fill="#eee9f7" />
      <text x="62" y={y(baseline.upper) - 9} fontSize="11" fill="#87789a">평소 범위 · 예시</text>
      <path d={path} fill="none" stroke="#9584b8" strokeWidth="3" strokeLinejoin="round" />
      {points.slice(1).map((point, i) => Number.isFinite(point.value) && Number.isFinite(points[i].value) && (point.value > baseline.upper || points[i].value > baseline.upper) ? <line key={point.date} x1={x(i)} y1={y(points[i].value)} x2={x(i + 1)} y2={y(point.value)} stroke="#d76850" strokeWidth="3" /> : null)}
      {sustained > 1 && <g><line x1={x(startIndex)} x2={x(startIndex)} y1="46" y2="232" stroke="#dba48e" strokeDasharray="4 4" /><text x={x(startIndex) - 8} y="37" textAnchor="end" fontSize="11" fill="#b6533d">{points[startIndex].date.slice(5).replace("-", "/")} 관심 증가 시작</text></g>}
      {points.map((point, i) => <g key={point.date}>
        {Number.isFinite(point.value) && <circle cx={x(i)} cy={y(point.value)} r={i === points.length - 1 ? 7 : 4} fill={point.value > baseline.upper ? "#d76850" : "#9584b8"} stroke="white" strokeWidth="2" tabIndex="0" role="img" aria-label={`${point.date}, ${point.value}건`} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(i)} onBlur={() => setHovered(null)}><title>{point.date}: {point.value}건</title></circle>}
        {(i % 4 === 0 || i === points.length - 1) && <text x={x(i)} y="256" textAnchor="middle" fontSize="11" fill="#827b89">{point.date.slice(5).replace("-", "/")}</text>}
      </g>)}
      {peak && <g><rect x="627" y={y(last.value) - 42} width="118" height="27" rx="8" fill="#fff0e9" /><text x="686" y={y(last.value) - 24} textAnchor="middle" fontSize="12" fontWeight="700" fill="#b6533d">최근 · {last.value}건</text></g>}
      {settled && <g>
        <text x={x(pastPeakIndex)} y={y(points[pastPeakIndex].value) - 16} textAnchor="middle" fontSize="12" fontWeight="700" fill="#b6533d">지난 정점 · {points[pastPeakIndex].value}건</text>
        <rect x="610" y={y(last.value) - 44} width="140" height="27" rx="8" fill="#eee9f7" />
        <text x="680" y={y(last.value) - 26} textAnchor="middle" fontSize="12" fontWeight="700" fill="#007fbe">최근 · {last.value}건 · 평소 수준</text>
      </g>}
    </svg>
    <div className="daily-peak-legend"><span><i />일별 언급량</span><span><i />평소 범위</span><span><i />관심 증가 구간</span></div>
    {review && <div className="peak-review-summary" aria-label="목업 기준 검토 상태와 권고사항">
      <div className="peak-review-heading"><strong>{review.label}</strong></div>
      <p>{review.summary}</p>
      <p className="peak-review-action"><b>현재 권고</b>{review.action}</p>
    </div>}
    <div className="daily-peak-next">
      <a href="#area2"><span><strong>관련 콘텐츠 확인</strong><small>우리 지역이 어떤 이야기로 언급되는지 살펴보세요.</small></span><span aria-hidden="true">→</span></a>
      <a href="#area1"><span><strong>심층 보고서</strong><small>방문 신호의 근거와 정책 브리핑을 살펴보세요.</small></span><span aria-hidden="true">→</span></a>
    </div>
  </section>;
}
