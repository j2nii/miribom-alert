// Single source of truth for "which region has which data file, and is it
// mock or real". Swapping mock -> real later means editing one row here --
// no component code changes. See docs/설계결정.md and docs/진행상황.md.
//
// `kind`:
//   "mock"        - data/mock/*.json, _mock:true envelope
//   "real"        - data/prod/*.json, _mock:false envelope. yeongwol/geoje's
//                   signal_status files are generated once by
//                   web/scripts/generate-signal-status.mjs from the live
//                   MySQL DB, not fetched live -- see that script's header
//                   comment for why (vw_daily_anomaly_scored is too slow to
//                   query per-request, 180s+ even filtered to one region).
//   "unsupported" - no file for this region/dataType yet; UI shows the
//                   existing "데이터 준비 전" empty state.
// VITE_USE_PROD gates data types that have BOTH a mock and a real file today.
// Only content_type does (agent②'s live output lives at data/prod/). Every
// other data type has no prod file yet, so the toggle has no effect on them
// until a real file exists -- adding one is a manifest edit, not a toggle.
const USE_PROD = import.meta.env.VITE_USE_PROD === "true";

export const REGION_MANIFEST = {
  yeongwol: {
    // 메인 실데이터 사례 (docs/meeting-notes/UI/MySQL_실데이터_연동_계획.md).
    // 나머지 8개 계약은 거제 전용 목업(지명·사례가 "거제"로 하드코딩됨)을 그대로
    // 재사용하면 화면에 지역명이 어긋나므로, 이번 라운드 범위 밖으로 두고
    // chungju와 같은 방식으로 "unsupported" 처리한다(파일 자체를 안 둠).
    signal_status: { url: "/prod/yeongwol_signal_status.json", kind: "real" },
  },
  geoje: {
    // 대비 사례 (총량은 그대로인데 특정 지점에만 쏠리는 패턴) -- signal_status만
    // 우선 실데이터로 전환, content_type 등 나머지는 이번 라운드 범위 밖.
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
  { key: "yeongwol", label: "영월군" },
  { key: "geoje", label: "거제시" },
  { key: "chungju", label: "충주시" },
];

export function getManifestEntry(region, dataType) {
  return REGION_MANIFEST[region]?.[dataType] ?? null;
}
