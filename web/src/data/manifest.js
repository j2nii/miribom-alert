// Single source of truth for "which region has which data file, and is it
// mock or real". Swapping mock -> real later means editing one row here --
// no component code changes. See docs/설계결정.md and docs/진행상황.md.
//
// `kind`:
//   "mock"        - data/mock/*.json, _mock:true envelope
//   "real"        - data/prod/*.json, _mock:false envelope
//   "unsupported" - no file for this region/dataType yet; UI shows the
//                   existing "데이터 준비 전" empty state.
// VITE_USE_PROD gates data types that have BOTH a mock and a real file today.
// Only content_type does (agent②'s live output lives at data/prod/). Every
// other data type has no prod file yet, so the toggle has no effect on them
// until a real file exists -- adding one is a manifest edit, not a toggle.
const USE_PROD = import.meta.env.VITE_USE_PROD === "true";

export const REGION_MANIFEST = {
  geoje: {
    signal_status: { url: "/mock/signal_status.json", kind: "mock" },
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
    // Intentionally schema-independent (baseline lifecycle reference case,
    // not one of the 9 official contracts) -- but same envelope shape, so
    // it's just as swappable to real data later. See docs/설계결정.md and
    // the "충주 데이터 재구성" section of the plan.
    signal_status: { url: "/mock/chungju_signal_status.json", kind: "mock" },
    content_type: { url: "/mock/chungju_content_type.json", kind: "mock" },
    // forecast/visitor_profile/hotspots/checklist/precedent/before_after/
    // timeline: no file yet -> loadData() resolves these as "unsupported".
  },
};

export const REGIONS = [
  { key: "geoje", label: "거제시" },
  { key: "chungju", label: "충주시" },
];

export function getManifestEntry(region, dataType) {
  return REGION_MANIFEST[region]?.[dataType] ?? null;
}
