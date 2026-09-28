// Server-side mirror of web/src/data/manifest.js. Vercel Node functions
// don't go through Vite, so `import.meta.env.VITE_USE_PROD` (a Vite
// build-time replacement) isn't available here -- read the same flag via
// `process.env` instead. Keep this table in sync with manifest.js by hand;
// it's intentionally small so that's a low-risk duplication.
const USE_PROD = process.env.VITE_USE_PROD === "true";

// 에이전트 산출물(signal_status·timeline·hotspots·visitor_profile·content_type)과 예측·신호 추이가
// 모두 있는 추가 지역. 파일 이름 규칙이 같아 지역코드만 다르다. 체크리스트·브리핑·선례·조치 전후는
// 이 지역들에 아직 없다 -> "unsupported"(데이터 준비 전)로 뜬다.
function agentRegion(code) {
  const real = (name) => ({ url: `/prod/${name}_${code}.json`, kind: "real" });
  return {
    signal_status: real("signal_status"),
    timeline: real("timeline"),
    hotspots: real("hotspots"),
    visitor_profile: real("visitor_profile"),
    content_type: real("content_type"),
    // analysis/src/forecast/export_forecast.py · export_signal_series.py (228개 시군구 공통 모델)
    forecast: real("forecast"),
    signal_series: real("signal_series"),
  };
}

export const REGION_MANIFEST = {
  yeongwol: {
    // agents/judge_signal_status.py, agents/agent1_timeline.py 실측 산출물.
    signal_status: { url: "/prod/signal_status_51750.json", kind: "real" },
    timeline: { url: "/prod/timeline_51750.json", kind: "real" },
    // agent_hotspots.py, agent_visitor_profile.py, agent2_apply.py 실측 산출물.
    hotspots: { url: "/prod/hotspots_51750.json", kind: "real" },
    visitor_profile: { url: "/prod/visitor_profile_51750.json", kind: "real" },
    content_type: { url: "/prod/content_type_51750.json", kind: "real" },
    // agent3_match.py --region 51750 실행 결과 (2026-09-24).
    checklist: { url: "/prod/checklist_51750.json", kind: "real" },
    forecast: { url: "/prod/forecast_51750.json", kind: "real" },
    signal_series: { url: "/prod/signal_series_51750.json", kind: "real" },
    precedent: { url: "/prod/precedent_51750.json", kind: "real" },
  },
  geoje: {
    signal_status: { url: "/prod/signal_status.json", kind: "real" },
    forecast: { url: "/prod/forecast.json", kind: "real" },
    signal_series: { url: "/prod/signal_series.json", kind: "real" },
    visitor_profile: { url: "/prod/visitor_profile.json", kind: "real" },
    hotspots: { url: "/prod/hotspots.json", kind: "real" },
    content_type: USE_PROD
      ? { url: "/prod/content_type.json", kind: "real" }
      : { url: "/mock/content_type.json", kind: "mock" },
    checklist: { url: "/prod/checklist.json", kind: "real" },
    precedent: { url: "/prod/precedent.json", kind: "real" },
    before_after: { url: "/mock/before_after.json", kind: "mock" },
    timeline: { url: "/prod/timeline.json", kind: "real" },
    briefing: { url: "/prod/briefing.json", kind: "real" },
  },
  yeosu: agentRegion("12130"),
  ulleung: agentRegion("47940"),
  sokcho: agentRegion("51210"),
  inje: agentRegion("51810"),
  chungju: {
    signal_status: { url: "/mock/chungju_signal_status.json", kind: "mock" },
    content_type: { url: "/mock/chungju_content_type.json", kind: "mock" },
  },
};

// 전국 시군구: 사례 지역이 아닌 곳은 지역 키가 5자리 지역코드("51150")다. 데이터랩·이동통신·검색지수만으로
// 만드는 3종(경보 판정·신호 추이·7일 예측)을 data/prod/regions/에서 읽는다. 목록은 regions/index.json
// (scripts/build_region_index.py)이 가지고 있고, 여기서는 파일 경로 규칙만 안다.
export const NATIONAL_TYPES = ["signal_status", "signal_series", "forecast"];
// 사례 지역의 지역코드 → 화면 키. ?region=51750처럼 코드로 들어와도 사례 화면으로 보낸다
export const SHOWCASE_CODES = {
  51750: "yeongwol",
  48310: "geoje",
  12130: "yeosu",
  51210: "sokcho",
  51810: "inje",
  47940: "ulleung",
};

export function isRegionCode(region) {
  return /^\d{5}$/.test(region ?? "");
}

export function getManifestEntry(region, dataType) {
  if (REGION_MANIFEST[region]) return REGION_MANIFEST[region][dataType] ?? null;
  if (isRegionCode(region) && NATIONAL_TYPES.includes(dataType)) {
    return { url: `/prod/regions/${dataType}_${region}.json`, kind: "real" };
  }
  return null;
}
