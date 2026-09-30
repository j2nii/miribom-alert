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
// Adding or removing a production file is a manifest edit, not a runtime toggle.

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
    // scripts/export_recent_youtube.py · export_recent_content_types.py -- 최근 영상·콘텐츠 유형
    recent_youtube: real("recent_youtube"),
    recent_content_type: real("recent_content_type"),
    // analysis/src/forecast/export_forecast.py · export_signal_series.py (228개 시군구 공통 모델)
    forecast: real("forecast"),
    signal_series: real("signal_series"),
    // analysis/src/forecast/monthly_outlook.py -- 6개월 월별 방문객 전망
    outlook: real("outlook"),
  };
}

export const REGION_MANIFEST = {
  yeongwol: {
    daily_peak: { url: "/mock/daily_peak.json", kind: "mock" },
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
    recent_youtube: { url: "/prod/recent_youtube_51750.json", kind: "real" },
    recent_content_type: { url: "/prod/recent_content_type_51750.json", kind: "real" },
    // agent3_match.py --region 51750 실행 결과 (2026-09-24, common.py의 load_input에
    // region 인자를 추가해 지역별 파일을 읽도록 확장한 뒤 생성).
    checklist: { url: "/prod/checklist_51750.json", kind: "real" },
    // analysis/src/forecast/export_forecast.py --region 51750 (7일 예측, 09-26 실측화).
    forecast: { url: "/prod/forecast_51750.json", kind: "real" },
    // analysis/src/forecast/export_signal_series.py -- 신호 추이·예측 패널의 차트 입력.
    signal_series: { url: "/prod/signal_series_51750.json", kind: "real" },
    outlook: { url: "/prod/outlook_51750.json", kind: "real" },
    // agents/agent4_precedent.py --region 51750 (연구보고서 사례, 원문 인용).
    precedent: { url: "/prod/precedent_51750.json", kind: "real" },
    // briefing/before_after는 아직 파일이 없다 -- "unsupported" 처리.
    // briefing은 forecast_51750이 생겼으므로 agent5_briefing.py --region 51750으로 만들 수 있다.
  },
  geoje: {
    daily_peak: { url: "/mock/daily_peak_geoje.json", kind: "mock" },
    // 대비 사례 (총량은 그대로인데 특정 지점에만 쏠리는 패턴).
    // signal_status/timeline/content_type 모두 agents/ 파이프라인의 실측
    // 산출물(기본 지역 = 거제이므로 파일명에 지역코드 접미사 없음)을 그대로 사용.
    signal_status: { url: "/prod/signal_status.json", kind: "real" },
    // analysis/src/forecast/export_forecast.py (7일 예측, 09-26 실측화 -- 목업 대체).
    forecast: { url: "/prod/forecast.json", kind: "real" },
    signal_series: { url: "/prod/signal_series.json", kind: "real" },
    outlook: { url: "/prod/outlook.json", kind: "real" },
    // agent_visitor_profile.py, agent_hotspots.py 실행 결과 (refactor/agents_db-full연동).
    visitor_profile: { url: "/prod/visitor_profile.json", kind: "real" },
    hotspots: { url: "/prod/hotspots.json", kind: "real" },
    content_type: { url: "/prod/content_type.json", kind: "real" },
    recent_youtube: { url: "/prod/recent_youtube_48310.json", kind: "real" },
    recent_content_type: { url: "/prod/recent_content_type_48310.json", kind: "real" },
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
    daily_peak: { url: "/mock/daily_peak.json", kind: "mock" },
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
  { key: "yeongwol", label: "영월군", region_id: "51750" },
  { key: "geoje", label: "거제시", region_id: "48310" },
  { key: "yeosu", label: "여수시", region_id: "12130" },
  { key: "sokcho", label: "속초시", region_id: "51210" },
  { key: "inje", label: "인제군", region_id: "51810" },
  { key: "ulleung", label: "울릉군", region_id: "47940" },
  { key: "chungju", label: "충주시", region_id: "43130" },
];

// 전국 시군구: 사례 지역이 아닌 곳은 지역 키가 5자리 지역코드("51150")다. 데이터랩·이동통신·검색지수만으로
// 만드는 3종(경보 판정·신호 추이·7일 예측)을 data/prod/regions/에서 읽는다. 목록은 regions/index.json
// (scripts/build_region_index.py)이 가지고 있고, 여기서는 파일 경로 규칙만 안다.
export const NATIONAL_TYPES = ["signal_status", "signal_series", "forecast", "outlook"];
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

// 9종 계약 중 이 지역에 몇 개가 있고 그중 몇 개가 실측인지. 지역마다 준비 상태가 달라서
// 어떤 화면은 비어 있는데, 그 이유를 지역 선택기 옆에서 바로 알려 주기 위한 것이다
// (처음 온 사람은 빈 화면을 고장으로 읽는다).
// 9종 데이터 계약. briefing은 이 9종을 입력으로 agent5가 만들어 내는 산출물이라 계약 수에
// 포함하지 않는다(web/api/query.js의 TOOLS 목록과 같은 기준). 이걸 빼먹으면 거제가
// "10/9종"으로 표시된다.
export const DATA_TYPES = [
  "signal_status",
  "forecast",
  "visitor_profile",
  "hotspots",
  "content_type",
  "checklist",
  "precedent",
  "before_after",
  "timeline",
];

export function getRegionCoverage(region) {
  const entries = DATA_TYPES.map((t) => getManifestEntry(region, t)).filter(Boolean);
  return {
    total: DATA_TYPES.length,
    available: entries.length,
    real: entries.filter((e) => e.kind === "real").length,
  };
}
