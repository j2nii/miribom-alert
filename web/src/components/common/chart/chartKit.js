import { useEffect, useRef, useState } from "react";

// 차트 공용 도구. 라이브러리 없이 SVG를 그리므로 축·눈금·색을 한곳에 모아 둔다.
// 색은 dataviz 검증기(scripts/validate_palette.js)로 6개 항목을 모두 통과한 조합이다
// (#00897a, #5162c4, #c7762a, 흰 배경). crimson은 임계·초과 같은 '상태'에만 쓴다.
export const COLOR = {
  visitors: "#00897a",
  search: "#5162c4",
  accent: "#c7762a",
  context: "#9aa7b3",
  total: "#10202f",
  threshold: "var(--crimson)",
  thresholdTint: "rgba(209, 75, 61, 0.10)",
  grid: "rgba(16, 32, 47, 0.08)",
  axis: "rgba(16, 32, 47, 0.28)",
  ink: "var(--ink)",
  inkSoft: "var(--ink-soft)",
};

// SVG를 viewBox로 늘리면 글자까지 같이 커지고 줄어든다. 실제 픽셀 폭을 재서 그 폭으로 그린다.
export function useElementWidth(fallback = 640) {
  const ref = useRef(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(Math.round(w));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

export const DAY = 86400000;
export const toTime = (iso) => Date.parse(`${iso}T00:00:00Z`);
export const fromTime = (t) => new Date(t).toISOString().slice(0, 10);

export function linear([d0, d1], [r0, r1]) {
  const span = d1 - d0 || 1;
  const f = (v) => r0 + ((v - d0) / span) * (r1 - r0);
  f.invert = (p) => d0 + ((p - r0) / (r1 - r0)) * span;
  return f;
}

export function log2Scale([d0, d1], [r0, r1]) {
  const l0 = Math.log2(d0);
  const l1 = Math.log2(d1);
  return (v) => r0 + ((Math.log2(v) - l0) / (l1 - l0 || 1)) * (r1 - r0);
}

// 1-2-5 계열로 보기 좋은 눈금
export function niceTicks(min, max, count = 4) {
  const span = max - min || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) ?? 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

export function niceMax(max, count = 4) {
  const ticks = niceTicks(0, max, count);
  const last = ticks[ticks.length - 1];
  return last >= max ? last : last + (ticks[1] - ticks[0]);
}

// 선 경로. null이 끼면 선을 끊는다(결측을 이어 그리지 않는다)
export function pathOf(points) {
  let d = "";
  let pen = false;
  for (const [x, y] of points) {
    if (y == null || Number.isNaN(y)) {
      pen = false;
      continue;
    }
    d += `${pen ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    pen = true;
  }
  return d;
}

// 뒤로 7일 이동평균. 그날을 포함한 과거만 쓴다(미래를 섞지 않는다)
export function trailingMean(values, window = 7) {
  return values.map((_, i) => {
    if (i < window - 1) return null;
    const slice = values.slice(i - window + 1, i + 1);
    if (slice.some((v) => v == null)) return null;
    return slice.reduce((a, b) => a + b, 0) / window;
  });
}

export const fmtInt = (v) => (v == null ? "–" : Math.round(v).toLocaleString("ko-KR"));
// 반올림은 사사오입. toFixed는 이진 부동소수 때문에 1.275를 1.27로 내려 문서(확정수치·사례 문서의 1.28)와 어긋난다
export const fix = (v, digits = 2) => (Math.round(v * 10 ** digits + 1e-9) / 10 ** digits).toFixed(digits);
export const fmtRatio = (v, digits = 2) => (v == null ? "–" : `${fix(v, digits)}배`);
export function fmtMD(iso) {
  const [, m, d] = iso.split("-");
  return `${+m}/${+d}`;
}
export function fmtYM(ym) {
  const [y, m] = ym.split("-");
  return +m === 1 ? `${y}.1` : `${+m}월`;
}
const WEEK = "일월화수목금토";
export const weekdayOf = (iso) => WEEK[new Date(`${iso}T00:00:00Z`).getUTCDay()];

// 달 첫날 눈금. 폭이 좁으면 격월로 거른다
export function monthTicks(startT, endT, width) {
  const ticks = [];
  const d = new Date(startT);
  d.setUTCDate(1);
  if (d.getTime() < startT) d.setUTCMonth(d.getUTCMonth() + 1);
  while (d.getTime() <= endT) {
    ticks.push(d.getTime());
    d.setUTCMonth(d.getUTCMonth() + 1);
  }
  const every = width < 520 ? 3 : width < 760 ? 2 : 1;
  return ticks.filter((_, i) => i % every === 0);
}

export function monthLabel(t) {
  const d = new Date(t);
  const m = d.getUTCMonth() + 1;
  return m === 1 ? `${d.getUTCFullYear()}.1` : `${m}월`;
}
