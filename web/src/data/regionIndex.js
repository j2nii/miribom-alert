import { useEffect, useState } from "react";
import { REGIONS, SHOWCASE_CODES, isRegionCode } from "./manifest.js";

// 전국 시군구 사전(data/prod/regions/index.json, scripts/build_region_index.py). 검색창·지역 이름표가
// 같이 쓰므로 한 번만 받아 모듈에 둔다. 지역을 고른 뒤에야 그 지역의 예측·신호 파일을 받는다.
let cache = null;

export function loadRegionIndex() {
  if (!cache) {
    cache = fetch("/prod/regions/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(prepare)
      .catch((err) => {
        cache = null; // 다음 호출에서 다시 시도
        throw err;
      });
  }
  return cache;
}

export function useRegionIndex() {
  const [state, setState] = useState({ status: "loading", index: null });
  useEffect(() => {
    let alive = true;
    loadRegionIndex()
      .then((index) => alive && setState({ status: "ok", index }))
      .catch((err) => alive && setState({ status: "error", index: null, error: String(err) }));
    return () => {
      alive = false;
    };
  }, []);
  return state;
}

// 화면이 쓰는 지역 키: 사례 지역은 "yeongwol" 같은 키, 나머지는 지역코드
export const keyOf = (entry) => entry.key ?? entry.code;

function prepare(raw) {
  const nameCount = new Map();
  for (const e of raw.regions) nameCount.set(e.name, (nameCount.get(e.name) ?? 0) + 1);
  const regions = raw.regions.map((e) => ({
    ...e,
    // 같은 이름이 여러 시도에 있으면(중구 5곳, 고성군 2곳) 시도를 붙여야 구분된다
    label: nameCount.get(e.name) > 1 ? `${e.sido_short} ${e.name}` : e.name,
    fullLabel: `${e.sido_short} ${e.name}`,
  }));
  const byKey = new Map(regions.map((e) => [keyOf(e), e]));
  const sidos = [...new Map(regions.map((e) => [e.sido_short, e.sido])).entries()].map(([short, full]) => ({
    short,
    full,
    count: regions.filter((e) => e.sido_short === short && !e.disabled).length,
  }));
  return { ...raw, regions, byKey, sidos };
}

// 주소·링크로 들어온 값을 화면 키로 정리한다. 사례 지역 코드는 사례 키로 바꾼다
export function normalizeRegionKey(value) {
  if (!value) return null;
  if (REGIONS.some((r) => r.key === value)) return value;
  if (isRegionCode(value)) return SHOWCASE_CODES[value] ?? value;
  return null;
}

// 지역 이름표. 사전이 오기 전에도 사례 지역은 이름이 나오게 REGIONS로 먼저 찾는다
export function regionLabelOf(key, index) {
  const entry = index?.byKey.get(key);
  if (entry) return entry.label;
  return REGIONS.find((r) => r.key === key)?.label ?? key;
}

export function useRegionLabel(key) {
  const { index } = useRegionIndex();
  return regionLabelOf(key, index);
}
