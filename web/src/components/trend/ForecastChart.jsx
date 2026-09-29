import { useMemo, useState } from "react";
import {
  COLOR,
  DAY,
  fmtInt,
  fmtMD,
  linear,
  niceMax,
  niceTicks,
  pathOf,
  toTime,
  useElementWidth,
  weekdayOf,
  fix,
} from "../common/chart/chartKit.js";

// 최근 실측 → (7일 전에 냈던 예측 = 백테스트) → 데이터 기준일 → 앞으로 7일 예측과 80% 구간.
// 과거 구간에 백테스트를 겹쳐 '이 모델이 평소 얼마나 맞았는지'를 예측과 같은 화면에서 보게 한다.
const M = { top: 22, right: 14, bottom: 42, left: 52 };
const PLOT_H = 210;
const HISTORY_DAYS = 42;

export default function ForecastChart({ forecast, series }) {
  const [ref, width] = useElementWidth(520);
  const [hover, setHover] = useState(null);
  const model = useMemo(() => buildModel(forecast, series), [forecast, series]);
  const { rows, cut, peak, backtest } = model;

  const innerW = Math.max(200, width - M.left - M.right);
  const t0 = rows[0].t;
  const t1 = rows[rows.length - 1].t;
  const x = linear([t0 - DAY / 2, t1 + DAY / 2], [M.left, M.left + innerW]);
  const yMax = niceMax(Math.max(...rows.flatMap((r) => [r.actual ?? 0, r.upper ?? 0, r.backtest ?? 0])));
  const y = linear([0, yMax], [M.top + PLOT_H, M.top]);
  const height = M.top + PLOT_H + M.bottom;

  const future = rows.filter((r) => r.predicted != null);
  const band =
    future.map((r, i) => `${i ? "L" : "M"}${x(r.t)},${y(r.upper)}`).join("") +
    [...future].reverse().map((r) => `L${x(r.t)},${y(r.lower)}`).join("") +
    "Z";
  const lastActual = [...rows].reverse().find((r) => r.actual != null);
  const bridge = lastActual ? [[x(lastActual.t), y(lastActual.actual)], ...future.map((r) => [x(r.t), y(r.predicted)])] : [];

  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round((x.invert(e.clientX - box.left) - t0) / DAY);
    setHover(i >= 0 && i < rows.length ? i : null);
  };
  const h = hover == null ? null : rows[hover];

  return (
    <div className="trend-chart" ref={ref}>
      <div className="stat-row">
        <div className="stat-tile">
          <p className="stat-tile__label">7일 중 최대 예상</p>
          <p className="stat-tile__value">{fmtInt(peak.predicted)}<small>명</small></p>
          <p className="stat-tile__sub">{fmtMD(peak.date)}({weekdayOf(peak.date)}) · 80% 구간 {fmtInt(peak.lower)}~{fmtInt(peak.upper)}</p>
        </div>
        {backtest && (
          <div className="stat-tile">
            <p className="stat-tile__label">이 지역 예측 오차 (2026 백테스트)</p>
            <p className="stat-tile__value">{fix(backtest.smape, 1)}<small>%</small></p>
            <p className="stat-tile__sub">평균 {fmtInt(backtest.mae)}명 · 전국 {fix(backtest.national_smape, 2)}%</p>
          </div>
        )}
      </div>

      <div className="chart-legend" aria-hidden="true">
        <span><i className="swatch-line" style={{ background: COLOR.visitors }} />실측 외지인 방문자</span>
        {backtest && <span><i className="swatch-line swatch-dash" style={{ borderColor: COLOR.search }} />7일 전에 낸 예측(백테스트)</span>}
        <span><i className="swatch-line swatch-dash" style={{ borderColor: COLOR.visitors }} />앞으로 7일 예측</span>
        <span><i className="swatch-band" />80% 구간</span>
      </div>

      <div className="chart-stage">
        <svg width={width} height={height} role="img" aria-label="최근 실측과 7일 방문객 예측" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {niceTicks(0, yMax, 4).map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + innerW} y1={y(v)} y2={y(v)} stroke={COLOR.grid} />
              <text x={M.left - 8} y={y(v) + 4} className="chart-tick" textAnchor="end">{compact(v)}</text>
            </g>
          ))}
          <rect x={x(cut + DAY / 2)} y={M.top} width={M.left + innerW - x(cut + DAY / 2)} height={PLOT_H} fill="rgba(0, 137, 122, 0.05)" />
          <line x1={x(cut + DAY / 2)} x2={x(cut + DAY / 2)} y1={M.top - 6} y2={M.top + PLOT_H} stroke={COLOR.axis} />
          <text x={x(cut + DAY / 2) - 6} y={M.top - 8} className="chart-note" textAnchor="end">데이터 기준일 {fmtMD(model.cutIso)}</text>
          <text x={x(cut + DAY / 2) + 6} y={M.top - 8} className="chart-note chart-note--strong" fill={COLOR.visitors}>예측</text>

          <path d={band} fill={COLOR.visitors} opacity="0.14" />
          <path d={pathOf(rows.map((r) => [x(r.t), r.backtest == null ? null : y(r.backtest)]))} fill="none" stroke={COLOR.search} strokeWidth="1.5" strokeDasharray="4 3" />
          <path d={pathOf(rows.map((r) => [x(r.t), r.actual == null ? null : y(r.actual)]))} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeLinejoin="round" />
          <path d={pathOf(bridge)} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeDasharray="6 4" />
          {future.map((r) => (
            <circle key={r.iso} cx={x(r.t)} cy={y(r.predicted)} r={r.iso === peak.date ? 5 : 3.5} fill={r.iso === peak.date ? COLOR.visitors : "#fff"} stroke={COLOR.visitors} strokeWidth="2" />
          ))}
          <text x={x(toTime(peak.date))} y={y(peak.upper) - 8} className="chart-note chart-note--strong" textAnchor="middle">
            {fmtInt(peak.predicted)}명
          </text>

          <line x1={M.left} x2={M.left + innerW} y1={M.top + PLOT_H} y2={M.top + PLOT_H} stroke={COLOR.axis} />
          {rows.map((r, i) =>
            i % 7 === (rows.length - 1) % 7 ? (
              <text key={`x${r.iso}`} x={x(r.t)} y={M.top + PLOT_H + 16} className="chart-tick" textAnchor="middle">{fmtMD(r.iso)}</text>
            ) : null
          )}
          {holidayMarks(rows, x).map((r) => (
            <g key={`h${r.iso}`}>
              <line x1={x(r.t)} x2={x(r.t)} y1={M.top + PLOT_H} y2={M.top + PLOT_H + 22} stroke={COLOR.threshold} strokeOpacity="0.5" />
              <text x={x(r.t) + 3} y={M.top + PLOT_H + 32} className="chart-note">{fmtMD(r.iso)} {r.holidayLabel}</text>
            </g>
          ))}

          {h && (
            <g pointerEvents="none">
              <line x1={x(h.t)} x2={x(h.t)} y1={M.top} y2={M.top + PLOT_H} stroke={COLOR.ink} strokeOpacity="0.4" />
              {h.actual != null && <circle cx={x(h.t)} cy={y(h.actual)} r="4.5" fill={COLOR.visitors} stroke="#fff" strokeWidth="2" />}
              {h.backtest != null && <circle cx={x(h.t)} cy={y(h.backtest)} r="4" fill={COLOR.search} stroke="#fff" strokeWidth="2" />}
            </g>
          )}
          <rect x={M.left} y={M.top} width={innerW} height={PLOT_H} fill="transparent" />
        </svg>

        {h && (
          <div className="chart-tooltip" style={{ left: Math.min(x(h.t) + 12, width - 220), top: M.top + 10 }}>
            <p className="chart-tooltip__date">{h.iso} ({weekdayOf(h.iso)}){h.holidayLabel ? ` · ${h.holidayLabel}` : ""}</p>
            {h.actual != null && (
              <p className="chart-tooltip__row"><i style={{ background: COLOR.visitors }} /><span>실측</span><b>{fmtInt(h.actual)}명</b></p>
            )}
            {h.backtest != null && (
              <p className="chart-tooltip__row">
                <i style={{ background: COLOR.search }} /><span>7일 전 예측</span><b>{fmtInt(h.backtest)}명</b>
                {h.actual != null && <em>{signedPct(h.backtest / h.actual - 1)}</em>}
              </p>
            )}
            {h.predicted != null && (
              <>
                <p className="chart-tooltip__row"><i style={{ background: COLOR.visitors }} /><span>예측</span><b>{fmtInt(h.predicted)}명</b></p>
                <p className="chart-tooltip__row"><i className="swatch-band-mini" /><span>80% 구간</span><b>{fmtInt(h.lower)}~{fmtInt(h.upper)}</b></p>
              </>
            )}
            {h.event && <p className="chart-tooltip__event">축제: {h.event}</p>}
          </div>
        )}
      </div>

      <ul className="peak-list">
        {forecast.peak_days.map((p) => (
          <li key={p.date}>
            <b>{fmtMD(p.date)}</b> {fmtInt(p.predicted)}명 <span>{p.reason}</span>
          </li>
        ))}
      </ul>

      <WeekdayBars weekdays={forecast.weekday_concentration} />

      <details className="chart-table">
        <summary>표로 보기</summary>
        <table>
          <thead>
            <tr>
              <th>날짜</th>
              <th>실측</th>
              <th>7일 전 예측</th>
              <th>예측</th>
              <th>80% 구간</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.iso}>
                <td>{r.iso} ({weekdayOf(r.iso)})</td>
                <td>{r.actual == null ? "–" : fmtInt(r.actual)}</td>
                <td>{r.backtest == null ? "–" : fmtInt(r.backtest)}</td>
                <td>{r.predicted == null ? "–" : fmtInt(r.predicted)}</td>
                <td>{r.predicted == null ? "–" : `${fmtInt(r.lower)}~${fmtInt(r.upper)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function buildModel(forecast, series) {
  const daily = forecast.daily;
  const firstT = toTime(daily[0].date);
  const cut = firstT - DAY;
  const history = (series?.daily ?? []).filter((d) => {
    const t = toTime(d.date);
    return t <= cut && t > cut - HISTORY_DAYS * DAY;
  });
  const rows = [
    ...history.map((d) => ({ iso: d.date, t: toTime(d.date), actual: d.visitors, backtest: d.backtest })),
    ...daily.map((d) => ({
      iso: d.date,
      t: toTime(d.date),
      predicted: d.predicted,
      lower: d.lower,
      upper: d.upper,
      isHoliday: d.is_holiday,
      event: d.event,
    })),
  ];
  // 공휴일 이름은 peak_days.reason에만 들어 있다 ("토요일 · 광복절 · 3일 연휴")
  const reasons = new Map(forecast.peak_days.map((p) => [p.date, p.reason]));
  for (const r of rows) {
    if (!r.isHoliday) continue;
    const reason = reasons.get(r.iso);
    r.holidayLabel = reason?.split(" · ")[1] ?? "공휴일";
  }
  const peak = [...daily].sort((a, b) => b.predicted - a.predicted)[0];
  return {
    rows,
    cut,
    cutIso: new Date(cut).toISOString().slice(0, 10),
    peak,
    backtest: series?.backtest ?? null,
  };
}

// 공휴일 이름표는 서로 70px 이상 떨어진 것만 (나머지는 툴팁과 표에 있다)
function holidayMarks(rows, x) {
  const out = [];
  for (const r of rows) {
    if (!r.isHoliday) continue;
    if (out.length && x(r.t) - x(out[out.length - 1].t) < 70) continue;
    out.push(r);
  }
  return out;
}

function WeekdayBars({ weekdays }) {
  const max = Math.max(...weekdays.map((w) => w.ratio));
  return (
    <div className="weekday-bars">
      <p className="weekday-bars__title">요일별 방문 비중 (최근 1년 실측)</p>
      <div className="weekday-bars__row">
        {weekdays.map((w) => (
          <div key={w.weekday} className="weekday-bars__col" title={`${w.weekday}요일 ${(w.ratio * 100).toFixed(1)}%`}>
            <span className="weekday-bars__val">{(w.ratio * 100).toFixed(0)}%</span>
            <span className="weekday-bars__bar" style={{ height: `${(w.ratio / max) * 56}px`, background: w.ratio === max ? COLOR.visitors : COLOR.context }} />
            <span className="weekday-bars__lab">{w.weekday}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function compact(v) {
  if (v >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return v.toLocaleString("ko-KR");
}

function signedPct(v) {
  const p = Math.round(v * 100);
  return `${p > 0 ? "+" : ""}${p}%`;
}
