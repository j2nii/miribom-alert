// Server-side mirror of web/src/data/manifest.js. Vercel Node functions
// don't go through Vite, so `import.meta.env.VITE_USE_PROD` (a Vite
// build-time replacement) isn't available here -- read the same flag via
// `process.env` instead. Keep this table in sync with manifest.js by hand;
// it's intentionally small (9 rows) so that's a low-risk duplication.
const USE_PROD = process.env.VITE_USE_PROD === "true";

export const REGION_MANIFEST = {
  yeongwol: {
    signal_status: { url: "/prod/yeongwol_signal_status.json", kind: "real" },
  },
  geoje: {
    signal_status: { url: "/prod/geoje_signal_status.json", kind: "real" },
    forecast: { url: "/mock/forecast.json", kind: "mock" },
    visitor_profile: { url: "/mock/visitor_profile.json", kind: "mock" },
    hotspots: { url: "/mock/hotspots.json", kind: "mock" },
    content_type: USE_PROD
      ? { url: "/prod/content_type.json", kind: "real" }
      : { url: "/mock/content_type.json", kind: "mock" },
    checklist: { url: "/mock/checklist.json", kind: "mock" },
    precedent: { url: "/mock/precedent.json", kind: "mock" },
    before_after: { url: "/mock/before_after.json", kind: "mock" },
    timeline: { url: "/mock/timeline.json", kind: "mock" },
  },
  chungju: {
    signal_status: { url: "/mock/chungju_signal_status.json", kind: "mock" },
    content_type: { url: "/mock/chungju_content_type.json", kind: "mock" },
  },
};

export function getManifestEntry(region, dataType) {
  return REGION_MANIFEST[region]?.[dataType] ?? null;
}
