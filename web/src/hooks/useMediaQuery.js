import { useEffect, useState } from "react";

// index.css의 좁은 화면 분기점과 동일한 값 -- 두 곳이 갈라지면 "모바일에서는 높이를 강제하지
// 않는다" 같은 JS 분기가 CSS와 엇나가므로 한 곳에서만 정의한다.
export const NARROW_QUERY = "(max-width: 860px)";

/**
 * matchMedia 구독 훅. useRegionData와 같은 컨벤션(상태 + useEffect 정리)을 따른다.
 */
export function useMediaQuery(query) {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && !!window.matchMedia?.(query).matches
  );

  useEffect(() => {
    if (!window.matchMedia) return;
    const mql = window.matchMedia(query);
    const onChange = (e) => setMatches(e.matches);
    setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
