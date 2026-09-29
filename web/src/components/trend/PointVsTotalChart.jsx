import { useMemo, useState } from "react";
import { COLOR, fmtInt, fmtYM, log2Scale, useElementWidth, fix } from "../common/chart/chartKit.js";

// 같은 잣대(전년 같은 달 대비 배율)로 관광지점과 시군구 총량을 겹쳐 그린다. 둘 다 '배율'이라
// 한 축에 올려도 된다. 배율은 곱셈 척도라 로그축(2배 간격)으로 그려야 0.5배와 2배가 같은 거리로 보인다.
// 강조는 가장 크게 뛴 지점 하나(주황)와 시군구 총량(진한 선)만. 나머지 지점은 회색 맥락선이다.
const M = { top: 18, right: 112, bottom: 28, left: 44 };
const PLOT_H = 230;

// outlook이 있으면 시군구 총량선을 6개월 전망(작년 같은 달 대비 배율)까지 잇는다. 지점은 예측하지
// 않는다 — 지점 급증을 미리 가려내는 판별력이 없었다(AUC 0.482).
export default function PointVsTotalChart({ points, regionName, outlook }) {
  const [ref, width] = useElementWidth(520);
  const [hover, setHover] = useState(null);
  const model = useMemo(() => buildModel(points, outlook), [points, outlook]);

  if (!model) {
    return (
      <div className="chart-empty">
        이 지역은 전년 같은 달과 짝지을 수 있는 관광지점 입장객 자료가 없어 지점 비교를 그리지 않습니다.
      </div>
    );
  }
  const { months, total, attractions, lead, headline, yMax, yMin, firstFuture } = model;
  const innerW = Math.max(160, width - M.left - M.right);
  const step = months.length > 1 ? innerW / (months.length - 1) : innerW;
  const x = (i) => M.left + i * step;
  const y = log2Scale([yMin, yMax], [M.top + PLOT_H, M.top]);
  const height = M.top + PLOT_H + M.bottom;
  const ticks = [0.5, 1, 2, 4, 8, 16, 32].filter((v) => v >= yMin && v <= yMax);

  const lineOf = (series) => {
    let d = "";
    let pen = false;
    months.forEach((m, i) => {
      const v = series.get(m);
      if (v == null) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round((e.clientX - box.left - M.left) / step);
    setHover(i >= 0 && i < months.length ? i : null);
  };

  const hMonth = hover == null ? null : months[hover];
  // 두 번째로 크게 뛴 지점도 급증 기준을 넘었으면 이름을 단다(영월: 단종장릉 13.5배·청령포 11.9배)
  const second = attractions[1] && attractions[1].max >= points.surge ? attractions[1] : null;
  const labelY = spreadLabels([
    { key: "total", y: lastY(total.values, months, y) },
    { key: "lead", y: lastY(lead.values, months, y) },
    { key: "second", y: second ? lastY(second.values, months, y) : null },
  ]);

  return (
    <div className="trend-chart" ref={ref}>
      {headline && (
        <div className="stat-duo">
          <div>
            <p className="stat-duo__label">{headline.name} · {fmtYM(headline.month)}</p>
            <p className="stat-duo__value" style={{ color: COLOR.accent }}>{fix(headline.ratio, 1)}배</p>
            <p className="stat-duo__sub">{fmtInt(headline.prev)} → {fmtInt(headline.visitors)}명</p>
          </div>
          <div className="stat-duo__vs">같은 달</div>
          <div>
            <p className="stat-duo__label">{regionName} 전체 외지인 방문자</p>
            <p className="stat-duo__value">{headline.totalRatio == null ? "–" : `${fix(headline.totalRatio, 2)}배`}</p>
            <p className="stat-duo__sub">
              {headline.totalRatio == null
                ? "해당 달 시군구 자료 없음"
                : headline.totalRatio < points.flat
                  ? `총량 기준(${points.flat}배 미만)으로는 '이상 없음'`
                  : `지점 증가폭(+${fix((headline.ratio - 1) * 100, 0)}%)의 약 1/${Math.round((headline.ratio - 1) / (headline.totalRatio - 1))} 수준`}
            </p>
          </div>
        </div>
      )}

      <div className="chart-legend" aria-hidden="true">
        <span><i className="swatch-line swatch-thick" style={{ background: COLOR.total }} />{regionName} 총량</span>
        <span><i className="swatch-line" style={{ background: COLOR.accent }} />{lead.name}</span>
        {attractions.length > 1 && <span><i className="swatch-line" style={{ background: COLOR.context }} />그 밖의 지점 {attractions.length - 1}곳</span>}
        <span><i className="swatch-line swatch-dash" style={{ borderColor: COLOR.threshold }} />지점 급증 {points.surge}배</span>
      </div>

      <div className="chart-stage">
        <svg width={width} height={height} role="img" aria-label={`${regionName} 관광지점과 시군구 총량의 전년 대비 배율`}
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + innerW} y1={y(v)} y2={y(v)} stroke={v === 1 ? COLOR.axis : COLOR.grid} />
              <text x={M.left - 8} y={y(v) + 4} className="chart-tick" textAnchor="end">{v}배</text>
            </g>
          ))}
          <line x1={M.left} x2={M.left + innerW} y1={y(points.surge)} y2={y(points.surge)} stroke={COLOR.threshold} strokeDasharray="5 4" strokeWidth="1.25" />

          {attractions.filter((a) => a !== lead).map((a) => (
            <path key={a.name} d={lineOf(a.values)} fill="none" stroke={COLOR.context} strokeWidth="1.5" opacity="0.8" />
          ))}
          <path d={lineOf(lead.values)} fill="none" stroke={COLOR.accent} strokeWidth="2" strokeLinejoin="round" />
          {firstFuture >= 0 && (
            <g>
              <rect x={x(firstFuture) - step / 2} y={M.top} width={M.left + innerW - x(firstFuture) + step / 2} height={PLOT_H} fill="rgba(0, 137, 122, 0.05)" />
              <text x={(x(firstFuture) - step / 2 + M.left + innerW) / 2} y={M.top + PLOT_H - 22} className="chart-note chart-note--strong" textAnchor="middle">
                총량 전망
              </text>
              <text x={(x(firstFuture) - step / 2 + M.left + innerW) / 2} y={M.top + PLOT_H - 8} className="chart-note" textAnchor="middle">
                지점은 예측 안 함(AUC 0.482)
              </text>
              <path d={lineOf(total.forecastPath)} fill="none" stroke={COLOR.total} strokeWidth="2.5" strokeDasharray="6 4" />
              {months.map((m, i) =>
                total.forecast.get(m) == null ? null : (
                  <circle key={`f${m}`} cx={x(i)} cy={y(total.forecast.get(m))} r="3.5" fill="#fff" stroke={COLOR.total} strokeWidth="2" />
                )
              )}
            </g>
          )}
          <path d={lineOf(total.values)} fill="none" stroke={COLOR.total} strokeWidth="3" strokeLinejoin="round" />
          {months.map((m, i) =>
            total.values.get(m) == null ? null : (
              <circle key={`t${m}`} cx={x(i)} cy={y(total.values.get(m))} r="3.5" fill={COLOR.total} stroke="#fff" strokeWidth="2" />
            )
          )}
          {headline && (
            <circle cx={x(months.indexOf(headline.month))} cy={y(headline.ratio)} r="5" fill={COLOR.accent} stroke="#fff" strokeWidth="2" />
          )}

          {/* 직접 라벨: 오른쪽 끝 */}
          <text x={M.left + innerW + 8} y={labelY.total + 4} className="chart-direct" fill={COLOR.ink}>{regionName} 총량</text>
          <text x={M.left + innerW + 8} y={labelY.lead + 4} className="chart-direct" fill={COLOR.ink}>{truncate(lead.name, 8)}</text>
          {second && (
            <text x={M.left + innerW + 8} y={labelY.second + 4} className="chart-direct" fill={COLOR.inkSoft} fontWeight="600">{truncate(second.name, 8)}</text>
          )}

          <line x1={M.left} x2={M.left + innerW} y1={M.top + PLOT_H} y2={M.top + PLOT_H} stroke={COLOR.axis} />
          {months.map((m, i) =>
            (months.length > 16 ? i % 3 !== (months.length - 1) % 3 : months.length > 8 && i % 2 === 1 && i !== months.length - 1) ? null : (
              <text key={`mx${m}`} x={x(i)} y={M.top + PLOT_H + 18} className="chart-tick" textAnchor="middle">{fmtYM(m)}</text>
            )
          )}

          {hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + PLOT_H} stroke={COLOR.ink} strokeOpacity="0.4" pointerEvents="none" />
          )}
          <rect x={M.left - step / 2} y={M.top} width={innerW + step} height={PLOT_H} fill="transparent" />
        </svg>

        {hMonth && (
          <div className="chart-tooltip" style={{ left: Math.min(x(hover) + 12, width - 250), top: M.top }}>
            <p className="chart-tooltip__date">{hMonth} · 전년 같은 달 대비</p>
            <p className="chart-tooltip__row">
              <i style={{ background: COLOR.total }} />
              <span>{regionName} 총량{total.forecast.has(hMonth) ? " (전망)" : ""}</span>
              <b>
                {total.forecast.has(hMonth)
                  ? `${fix(total.forecast.get(hMonth), 2)}배`
                  : total.values.get(hMonth) == null
                    ? "자료 없음"
                    : `${fix(total.values.get(hMonth), 2)}배`}
              </b>
            </p>
            {attractions
              .map((a) => ({ a, v: a.values.get(hMonth), raw: a.raw.get(hMonth) }))
              .filter((r) => r.v != null)
              .sort((p, q) => q.v - p.v)
              .map(({ a, v, raw }) => (
                <p key={a.name} className="chart-tooltip__row">
                  <i style={{ background: a === lead ? COLOR.accent : COLOR.context }} />
                  <span>{a.name}</span>
                  <b className={v >= points.surge ? "is-warn" : ""}>{fix(v, 2)}배</b>
                  <em>{fmtInt(raw.prev)}→{fmtInt(raw.visitors)}</em>
                </p>
              ))}
          </div>
        )}
      </div>

      <p className="chart-footnote">
        같은 지점·같은 달을 전년과 짝지어 비교했고, 전년 입장객 {points.min_base.toLocaleString("ko-KR")}명 미만 지점은 뺐습니다. 시군구 총량도 같은
        잣대(월 합계 전년 대비)로 쟀습니다. 지점 입장객은 월 단위이고 공개가 늦어 실시간 경보가 아니라 <b>다음 달 중점 관찰 대상</b>을 고르는 데 씁니다(D-16).
      </p>

      <details className="chart-table">
        <summary>표로 보기</summary>
        <table>
          <thead>
            <tr>
              <th>월</th>
              <th>{regionName} 총량</th>
              {attractions.map((a) => <th key={a.name}>{a.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {months.map((m) => (
              <tr key={m}>
                <td>{m}</td>
                <td>{total.values.get(m) == null ? "–" : `${fix(total.values.get(m), 2)}배`}</td>
                {attractions.map((a) => (
                  <td key={a.name}>{a.values.get(m) == null ? "–" : `${fix(a.values.get(m), 2)}배`}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function buildModel(points, outlook) {
  if (!points?.attractions?.length || !points.months?.length) return null;
  const total = { values: new Map(points.region_total.filter((r) => r.ratio != null).map((r) => [r.month, r.ratio])) };
  total.forecast = new Map();
  let months = points.months;
  let firstFuture = -1;
  if (outlook?.outlook?.length) {
    // 지점 자료가 끝난 뒤 ~ 전망 끝까지 달을 늘리고, 그 사이 실측 총량은 전망 파일의 월별 실측으로 채운다
    const last = months[months.length - 1];
    const end = outlook.outlook[outlook.outlook.length - 1].month;
    const extra = [];
    for (let m = nextMonth(last); m <= end; m = nextMonth(m)) extra.push(m);
    months = [...months, ...extra];
    for (const h of outlook.history) {
      if (h.full && h.ly && !total.values.has(h.month) && extra.includes(h.month)) total.values.set(h.month, h.visitors / h.ly);
    }
    for (const f of outlook.outlook) total.forecast.set(f.month, f.yoy);
    firstFuture = months.indexOf(outlook.outlook[0].month);
  }
  // 전망 점선은 마지막 실측 점에서 시작해 이어지게
  const lastActual = [...total.values.keys()].filter((m) => !total.forecast.has(m)).sort().pop();
  total.forecastPath = new Map([...(lastActual ? [[lastActual, total.values.get(lastActual)]] : []), ...total.forecast]);
  const attractions = points.attractions.map((a) => ({
    name: a.name,
    max: a.max_ratio,
    values: new Map(a.series.map((s) => [s.month, s.ratio])),
    raw: new Map(a.series.map((s) => [s.month, s])),
  }));
  const lead = attractions[0];

  let headline = null;
  for (const s of points.attractions[0].series) {
    if (!headline || s.ratio > headline.ratio) headline = { ...s, name: lead.name };
  }
  if (headline) headline.totalRatio = total.values.get(headline.month) ?? null;

  const all = [...total.values.values(), ...total.forecast.values(), ...attractions.flatMap((a) => [...a.values.values()])];
  const yMax = 2 ** Math.ceil(Math.log2(Math.max(4, ...all) * 1.05));
  const yMin = Math.min(0.5, 2 ** Math.floor(Math.log2(Math.min(...all) * 0.95)));
  return { months, total, attractions, lead, headline, yMax, yMin: Math.max(yMin, 0.125), firstFuture };
}

function nextMonth(m) {
  const [y, mo] = m.split("-").map(Number);
  return mo === 12 ? `${y + 1}-01` : `${y}-${String(mo + 1).padStart(2, "0")}`;
}

function lastY(values, months, y) {
  for (let i = months.length - 1; i >= 0; i -= 1) {
    const v = values.get(months[i]);
    if (v != null) return y(v);
  }
  return null;
}

// 두 직접 라벨이 겹치지 않게 최소 14px 띄운다
function spreadLabels(items) {
  const out = {};
  const valid = items.filter((it) => it.y != null).sort((a, b) => a.y - b.y);
  for (let i = 0; i < valid.length; i += 1) {
    if (i > 0 && valid[i].y - valid[i - 1].y < 14) valid[i].y = valid[i - 1].y + 14;
    out[valid[i].key] = valid[i].y;
  }
  for (const it of items) if (out[it.key] == null) out[it.key] = -100;
  return out;
}

function truncate(s, n) {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}
