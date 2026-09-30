import { useMemo, useState } from "react";
import { COLOR, fix, fmtInt, linear, niceMax, niceTicks, useElementWidth } from "../common/chart/chartKit.js";

// 앞으로 6개월 월별 외지인 방문자 전망 (analysis/src/forecast/monthly_outlook.py).
// 행사 기획·예산 편성 참고용. 예측값만 던지지 않고, 아래 '근거' 패널에서
//   ① 달마다 어떻게 계산됐나(작년 같은 달 × 보정)  ② 왜 이 방법인가(방법 7가지의 두 해 검증 오차)
// 를 사용자가 직접 확인할 수 있게 한다.
const M = { top: 26, right: 14, bottom: 30, left: 52 };
const PLOT_H = 220;

const ym = (s) => {
  const [y, m] = s.split("-");
  return { y: +y, m: +m };
};
const monthShort = (s) => {
  const { y, m } = ym(s);
  return m === 1 ? `${y}.1` : `${m}월`;
};
const monthLong = (s) => {
  const { y, m } = ym(s);
  return `${y}년 ${m}월`;
};
const pct = (r) => `${r >= 1 ? "+" : "−"}${fix(Math.abs(r - 1) * 100, 1)}%`;

export default function OutlookChart({ outlook }) {
  const [ref, width] = useElementWidth(520);
  const [hover, setHover] = useState(null);
  const model = useMemo(() => buildModel(outlook), [outlook]);
  const { rows, future, partial, totals, peak } = model;

  const innerW = Math.max(200, width - M.left - M.right);
  const step = innerW / Math.max(1, rows.length - 1);
  const x = (i) => M.left + i * step;
  const yMax = niceMax(Math.max(...rows.flatMap((r) => [r.actual ?? 0, r.upper ?? 0, r.ly ?? 0])));
  const y = linear([0, yMax], [M.top + PLOT_H, M.top]);
  const height = M.top + PLOT_H + M.bottom;
  const firstFuture = rows.findIndex((r) => r.predicted != null);

  const line = (key) => {
    let d = "";
    let pen = false;
    rows.forEach((r, i) => {
      if (r[key] == null) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const futureIdx = rows.map((r, i) => (r.predicted != null ? i : null)).filter((i) => i != null);
  const band =
    futureIdx.map((i, k) => `${k ? "L" : "M"}${x(i)},${y(rows[i].upper)}`).join("") +
    [...futureIdx].reverse().map((i) => `L${x(i)},${y(rows[i].lower)}`).join("") +
    "Z";
  const lastActual = [...rows].reverse().findIndex((r) => r.actual != null);
  const lastActualIdx = lastActual < 0 ? -1 : rows.length - 1 - lastActual;
  const bridge =
    lastActualIdx >= 0 && firstFuture > 0
      ? `M${x(lastActualIdx)},${y(rows[lastActualIdx].actual)}L${x(firstFuture)},${y(rows[firstFuture].predicted)}`
      : "";

  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round((e.clientX - box.left - M.left) / step);
    setHover(i >= 0 && i < rows.length ? i : null);
  };
  const h = hover == null ? null : rows[hover];
  const d = outlook;

  return (
    <div className="trend-chart" ref={ref}>
      <div className="stat-row">
        <div className="stat-tile">
          <p className="stat-tile__label">앞으로 6개월 합계 예상</p>
          <p className="stat-tile__value">{fmtInt(totals.predicted)}<small>명</small></p>
          <p className="stat-tile__sub">작년 같은 기간({fmtInt(totals.ly)}명) 대비 {pct(totals.predicted / totals.ly)}</p>
        </div>
        <div className="stat-tile">
          <p className="stat-tile__label">가장 많은 달</p>
          <p className="stat-tile__value">{monthShort(peak.month)} <small>{fmtInt(peak.predicted)}명</small></p>
          <p className="stat-tile__sub">작년 같은 달 대비 {pct(peak.yoy)}{peak.major_holiday_days > 0 ? " · 명절 연휴 포함" : ""}</p>
        </div>
      </div>

      <div className="chart-legend" aria-hidden="true">
        <span><i className="swatch-line" style={{ background: COLOR.visitors }} />월별 실측</span>
        <span><i className="swatch-line" style={{ background: COLOR.context }} />작년 같은 달</span>
        <span><i className="swatch-line swatch-dash" style={{ borderColor: COLOR.visitors }} />전망</span>
        <span><i className="swatch-band" />80% 구간</span>
      </div>

      <div className="chart-stage">
        <svg width={width} height={height} role="img" aria-label="월별 외지인 방문자 실측과 6개월 전망" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {niceTicks(0, yMax, 4).map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + innerW} y1={y(v)} y2={y(v)} stroke={COLOR.grid} />
              <text x={M.left - 8} y={y(v) + 4} className="chart-tick" textAnchor="end">{compact(v)}</text>
            </g>
          ))}
          {firstFuture > 0 && (
            <>
              <rect x={x(firstFuture) - step / 2} y={M.top} width={M.left + innerW - x(firstFuture) + step / 2} height={PLOT_H} fill="rgba(0, 137, 122, 0.05)" />
              <text x={x(firstFuture) - step / 2 + 6} y={M.top - 8} className="chart-note chart-note--strong" fill={COLOR.visitors}>
                전망 ({monthLong(future[0].month)}~)
              </text>
            </>
          )}
          <path d={band} fill={COLOR.visitors} opacity="0.14" />
          <path d={line("ly")} fill="none" stroke={COLOR.context} strokeWidth="1.5" />
          <path d={line("actual")} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeLinejoin="round" />
          <path d={bridge} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeDasharray="6 4" />
          <path d={line("predicted")} fill="none" stroke={COLOR.visitors} strokeWidth="2" strokeDasharray="6 4" />
          {rows.map((r, i) =>
            r.actual != null ? (
              <circle key={`a${i}`} cx={x(i)} cy={y(r.actual)} r="3" fill={COLOR.visitors} stroke="#fff" strokeWidth="1.5" />
            ) : r.predicted != null ? (
              <circle key={`p${i}`} cx={x(i)} cy={y(r.predicted)} r={r.month === peak.month ? 5 : 3.5} fill={r.month === peak.month ? COLOR.visitors : "#fff"} stroke={COLOR.visitors} strokeWidth="2" />
            ) : null
          )}
          {partial && firstFuture >= 0 && (
            <text x={x(firstFuture)} y={y(rows[firstFuture].predicted) + 18} className="chart-note" textAnchor="middle">
              ({ym(partial.month).m}/{partial.days}까지 실측 {compact(partial.visitors)})
            </text>
          )}

          <line x1={M.left} x2={M.left + innerW} y1={M.top + PLOT_H} y2={M.top + PLOT_H} stroke={COLOR.axis} />
          {rows.map((r, i) =>
            i % (rows.length > 16 ? 3 : 2) === (rows.length - 1) % (rows.length > 16 ? 3 : 2) ? (
              <text key={`m${i}`} x={x(i)} y={M.top + PLOT_H + 18} className="chart-tick" textAnchor="middle">{monthShort(r.month)}</text>
            ) : null
          )}
          {h && <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + PLOT_H} stroke={COLOR.ink} strokeOpacity="0.4" pointerEvents="none" />}
          <rect x={M.left - step / 2} y={M.top} width={innerW + step} height={PLOT_H} fill="transparent" />
        </svg>

        {h && (
          <div className="chart-tooltip" style={{ left: Math.min(x(hover) + 12, width - 240), top: M.top + 8 }}>
            <p className="chart-tooltip__date">{monthLong(h.month)}</p>
            {h.actual != null && <Row color={COLOR.visitors} label="실측" value={`${fmtInt(h.actual)}명`} />}
            {h.predicted != null && (
              <>
                <Row color={COLOR.visitors} label="전망" value={`${fmtInt(h.predicted)}명`} />
                <Row color="rgba(0,137,122,.3)" label="80% 구간" value={`${fmtInt(h.lower)}~${fmtInt(h.upper)}`} />
              </>
            )}
            {h.ly != null && <Row color={COLOR.context} label="작년 같은 달" value={`${fmtInt(h.ly)}명`} />}
            {h.reason && <p className="chart-tooltip__event">{h.reason}</p>}
          </div>
        )}
      </div>

      <Evidence d={d} future={future} />

      <details className="chart-table">
        <summary>표로 보기 (월별 실측·전망)</summary>
        <table>
          <thead>
            <tr>
              <th>월</th>
              <th>실측</th>
              <th>작년 같은 달</th>
              <th>전망</th>
              <th>80% 구간</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.month}>
                <td>{r.month}</td>
                <td>{r.actual == null ? (r.partialVisitors ? `${fmtInt(r.partialVisitors)} (부분)` : "–") : fmtInt(r.actual)}</td>
                <td>{r.ly == null ? "–" : fmtInt(r.ly)}</td>
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

// ── 근거 패널 ────────────────────────────────────────────────────────────────
function Evidence({ d, future }) {
  const chosen = d.methods.find((m) => m.chosen);
  const testBest = [...d.methods].sort((a, b) => a.test_smape - b.test_smape)[0];
  const validBest = [...d.methods].sort((a, b) => a.valid_smape - b.valid_smape)[0];
  const usesTrend = future.some((f) => f.trend_factor !== 1);

  return (
    <details className="evidence">
      <summary>
        <span className="evidence__badge">근거 보기</span>
        이 전망은 어떻게 나왔나 — 계산 방법 · 방법 선택 이유 · 검증 오차
      </summary>

      <div className="evidence__body">
        <section>
          <h4>① 계산 방법 — {d.method.label}</h4>
          <p className="evidence__formula">
            전망 = <b>작년 같은 달 방문자</b>
            {usesTrend && (
              <>
                {" "}× <b>최근 추세</b>
              </>
            )}{" "}
            × <b>휴일·명절 보정</b>
          </p>
          <p className="evidence__note">
            휴일·명절 보정은 그 달과 작년 같은 달의 쉬는 날 수, 평일 공휴일 수, 설·추석 연휴가 어느 달에 들었는지의 차이로 계산합니다. 보정 크기는
            전국 226개 시군구의 과거 자료에서 추정했습니다. 명절이 다른 달로 옮겨가면(예: 추석 2025년 10월 → 2026년 9월) 그만큼 방문자가 옮겨 갑니다.
          </p>
          <table className="evidence__table">
            <thead>
              <tr>
                <th>월</th>
                <th>작년 같은 달</th>
                {usesTrend && <th>× 추세</th>}
                <th>× 보정</th>
                <th>= 전망</th>
                <th>보정 이유</th>
              </tr>
            </thead>
            <tbody>
              {future.map((f) => (
                <tr key={f.month}>
                  <td>{monthShort(f.month)}</td>
                  <td>{fmtInt(f.last_year)}</td>
                  {usesTrend && <td>{fix(f.trend_factor, 3)}</td>}
                  <td className={f.adjust_factor > 1.02 ? "is-up" : f.adjust_factor < 0.98 ? "is-down" : ""}>{fix(f.adjust_factor, 3)}</td>
                  <td><b>{fmtInt(f.predicted)}</b></td>
                  <td className="evidence__reason">{reasonOf(f)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h4>② 왜 이 방법인가 — 방법 {d.methods.length}가지를 두 해로 검증</h4>
          <p className="evidence__note">
            각 방법으로 과거 시점에서 '그때 알던 자료만으로' 몇 달 뒤를 예측해 실제와 비교했습니다(2025년 = 검증, 2026년 1~7월 = 시험, 1~6달 앞).
            고르는 규칙: <b>{d.rule}</b>. 한 해만 잘 맞은 방법을 피하려는 규칙입니다.
          </p>
          <table className="evidence__table">
            <thead>
              <tr>
                <th>방법</th>
                <th>2025 검증 오차</th>
                <th>2026 시험 오차</th>
                <th>두 해 평균</th>
              </tr>
            </thead>
            <tbody>
              {[...d.methods]
                .sort((a, b) => (a.mean_smape ?? 99) - (b.mean_smape ?? 99))
                .map((m) => (
                  <tr key={m.key} className={m.chosen ? "is-chosen" : ""}>
                    <td>
                      {m.chosen && <span className="evidence__pick">선택</span>}
                      {m.label}
                    </td>
                    <td className={m.key === validBest.key ? "is-best" : ""}>{fix(m.valid_smape, 2)}%</td>
                    <td className={m.key === testBest.key ? "is-best" : ""}>{fix(m.test_smape, 2)}%</td>
                    <td><b>{m.mean_smape == null ? "–" : `${fix(m.mean_smape, 2)}%`}</b></td>
                  </tr>
                ))}
            </tbody>
          </table>
          <p className="evidence__note">
            오차는 sMAPE(평균적으로 몇 % 틀리나), 전국 226개 시군구 평균입니다. 굵은 칸은 그 해 1위입니다.
            {testBest.key !== chosen.key && (
              <>
                {" "}2026년만 보면 '{testBest.label}'이 {fix(testBest.test_smape, 2)}%로 가장 나았지만 2025년에는 {fix(testBest.valid_smape, 2)}%로 흔들려
                두 해 모두 안정적인 방법을 골랐습니다.
              </>
            )}{" "}
            최근 증감 추세를 넣은 방법은 모두 2025년엔 좋고 2026년엔 기준선보다 나빴습니다 — 한 해의 흐름이 다음 해로 이어지지 않았습니다.
          </p>
        </section>

        <section>
          <h4>③ 얼마나 맞나</h4>
          <ul className="evidence__list">
            <li>
              이 방법의 2026년 시험 오차: 전국 <b>{fix(d.accuracy.national_smape, 2)}%</b>
              {d.accuracy.region_smape != null && (
                <>
                  , {d.region.name} <b>{fix(d.accuracy.region_smape, 1)}%</b>
                </>
              )}
            </li>
            <li>
              몇 달 앞별 오차:{" "}
              {Object.entries(d.accuracy.by_horizon)
                .map(([k, v]) => `${k}달 앞 ${fix(v, 1)}%`)
                .join(" · ")}
            </li>
            <li>80% 구간은 두 해 검증에서 실제값이 예측의 몇 배로 나왔는지(10·90분위)로 정했습니다.</li>
            <li>축제 신설·콘텐츠 유행 같은 새 사건은 반영되지 않습니다. 날짜별 혼잡과 관광지점 쏠림도 이 월 합계에는 보이지 않습니다.</li>
          </ul>
        </section>
      </div>
    </details>
  );
}

function reasonOf(f) {
  const parts = [];
  if (f.major_holiday_days > 0 && !(f.major_holiday_days_ly > 0)) parts.push(`명절 연휴 ${f.major_holiday_days}일이 이 달로 옴`);
  else if (!(f.major_holiday_days > 0) && f.major_holiday_days_ly > 0) parts.push(`작년 이 달에 있던 명절 연휴(${f.major_holiday_days_ly}일)가 없음`);
  else if (f.major_holiday_days > 0) parts.push(`명절 연휴 ${f.major_holiday_days}일(작년 ${f.major_holiday_days_ly}일)`);
  if (f.rest_days_diff) parts.push(`쉬는 날 ${f.rest_days_diff > 0 ? "+" : ""}${f.rest_days_diff}일`);
  if (f.weekday_holiday_diff) parts.push(`평일 공휴일 ${f.weekday_holiday_diff > 0 ? "+" : ""}${f.weekday_holiday_diff}일`);
  if (parts.length === 0) parts.push("달력 차이 없음 — 기본 보정만");
  return parts.join(" · ");
}

function buildModel(d) {
  const future = d.outlook;
  const futureMonths = new Set(future.map((f) => f.month));
  const hist = d.history.filter((h) => !futureMonths.has(h.month) || h.full);
  const partial = d.history.find((h) => !h.full && futureMonths.has(h.month)) ?? null;
  const rows = [
    ...hist.map((h) => ({ month: h.month, actual: h.full ? h.visitors : null, ly: h.ly })),
    ...future.map((f) => ({
      month: f.month,
      predicted: f.predicted,
      lower: f.lower,
      upper: f.upper,
      ly: f.last_year,
      reason: reasonOf(f),
      partialVisitors: partial?.month === f.month ? partial.visitors : null,
    })),
  ];
  const totals = future.reduce(
    (a, f) => ({ predicted: a.predicted + f.predicted, lower: a.lower + f.lower, upper: a.upper + f.upper, ly: a.ly + f.last_year }),
    { predicted: 0, lower: 0, upper: 0, ly: 0 }
  );
  const peak = [...future].sort((a, b) => b.predicted - a.predicted)[0];
  return { rows, future, partial, totals, peak };
}

function Row({ color, label, value }) {
  return (
    <p className="chart-tooltip__row">
      <i style={{ background: color }} />
      <span>{label}</span>
      <b>{value}</b>
    </p>
  );
}

function compact(v) {
  if (v >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return v.toLocaleString("ko-KR");
}
