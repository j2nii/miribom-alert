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
// VITE_USE_PROD gates data types that have BOTH a mock and a real file and
// where we still want an easy way to fall back to mock. geoje's content_type
// is real by default now (VITE_USE_PROD=true in .env/.env.example, since the
// 5-region LLM classification via agent2_apply.py is trusted) -- the toggle
// is kept only as an escape hatch back to mock if a problem shows up. Data
// types that only have one version (mock-only, or promoted straight to real
// once the agents/ pipeline produced them -- hotspots/visitor_profile/checklist)
// skip the toggle entirely; adding/removing a prod file is a manifest edit,
// not a runtime toggle.
const USE_PROD = import.meta.env.VITE_USE_PROD === "true";

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
    // 메인 실데이터 사례 (docs/meeting-notes/UI/MySQL_실데이터_연동_계획.md).
    // signal_status/timeline/hotspots/visitor_profile/content_type 5종은
    // agents/ 파이프라인이 이 지역(region_id 51750) 실측 산출물을 만들어뒀음.
    signal_status: { url: "/prod/signal_status_51750.json", kind: "real" },
    timeline: { url: "/prod/timeline_51750.json", kind: "real" },
    // refactor/agents_db-full연동 브랜치에서 새로 생성됨 (agent_hotspots.py,
    // agent_visitor_profile.py, agent2_apply.py의 LLM 분류 결과).
    hotspots: { url: "/prod/hotspots_51750.json", kind: "real" },
    visitor_profile: { url: "/prod/visitor_profile_51750.json", kind: "real" },
    content_type: { url: "/prod/content_type_51750.json", kind: "real" },
    // agent3_match.py --region 51750 실행 결과 (2026-09-24, common.py의 load_input에
    // region 인자를 추가해 지역별 파일을 읽도록 확장한 뒤 생성).
    checklist: { url: "/prod/checklist_51750.json", kind: "real" },
    // analysis/src/forecast/export_forecast.py --region 51750 (7일 예측, 09-26 실측화).
    forecast: { url: "/prod/forecast_51750.json", kind: "real" },
    // analysis/src/forecast/export_signal_series.py -- 신호 추이·예측 패널의 차트 입력.
    signal_series: { url: "/prod/signal_series_51750.json", kind: "real" },
    // agents/agent4_precedent.py --region 51750 (연구보고서 사례, 원문 인용).
    precedent: { url: "/prod/precedent_51750.json", kind: "real" },
    // briefing/before_after는 아직 파일이 없다 -- "unsupported" 처리.
    // briefing은 forecast_51750이 생겼으므로 agent5_briefing.py --region 51750으로 만들 수 있다.
  },
  geoje: {
    // 대비 사례 (총량은 그대로인데 특정 지점에만 쏠리는 패턴).
    // signal_status/timeline/content_type 모두 agents/ 파이프라인의 실측
    // 산출물(기본 지역 = 거제이므로 파일명에 지역코드 접미사 없음)을 그대로 사용.
    signal_status: { url: "/prod/signal_status.json", kind: "real" },
    // analysis/src/forecast/export_forecast.py (7일 예측, 09-26 실측화 -- 목업 대체).
    forecast: { url: "/prod/forecast.json", kind: "real" },
    signal_series: { url: "/prod/signal_series.json", kind: "real" },
    // agent_visitor_profile.py, agent_hotspots.py 실행 결과 (refactor/agents_db-full연동).
    visitor_profile: { url: "/prod/visitor_profile.json", kind: "real" },
    hotspots: { url: "/prod/hotspots.json", kind: "real" },
    content_type: USE_PROD
      ? { url: "/prod/content_type.json", kind: "real" }
      : { url: "/mock/content_type.json", kind: "mock" },
    // agent3_match.py 실행 결과. hotspots/visitor_profile/content_type이 모두
    // 실측이 되면서 입력 4종이 전부 실측이 돼 파일 자체도 _mock:false로 바뀌었다
    // (09-20엔 hotspots/visitor_profile이 아직 mock이라 _mock:true였음).
    checklist: { url: "/prod/checklist.json", kind: "real" },
    // agents/agent4_precedent.py (연구보고서 사례 6건, 원문 인용 -- 목업 대체).
    precedent: { url: "/prod/precedent.json", kind: "real" },
    before_after: { url: "/mock/before_after.json", kind: "mock" },
    timeline: { url: "/prod/timeline.json", kind: "real" },
    // agent5_briefing.py 실행 결과. 라이브 LLM 호출(web/api/briefing.js)은
    // 폐기했다 -- "AI가 매번 새로 쓰는" 방식은 D-04의 "매일 같은 문장 틀이어야
    // 어제와 비교된다"는 설계 근거와 어긋난다. 나중에 실시간성이 필요해지면
    // 이 정적 파일을 읽는 대신 agent5_briefing.py 자체를 최신 데이터로 재실행하는
    // 방식으로 가야 한다(에이전트 루프 밖에서 별도 LLM 호출을 만들지 않는다).
    // forecast가 실측이 된 뒤 다시 생성돼 파일도 _mock:false다.
    briefing: { url: "/prod/briefing.json", kind: "real" },
  },
  yeosu: agentRegion("12130"),
  ulleung: agentRegion("47940"),
  sokcho: agentRegion("51210"),
  inje: agentRegion("51810"),
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
  { key: "yeosu", label: "여수시" },
  { key: "sokcho", label: "속초시" },
  { key: "inje", label: "인제군" },
  { key: "ulleung", label: "울릉군" },
  { key: "chungju", label: "충주시" },
];

export function getManifestEntry(region, dataType) {
  return REGION_MANIFEST[region]?.[dataType] ?? null;
}
