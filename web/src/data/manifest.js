// Single source of truth for "which region has which data file, and is it
// mock or real". Swapping mock -> real later means editing one row here --
// no component code changes. See docs/설계결정.md and docs/진행상황.md.
//
// `kind`:
//   "mock"        - data/mock/*.json, _mock:true envelope
//   "real"        - data/prod/*.json, _mock:false envelope, produced by the
//                   agents/ pipeline (judge_signal_status.py, agent1_timeline.py,
//                   agent2_apply.py, ...) -- NOT queried live from MySQL. We
//                   tried a direct-DB approach first (see git history /
//                   docs/meeting-notes/UI/MySQL_실데이터_연동_계획.md) but
//                   reverted it once we found agents/ already produces the
//                   same contracts from the same DB, with the project's
//                   actual 관심/의도/실현 3-signal definition -- prefer that
//                   over a second parallel pipeline.
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
    // agents/judge_signal_status.py, agents/agent1_timeline.py가 이미 이 지역
    // (region_id 51750) 실측 산출물을 만들어뒀음 -- 그대로 사용.
    // 나머지 계약은 거제 전용 목업(지명·사례가 "거제"로 하드코딩됨)을 그대로
    // 재사용하면 화면에 지역명이 어긋나므로, "unsupported" 처리한다.
    signal_status: { url: "/prod/signal_status_51750.json", kind: "real" },
    timeline: { url: "/prod/timeline_51750.json", kind: "real" },
  },
  geoje: {
    // 대비 사례 (총량은 그대로인데 특정 지점에만 쏠리는 패턴).
    // signal_status/timeline/content_type 모두 agents/ 파이프라인의 실측
    // 산출물(기본 지역 = 거제이므로 파일명에 지역코드 접미사 없음)을 그대로 사용.
    signal_status: { url: "/prod/signal_status.json", kind: "real" },
    forecast: { url: "/mock/forecast.json", kind: "mock" },
    visitor_profile: { url: "/mock/visitor_profile.json", kind: "mock" },
    hotspots: { url: "/mock/hotspots.json", kind: "mock" },
    content_type: USE_PROD
      ? { url: "/prod/content_type.json", kind: "real" }
      : { url: "/mock/content_type.json", kind: "mock" },
    // agent3_match.py 실행 결과(_mock:true로 자체 표시 -- 아직 일부 입력이
    // mock이라 정직하게 그렇게 표시하는 것). 09-12 손으로 쓴 목업(3건)보다
    // 09-20 agent 실행 결과(14건)가 더 최신·풍부해 이쪽을 쓴다.
    checklist: { url: "/prod/checklist.json", kind: "mock" },
    precedent: { url: "/mock/precedent.json", kind: "mock" },
    before_after: { url: "/mock/before_after.json", kind: "mock" },
    timeline: { url: "/prod/timeline.json", kind: "real" },
    // agent5_briefing.py 실행 결과. 라이브 LLM 호출(web/api/briefing.js)은
    // 폐기했다 -- "AI가 매번 새로 쓰는" 방식은 D-04의 "매일 같은 문장 틀이어야
    // 어제와 비교된다"는 설계 근거와 어긋난다. 나중에 실시간성이 필요해지면
    // 이 정적 파일을 읽는 대신 agent5_briefing.py 자체를 최신 데이터로 재실행하는
    // 방식으로 가야 한다(에이전트 루프 밖에서 별도 LLM 호출을 만들지 않는다).
    briefing: { url: "/prod/briefing.json", kind: "mock" },
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
