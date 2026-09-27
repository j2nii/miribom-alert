import { useMemo, useState } from "react";
import {
  COLOR,
  DAY,
  fmtInt,
  fmtMD,
  fmtRatio,
  linear,
  monthLabel,
  monthTicks,
  niceMax,
  niceTicks,
  pathOf,
  toTime,
  trailingMean,
  useElementWidth,
  weekdayOf,
  fix,
} from "../common/chart/chartKit.js";

// 검색 배율(위)과 외지인 방문자(아래)를 같은 시간축으로 쌓는다. 두 지표는 단위가 달라
// 한 축에 겹치지 않는다(이중 축 금지). 타임라인 사건은 두 패널을 관통하는 세로선으로 표시한다.
const M = { left: 52, right: 16 };
const TOP_H = 150;
const GAP = 34;
const BOTTOM_H = 170;
const AXIS_H = 26;
const PIN_H = 40; // 사건 핀 두 줄 (가까운 사건은 아랫줄로 비켜 놓는다)
const PIN_ROWS = [10, 28];

const EVENT_ORDER = ["콘텐츠 확산", "검색 급증", "방문 급증", "혼잡 발생", "조치 시행"];

export default function SignalTrendChart({ series, timeline }) {
  const [ref, width] = useElementWidth();
  const [hover, setHover] = useState(null);

  const model = useMemo(() => buildModel(series, timeline), [series, timeline]);
  const { daily, t0, t1, events, episodes, thresholds, searchEnd, visitorsEnd } = model;

  const innerW = Math.max(200, width - M.left - M.right);
  const x = linear([t0, t1], [M.left, M.left + innerW]);

  const topY0 = PIN_H;
  const searchMax = niceMax(Math.max(thresholds.search * 1.25, ...daily.map((d) => d.search ?? 0)));
  const ySearch = linear([0, searchMax], [topY0 + TOP_H, topY0]);

  const botY0 = topY0 + TOP_H + GAP;
  const visMax = niceMax(Math.max(...daily.flatMap((d) => [d.visitorsRaw ?? 0, d.lyMean ?? 0])));
  const yVis = linear([0, visMax], [botY0 + BOTTOM_H, botY0]);
  const height = botY0 + BOTTOM_H + AXIS_H;

  const searchPts = daily.map((d) => [x(d.t), d.search == null ? null : ySearch(d.search)]);
  const aboveArea = areaAbove(daily, x, ySearch, thresholds.search);
  const rawPts = daily.map((d) => [x(d.t), d.visitorsRaw == null ? null : yVis(d.visitorsRaw)]);
  const meanPts = daily.map((d) => [x(d.t), d.visMean == null ? null : yVis(d.visMean)]);
  const lyPts = daily.map((d) => [x(d.t), d.lyMean == null ? null : yVis(d.lyMean)]);

  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left;
    const t = x.invert(px);
    const i = Math.round((t - t0) / DAY);
    if (i < 0 || i >= daily.length) return setHover(null);
    setHover(i);
  };

  // 핀이 18px보다 가까우면 다른 줄로. 두 줄로도 모자라면 같은 줄에 겹치되 번호는 표 목록에 남는다
  const pinRow = [];
  const lastX = PIN_ROWS.map(() => -Infinity);
  for (const ev of events) {
    const px = x(ev.t);
    const row = lastX.findIndex((lx) => px - lx >= 18);
    const r = row === -1 ? 0 : row;
    pinRow.push(r);
    lastX[r] = px;
  }

  // 글자 라벨은 최고치가 가장 큰 구간 하나에만 단다. 나머지는 마름모만(값은 툴팁·사건 목록에)
  const mainEpisode = episodes.reduce((a, b) => (a && a.peak >= b.peak ? a : b), null);

  const h = hover == null ? null : daily[hover];
  const hEvents = h ? events.filter((ev) => ev.t === h.t) : [];

  return (
    <div className="trend-chart" ref={ref}>
      <div className="chart-legend" aria-hidden="true">
        <span><i className="swatch-line" style={{ background: COLOR.search }} />검색지수 전년 대비 배율 (7일 중앙값)</span>
        <span><i className="swatch-line swatch-dash" style={{ borderColor: COLOR.threshold }} />신호 임계 {thresholds.search}배</span>
        <span><i className="swatch-line" style={{ background: COLOR.visitors }} />외지인 방문자 (7일 평균)</span>
        <span><i className="swatch-line" style={{ background: COLOR.context }} />전년 같은 요일 (7일 평균)</span>
        {events.length > 0 && <span><i className="swatch-pin" />타임라인 사건</span>}
      </div>

      <div className="chart-stage">
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`${series.region.name} 검색 배율과 외지인 방문자 추이`}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {/* 위 패널: 검색 배율 */}
          <text x={M.left} y={topY0 - 8} className="chart-panel-label">검색 관심 · 전년 대비 배율</text>
          {niceTicks(0, searchMax, 4).map((v) => (
            <g key={`sy${v}`}>
              <line x1={M.left} x2={M.left + innerW} y1={ySearch(v)} y2={ySearch(v)} stroke={COLOR.grid} />
              <text x={M.left - 8} y={ySearch(v) + 4} className="chart-tick" textAnchor="end">{v}배</text>
            </g>
          ))}
          {episodes.map((ep) => (
            <rect
              key={`ep${ep.start}`}
              x={x(ep.startT)}
              y={topY0}
              width={Math.max(2, x(ep.endT) - x(ep.startT))}
              height={TOP_H}
              fill={COLOR.thresholdTint}
            />
          ))}
          <path d={aboveArea} fill={COLOR.threshold} opacity="0.18" />
          <line
            x1={M.left}
            x2={M.left + innerW}
            y1={ySearch(thresholds.search)}
            y2={ySearch(thresholds.search)}
            stroke={COLOR.threshold}
            strokeDasharray="5 4"
            strokeWidth="1.25"
          />
          <text x={M.left + innerW} y={ySearch(thresholds.search) - 5} className="chart-note" textAnchor="end" fill={COLOR.threshold}>
            임계 {thresholds.search}배
          </text>
          <path d={pathOf(searchPts)} fill="none" stroke={COLOR.search} strokeWidth="2" strokeLinejoin="round" />
          {episodes.map((ep) => (
            <EpisodeMarker
              key={`cf${ep.start}`}
              ep={ep}
              x={x}
              y={ySearch}
              top={topY0}
              innerRight={M.left + innerW}
              labelled={ep === mainEpisode}
            />
          ))}

          {/* 아래 패널: 외지인 방문자 */}
          <text x={M.left} y={botY0 - 8} className="chart-panel-label">외지인 방문자 · 명</text>
          {niceTicks(0, visMax, 4).map((v) => (
            <g key={`vy${v}`}>
              <line x1={M.left} x2={M.left + innerW} y1={yVis(v)} y2={yVis(v)} stroke={COLOR.grid} />
              <text x={M.left - 8} y={yVis(v) + 4} className="chart-tick" textAnchor="end">{compact(v)}</text>
            </g>
          ))}
          <path d={pathOf(lyPts)} fill="none" stroke={COLOR.context} strokeWidth="2" strokeLinejoin="round" />
          <path d={pathOf(rawPts)} fill="none" stroke={COLOR.visitors} strokeWidth="1" opacity="0.28" />
          <path d={pathOf(meanPts)} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeLinejoin="round" />
          <line x1={x(visitorsEnd)} x2={x(visitorsEnd)} y1={botY0} y2={botY0 + BOTTOM_H} stroke={COLOR.axis} />
          <text x={x(visitorsEnd) - 4} y={botY0 + 12} className="chart-note" textAnchor="end">방문자 자료 {fmtMD(model.visitorsEndIso)}까지</text>

          {/* 사건 세로선 + 번호 핀 */}
          {events.map((ev, i) => (
            <g key={`evl${ev.n}`}>
              <line x1={x(ev.t)} x2={x(ev.t)} y1={PIN_ROWS[pinRow[i]] + 8} y2={botY0 + BOTTOM_H} stroke={COLOR.ink} strokeOpacity="0.22" />
              <circle cx={x(ev.t)} cy={PIN_ROWS[pinRow[i]]} r="8" fill={ev.is_signal ? COLOR.ink : "#fff"} stroke={COLOR.ink} strokeWidth="1.25" />
              <text x={x(ev.t)} y={PIN_ROWS[pinRow[i]] + 3.5} textAnchor="middle" className="chart-pin-num" fill={ev.is_signal ? "#fff" : COLOR.ink}>{ev.n}</text>
            </g>
          ))}

          {/* x축 */}
          <line x1={M.left} x2={M.left + innerW} y1={botY0 + BOTTOM_H} y2={botY0 + BOTTOM_H} stroke={COLOR.axis} />
          {monthTicks(t0, t1, innerW).map((t) => (
            <text key={`mx${t}`} x={x(t)} y={botY0 + BOTTOM_H + 18} className="chart-tick" textAnchor="middle">{monthLabel(t)}</text>
          ))}

          {/* 호버 */}
          {h && (
            <g pointerEvents="none">
              <line x1={x(h.t)} x2={x(h.t)} y1={topY0} y2={botY0 + BOTTOM_H} stroke={COLOR.ink} strokeOpacity="0.45" />
              {h.search != null && <Dot cx={x(h.t)} cy={ySearch(h.search)} color={COLOR.search} />}
              {h.visMean != null && <Dot cx={x(h.t)} cy={yVis(h.visMean)} color={COLOR.visitors} />}
              {h.lyMean != null && <Dot cx={x(h.t)} cy={yVis(h.lyMean)} color={COLOR.context} />}
            </g>
          )}
          <rect x={M.left} y={0} width={innerW} height={height - AXIS_H} fill="transparent" />
        </svg>

        {h && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(x(h.t) + 12, width - 236), top: topY0 + 8 }}
          >
            <p className="chart-tooltip__date">{h.iso} ({weekdayOf(h.iso)})</p>
            <Row color={COLOR.search} label="검색 배율(7일 중앙값)" value={fmtRatio(h.search)} warn={h.search != null && h.search >= thresholds.search} />
            <Row color={COLOR.visitors} label="외지인 방문자" value={h.visitorsRaw == null ? "자료 없음" : `${fmtInt(h.visitorsRaw)}명`} />
            <Row color={COLOR.visitors} label="  7일 평균" value={h.visMean == null ? "–" : `${fmtInt(h.visMean)}명`} />
            <Row color={COLOR.context} label="전년 같은 요일 7일 평균" value={h.lyMean == null ? "–" : `${fmtInt(h.lyMean)}명`} />
            {hEvents.map((ev) => (
              <p key={ev.n} className="chart-tooltip__event">
                <b>{ev.n}</b> {ev.type} — {ev.description}
              </p>
            ))}
          </div>
        )}
      </div>

      {events.length > 0 && (
        <ol className="event-legend">
          {events.map((ev) => (
            <li key={`el${ev.n}`} className={ev.is_signal ? "is-signal" : ""}>
              <span className="event-legend__num">{ev.n}</span>
              <span className="event-legend__date">{fmtMD(ev.date)}</span>
              <span className="event-legend__type">{ev.type}</span>
              <span className="event-legend__desc">{ev.description}</span>
            </li>
          ))}
        </ol>
      )}

      <p className="chart-footnote">
        검색 {fmtMD(model.searchEndIso)}·방문자 {fmtMD(model.visitorsEndIso)}까지 반영. 배율은 그날 값 ÷ 364일 전 같은 요일 값의 최근
        7일 중앙값이고, 붉은 띠는 임계를 {thresholds.min_duration}일 이상 연속 넘은 구간입니다(D-12, 에이전트① 타임라인과 같은 규칙).
      </p>

      <TableView daily={daily} thresholds={thresholds} />
    </div>
  );
}

function buildModel(series, timeline) {
  const raw = series.daily;
  const visitorsRaw = raw.map((d) => d.visitors);
  const visMean = trailingMean(visitorsRaw);
  const lyMean = trailingMean(raw.map((d) => d.visitors_ly));
  const daily = raw.map((d, i) => ({
    iso: d.date,
    t: toTime(d.date),
    search: d.search_stat,
    visitorsRaw: d.visitors,
    visMean: visMean[i],
    lyMean: lyMean[i],
  }));
  const t0 = daily[0].t;
  const t1 = daily[daily.length - 1].t;

  const events = (timeline?.events ?? [])
    .filter((e) => {
      const t = toTime(e.date);
      return t >= t0 && t <= t1;
    })
    .sort((a, b) => a.date.localeCompare(b.date) || EVENT_ORDER.indexOf(a.type) - EVENT_ORDER.indexOf(b.type))
    .map((e, i) => ({ ...e, n: i + 1, t: toTime(e.date) }));

  const episodes = series.episodes
    .filter((e) => e.metric === "search")
    .map((e) => ({ ...e, startT: toTime(e.start), endT: toTime(e.end), confirmT: toTime(e.confirm), peakT: toTime(e.peak_date) }));

  return {
    daily,
    t0,
    t1,
    events,
    episodes,
    thresholds: series.thresholds,
    searchEnd: toTime(series.as_of.search),
    visitorsEnd: toTime(series.as_of.visitors),
    searchEndIso: series.as_of.search,
    visitorsEndIso: series.as_of.visitors,
  };
}

// 임계를 넘은 부분만 칠한다(임계선과 곡선 사이)
function areaAbove(daily, x, y, threshold) {
  let d = "";
  let run = [];
  const flush = () => {
    if (run.length > 1) {
      d += `M${x(run[0].t)},${y(threshold)}`;
      for (const p of run) d += `L${x(p.t)},${y(p.search)}`;
      d += `L${x(run[run.length - 1].t)},${y(threshold)}Z`;
    }
    run = [];
  };
  for (const p of daily) {
    if (p.search != null && p.search >= threshold) run.push(p);
    else flush();
  }
  flush();
  return d;
}

function EpisodeMarker({ ep, x, y, top, innerRight, labelled }) {
  const cx = x(ep.confirmT);
  const px = x(ep.peakT);
  const label = `신호 확정 ${fmtMD(ep.confirm)}`;
  const peakLabel = `최고 ${fix(ep.peak, 2)}배 (${fmtMD(ep.peak_date)})`;
  const anchorEnd = px > innerRight - 150;
  const confirmEnd = cx > innerRight - 90;
  return (
    <g>
      <path d={`M${cx},${top + 6} l5,6 l-5,6 l-5,-6 Z`} fill={COLOR.threshold} stroke="#fff" strokeWidth="1.5">
        <title>{`${label} · ${ep.start}~${ep.end} 임계 초과 · ${peakLabel}`}</title>
      </path>
      <circle cx={px} cy={y(ep.peak)} r="4" fill={COLOR.search} stroke="#fff" strokeWidth="2" />
      {!labelled ? null : (
        <text x={confirmEnd ? cx - 8 : cx + 8} y={top + 16} className="chart-note chart-note--strong" fill={COLOR.threshold} textAnchor={confirmEnd ? "end" : "start"}>
          {label}
        </text>
      )}
      {labelled && <text
        x={anchorEnd ? px - 8 : px + 8}
        y={Math.max(top + 30, y(ep.peak) + 4)}
        className="chart-note"
        textAnchor={anchorEnd ? "end" : "start"}
      >
        {peakLabel}
      </text>}
    </g>
  );
}

function Dot({ cx, cy, color }) {
  return <circle cx={cx} cy={cy} r="4.5" fill={color} stroke="#fff" strokeWidth="2" />;
}

function Row({ color, label, value, warn }) {
  return (
    <p className="chart-tooltip__row">
      <i style={{ background: color }} />
      <span>{label}</span>
      <b className={warn ? "is-warn" : ""}>{value}</b>
    </p>
  );
}

function compact(v) {
  if (v >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return v.toLocaleString("ko-KR");
}

// 표 보기: 월별 요약 (툴팁 없이도 모든 값을 읽을 수 있게)
function TableView({ daily, thresholds }) {
  const months = new Map();
  for (const d of daily) {
    const key = d.iso.slice(0, 7);
    const m = months.get(key) ?? { key, searchMax: null, above: 0, vis: 0, visN: 0, ly: 0, lyN: 0 };
    if (d.search != null) {
      m.searchMax = Math.max(m.searchMax ?? 0, d.search);
      if (d.search >= thresholds.search) m.above += 1;
    }
    if (d.visitorsRaw != null) {
      m.vis += d.visitorsRaw;
      m.visN += 1;
    }
    months.set(key, m);
  }
  return (
    <details className="chart-table">
      <summary>표로 보기 (월별 요약)</summary>
      <table>
        <thead>
          <tr>
            <th>월</th>
            <th>검색 배율 최고</th>
            <th>임계 초과 일수</th>
            <th>외지인 방문자 합계</th>
            <th>자료 일수</th>
          </tr>
        </thead>
        <tbody>
          {[...months.values()].map((m) => (
            <tr key={m.key}>
              <td>{m.key}</td>
              <td>{fmtRatio(m.searchMax)}</td>
              <td>{m.above}일</td>
              <td>{m.visN ? `${fmtInt(m.vis)}명` : "–"}</td>
              <td>{m.visN}일</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
