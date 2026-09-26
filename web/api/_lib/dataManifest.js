// Server-side mirror of web/src/data/manifest.js. Vercel Node functions
// don't go through Vite, so `import.meta.env.VITE_USE_PROD` (a Vite
// build-time replacement) isn't available here -- read the same flag via
// `process.env` instead. Keep this table in sync with manifest.js by hand;
// it's intentionally small (9 rows) so that's a low-risk duplication.
const USE_PROD = process.env.VITE_USE_PROD === "true";

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
    // briefing: forecast_51750(mock조차 없음)가 없어 아직 생성 불가 -- unsupported로 둔다.
  },
  geoje: {
    signal_status: { url: "/prod/signal_status.json", kind: "real" },
    forecast: { url: "/mock/forecast.json", kind: "mock" },
    visitor_profile: { url: "/prod/visitor_profile.json", kind: "real" },
    hotspots: { url: "/prod/hotspots.json", kind: "real" },
    content_type: USE_PROD
      ? { url: "/prod/content_type.json", kind: "real" }
      : { url: "/mock/content_type.json", kind: "mock" },
    checklist: { url: "/prod/checklist.json", kind: "real" },
    precedent: { url: "/mock/precedent.json", kind: "mock" },
    before_after: { url: "/mock/before_after.json", kind: "mock" },
    timeline: { url: "/prod/timeline.json", kind: "real" },
    briefing: { url: "/prod/briefing.json", kind: "mock" },
  },
  chungju: {
    signal_status: { url: "/mock/chungju_signal_status.json", kind: "mock" },
    content_type: { url: "/mock/chungju_content_type.json", kind: "mock" },
  },
};

export function getManifestEntry(region, dataType) {
  return REGION_MANIFEST[region]?.[dataType] ?? null;
}
