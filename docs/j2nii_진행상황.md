# 진행 상황 (j2nii · 프론트엔드)

> 최종 갱신: **2026-09-25(금)** · 작성 담당: 역할3(프론트엔드) — j2nii
> 관련 문서: `docs/진행상황.md`(전체 프로젝트), `docs/설계결정.md`(D-01~D-13), `docs/meeting-notes/UI/`(자연어 질의 인터페이스 조사·계획, MySQL 실데이터 연동 계획), `docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf`

---

## 한 줄 요약

**`web/`에 실제 Vite+React 앱을 새로 세우고, 9종+briefing 스키마를 실제로 읽어 그리는 AREA 0~4 화면을 전부 완성했다. AREA 0에 자연어 질의 채팅(실제 tool-calling + 스트리밍, Upstage Solar)을 추가했다. agents 브랜치가 안내한 `signal_status`/`checklist`/`timeline` 스키마 변경 중 화면이 깨지는 부분(Tier 1)은 반영 완료. MySQL DB(`tour_earlywarning`)에 직접 연결해보기도 했으나(§14~16), `agents/` 폴더(judge_signal_status.py, agent1_timeline.py, agent5_briefing.py 등)가 이미 DB→JSON 변환을 전담하는 정본 파이프라인임을 확인하고 우리 코드는 걷어낸 뒤 그 산출물을 쓰는 쪽으로 최종 정리했다(§17~18) — `signal_status`/`timeline`(영월·거제)과 `checklist`(거제)가 실데이터로, "AI 정책 초안 도우미"도 라이브 LLM 호출 대신 agent5의 정적 브리핑을 표시하는 방식으로 바뀌었다.**

**(09-24~09-25 추가) `refactor/agents_db-full연동` 브랜치가 develop에 병합된 뒤, 그 브랜치가 만든 `hotspots`/`visitor_profile`/`content_type`(5개 지역) 실측 산출물을 프론트에 마저 연결했다(§24) — 이 과정에서 실측 데이터가 옵셔널 필드를 비워도 무조건 읽던 컴포넌트 버그 2건을 발견해 고쳤다. 영월 콘텐츠 분류에서 유튜브 검색이 지역명이 전혀 없는 강릉 영상을 섞어 온 것을 발견해 `agent2_content_type.md` 프롬프트에 지역 검증 규칙을 추가했다(§25 — 완전히 해결되진 않음). `agents/common.py`에 지역 인자를 추가해 `agent3_match.py`/`agent5_briefing.py`가 거제 외 지역도 처리할 수 있게 확장하고, 영월 `checklist`를 실측으로 만들었다(§26 — `briefing`은 forecast 부재로 아직 보류). 마지막으로 5개 에이전트+비에이전트 스크립트의 현황을 정리한 문서와 실제 화면 캡처를 남겼다(§27).**

---

## 09-13 작업 (AREA 0~4 골격)

### 1. `web/` 프로젝트 셋업
- `package.json`/`vite.config.js`/`index.html`/`main.jsx` 신규 — 번들러 없던 빈 폴더에 실제 Vite+React 앱을 처음부터 구축
- `vite.config.js`의 `publicDir`을 리포지토리 루트 `data/`로 지정 — `data/mock/*.json`은 `/mock/*.json`, `data/prod/*.json`은 `/prod/*.json`으로 그대로 서빙됨. 복사 스크립트 없이 `scripts/gen_mock.py` 재실행 결과가 즉시 반영된다

### 2. 데이터 로더 (`web/src/data/`)
- `loadData.js` — `loadData(dataType, {region})`: 매니페스트 조회 → `fetch` → 봉투(envelope) 반환. 실패/미지원 시 상태 코드로 구분
- `manifest.js` — `REGION_MANIFEST`: 지역별 데이터 타입 → `{url, kind: "real"|"mock"|"unsupported"}`. 목업→실데이터 전환은 이 파일 한 줄만 바꾸면 됨

### 3. AREA 0~4 전 화면 실동작
| 화면 | 구현 내용 |
| --- | --- |
| AREA 0 관제 대시보드 | `signal_status`+`forecast` 기반 경보 배지·게이지, 오늘자 예측 티저 + **09-17: 자연어 질의 채팅 위젯** |
| AREA 1 신호 스캔 | 3중 교차검증(확신도 박스), 90일 예측 차트, 인기 관광지 랭킹, 방문객 프로파일 |
| AREA 2 콘텐츠·유형 | 4탭(유튜브/SNS 언급량/실제 검색 장소/콘텐츠 유형 요약) |
| AREA 3 정책 브리핑 | 체크리스트(phase별 그룹, top5+더보기, 매뉴얼 인용), 선례 카드, AI 정책 초안 도우미 |
| AREA 4 성과 리포트 | 리드타임 타임라인, 조치 전후 KPI 비교 |

공통 원칙(`SourceBadge`/`CaveatNote`/`MockBanner`/`ManualRefCite`)을 모든 데이터 블록에 일괄 적용.

### 4~7. 레이아웃 이식·AI 브리핑 복원·시각화·충주 데이터
- 참조 데모(`docs/meeting-notes/tourism-radar-demo.html`) 레이아웃/토큰 그대로 이식
- `web/api/briefing.js` 서버리스 함수로 Upstage Solar 호출 복원 (규칙 기반 폴백 유지)
- `StageGauge`/`ConfidenceBox`/`TrendChart` 등 공통 시각화, 충주 생애주기 데이터 추가

(상세 내용은 이전 버전 기록 — 자세한 diff는 git log 09-13 커밋들 참고)

---

## 09-16~09-17 작업 (자연어 질의 인터페이스 + agents 브랜치 연동 대응)

### 8. 프론트 기능 조사 + 자연어 질의 인터페이스 계획
- `docs/meeting-notes/UI/프론트구조_기능조사_및_에이전트연동계획.md` — v3 회의 문서 대비 현재 프론트로 못 쓰는 기능, 5개 에이전트-프론트 연결 현황 조사
- `docs/meeting-notes/UI/자연어_질의_인터페이스_구현계획.md` — RAG 대신 실제 tool-calling을 쓴 이유(9종 데이터가 작고 이미 구조화돼 있어 벡터 검색이 불필요), Upstage Solar의 tool-calling 지원을 공식 문서로 확인한 근거

### 9. `web/api/query.js` — 자연어 질의 인터페이스 백엔드 (신규)
- `web/api/_lib/dataManifest.js` — `manifest.js`의 서버 전용 복제본 (Vercel Node 함수는 `import.meta.env`를 못 읽어서 분리)
- Upstage Solar의 OpenAI 호환 `tools`/`tool_choice` 파라미터로 9종 데이터를 각각 하나의 도구(`get_signal_status` 등)로 노출 → 모델이 질문에 필요한 것만 스스로 호출
- 답변은 NDJSON으로 스트리밍 (`{type:"token"}` 반복 후 `{type:"done", usedDataTypes, envelopes}`) — 한 번에 뚝 떨어지지 않고 실시간으로 보임
- tool-calling 자체가 실패하면 9종 데이터를 전부 컨텍스트에 넣는 단일 호출로 폴백

### 10. `ChatWidget.jsx` — AREA 0 채팅 UI (신규)
- AREA0에서 좌측 대시보드와 나란히 배치(docked), AREA0 전체가 스크롤로 뷰포트를 완전히 벗어나야만 floating 토글 버튼으로 전환 (`IntersectionObserver`가 AREA0 영역 전체를 감시)
- 접힌 아이콘 상태는 화면 좌/우 여백 안에서만 이동 가능(스크롤바에 안 가리게 `document.documentElement.clientWidth` 기준으로 계산), 펼친 패널은 화면 전체에서 자유롭게 드래그
- 드래그와 클릭을 픽셀 이동량으로 구분해 오탐 방지
- `react-markdown`으로 답변 렌더링 (자체 정규식 파서 대신 라이브러리 선택 — XSS 안전성 + 목록/굵게 등 확장성 이유)
- 질문 입력창은 최소 2줄(56px)에서 최대 120px까지 자동으로 늘어나고 그 이상은 스크롤

### 11. `web/dev-server.mjs` — 로컬 개발용 API 서버 (신규)
- 이 개발 환경에서 `vercel dev`가 yarn 미설치·npm 레지스트리 오류로 계속 실행 실패해, `api/*.js` 핸들러를 그대로 Node `http` 서버로 감싸는 대체 서버 추가
- `web/vite.config.js`에 `/api` → `localhost:3001` 프록시 추가 — `npm run dev:api` + `npm run dev` 두 터미널이면 `vercel dev` 없이도 전체 기능(스트리밍 포함) 테스트 가능. Vercel 배포에는 영향 없음 (`api/` 밖에 있어 함수로 인식 안 되고, 프록시는 `vite dev` 전용)

### 12. agents 브랜치 PR 스키마 변경 대응 (Tier 1 — 화면 깨짐 방지, 완료)
agents 브랜치가 DB 연결로 실데이터를 만들면서 `signal_status`/`checklist`/`timeline` 계약이 바뀌었다. 인계 메시지 본문뿐 아니라 `origin/agents`의 실제 스키마 파일을 직접 diff해서 확인하고 아래 4건을 고쳤다:
1. `ChecklistPanel.jsx` — `phase` enum에 `"사전(예보 대응)"`이 추가됐는데 `PHASE_ORDER`가 몰라서 해당 항목이 **에러 없이 화면에서 통째로 사라지는** 버그 → 목록에 추가
2. `ChecklistPanel.jsx` — `matched_for.congestion_level` 무방비 접근 → 없으면 "미측정" 표시
3. `LeadTimeTimeline.jsx` — `spatial_type`/`content_type`/`lead_time_days` 생략 가능해진 것 방어 + **레이블 오류 수정**("콘텐츠 확산 → 조치 시행"이 아니라 "→ 방문 급증"이 맞는 정의) + 신규 `lags.*`(조치까지 시차, 신호가 조치보다 며칠 앞섰는지) 표시 추가
4. `SignalStatusPanel.jsx`/`CrossValidationLights.jsx` — `congestion_level` 없으면 숨기지 않고 "미측정" 명시(스키마 주석 의도), `cross_validation[].value`가 null일 때 고정 문구 대신 `missing_reason` 사용

**Tier 2(새 필드 활용: 지역별 파일 5곳 추가, `signal_status.history` 추이 그래프, `checklist.assessment.out_of_scope` 노출 등)와 Tier 3(`web/api/briefing.js`를 사전 생성된 `data/prod/briefing.json` 읽기 구조로 바꿀지)는 아직 미착수** — Tier 3는 팀 논의가 먼저 필요한 아키텍처 결정이라 임의로 진행하지 않음.

### 13. `develop`으로의 PR 초안 준비
`UI/UX` → `develop` PR 제목·본문 초안 작성 (agents 브랜치 PR과 같은 시점에 올라갈 예정). agents PR이 지적한 스키마 이슈에 이미 대응했다는 내용 포함.

---

## 09-20~09-23 작업 (MySQL 실데이터 연동 — signal_status)

### 14. DB 접속 및 공식 사용설명서 대조
- `tour_earlywarning` MySQL 서버 접속 확인. **SSL 필수(Require) 계정**이라 `ssl: { rejectUnauthorized: false }` 없이는 자격증명이 맞아도 `ER_ACCESS_DENIED_ERROR`가 나는 함정이 있었음 — 비밀번호 문제로 착각하기 쉬움
- 09-22 분석팀이 배포한 공식 문서(`docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf`)와 직접 조회 결과를 대조 — 그 사이 테이블/뷰가 43개→97개(현재 107개)로 크게 늘어남을 확인
- DB 데이터는 **의도적으로 동결**되어 있음(공모전용 가상 기준시점) — 화면의 "오늘"은 실제 날짜가 아니라 `2026-08-14`로 고정(`web/api/_lib/referenceDate.js`)

### 15. 메인 사례를 거제 → 영월로 변경
- PDF의 팀 작업 권장 순서("영월 주 사례와 거제 대비 사례 시각화")에 맞춰, **영월을 메인 실데이터 사례, 거제를 대비 사례**(총량은 크지만 신호는 약한 지역)로 재설정
- `region_id`: 영월군 `51750`, 거제시 `48310` (둘 다 `dim_region`/`youtube_video`에 실데이터 존재 확인)
- `web/src/App.jsx` 기본 지역을 `geoje` → `yeongwol`로 변경 (AI 대화창의 기준 지역도 이 값을 공유하므로 자동으로 함께 바뀜)

### 16. 아키텍처 변경: 라이브 API → 1회 생성한 정적 파일
- 처음엔 `web/api/signal-status.js` 서버리스 함수로 요청마다 DB를 조회하는 방식으로 만들었으나, 실제 측정해보니 **`vw_daily_anomaly_scored` 뷰가 지역 하나로 필터링해도 180초 이상** 걸림을 발견(다른 뷰는 정상, 이 뷰만 228개 지역 전체를 먼저 계산한 뒤 거르는 구조로 추정) — Vercel 함수 타임아웃을 훌쩍 넘겨 폐기
- 대신 `web/scripts/generate-signal-status.mjs`로 **1회 추출 → `data/prod/{region}_signal_status.json` 정적 파일 커밋** 방식 채택 (agent②의 `content_type.json`과 동일 패턴). 영월 162초, 거제 132초 걸려서 생성 완료, 둘 다 기준일 기준 `alert_level: 관심`
- `docs/설계결정.md` D-05(3개 신호 중 몇 개 초과했는지로 등급 산정)를 `vw_daily_anomaly_scored`의 `is_interest_spike_current`/`is_demand_spike_current`/`is_viral_candidate` 3개 불리언에 그대로 대응시켜 판정 로직 구현
- `web/src/data/manifest.js`/`web/api/_lib/dataManifest.js`에 영월 신규 추가, 영월·거제의 `signal_status`를 `kind: "real"`로 전환. 나머지 8개 계약은 이번 라운드 범위 밖(영월은 지역명 불일치를 피하기 위해 "unsupported" 처리)
- 상세 설계는 `docs/data-pipeline/UI_MySQL_실데이터_연동_계획.md` 참고 (향후 24시간 자동 재수집 전환 시 필요한 변경사항도 정리해둠 — `REFERENCE_DATE` 동적화 + 스케줄러 추가 두 가지뿐, 수정 비용 낮음)

### 17. §16 뒤집음: `agents/` 파이프라인 산출물 사용으로 최종 전환
`data/prod/`를 다시 확인해보니, `agents/judge_signal_status.py`와 `agents/agent1_timeline.py`가 **영월(`signal_status_51750.json`, `timeline_51750.json`)·거제(`signal_status.json`, `timeline.json`) 실측 산출물을 이미 만들어둔 상태**였다(09-20 생성, `_mock:false`). 게다가 이쪽이 프로젝트가 원래 정의한 **"관심(SNS 언급량)·의도(내비게이션 검색)·실현(방문자수)" 3중 교차검증**을 월 단위로 제대로 구현하고 있었고, 24개월 `history`도 포함돼 있어 §16에서 우리가 만든 일별 네이버 검색 z-score 기반 판정(관심·의도·실현 정의와 안 맞고 history도 없음)보다 나았다.

**되돌린 것**: `web/api/_lib/db.js`, `web/api/_lib/referenceDate.js`, `web/scripts/generate-signal-status.mjs`, 우리가 생성했던 `data/prod/{region}_signal_status.json` 2개 삭제. `mysql2` 의존성 제거.

**바꾼 것**: `manifest.js`/`dataManifest.js`가 이제 `agents/` 산출물을 직접 가리킴 — 영월·거제의 `signal_status`, `timeline`을 실측(`kind: real`)으로, 거제의 `checklist`도 `data/mock/`(09-12 손 작성, 3건) 대신 `data/prod/checklist.json`(agent3 실행 결과, 09-20, 14건 — 단 이 파일 자체는 아직 일부 입력이 mock이라 `_mock:true`로 정직하게 표시됨)으로 전환.

**교훈**: MySQL에 직접 연결 가능하다고 해서 그게 이 프로젝트의 정본 데이터 생성 경로는 아니었다 — `agents/` 폴더가 이미 DB→JSON 변환을 전담하는 공식 파이프라인이었고, 뭔가 새로 만들기 전에 `data/prod/`에 이미 있는지부터 확인했어야 했다.

### 18. 브리핑 아키텍처도 agent5에게 일임 — 라이브 LLM 호출 폐기
같은 논리를 AI 정책 초안 도우미에도 적용했다. `web/api/briefing.js`는 버튼을 누를 때마다 Upstage를 실시간 호출해 3문단을 매번 새로 생성했는데, 이건 `agents/agent5_briefing.py`의 역할과 겹칠 뿐 아니라 **D-04의 설계 근거("매일 같은 문장 틀이어야 어제와 비교된다")와도 어긋난다** — 매번 자유 생성되는 문장은 재현성이 없다. agent5는 1·2문단을 코드가 고정 템플릿으로 쓰고 3문단(종합 판단·조치 선택)만 LLM이 쓰는 방식이라 이 문제가 없다.

**되돌린 것**: `web/api/briefing.js`, `web/src/lib/briefingTemplate.js`(규칙 기반 폴백) 삭제, `dev-server.mjs`에서 라우트 제거.

**바꾼 것**: `BriefingGenerator.jsx`를 "생성" 버튼이 있는 컴포넌트에서, `agents/agent5_briefing.py`가 만든 `data/prod/briefing.json`을 그대로 표시하는 컴포넌트로 재작성. `Area3Briefing.jsx`가 `useRegionData("briefing", region)`으로 불러옴(다른 AREA3 데이터와 동일한 패턴). `manifest.js`/`dataManifest.js`에 `briefing` 계약 추가(`kind: "mock"` — 파일 자체가 `_mock:true`, checklist와 같은 이유).

**향후 실시간성이 필요해지면**: 사용자 지침에 따라 "버튼 누를 때마다 데이터를 최신화하고 agent5_briefing.py 로직 자체를 다시 돌리는" 방식으로 가야 한다 — 에이전트 루프 밖에 별도 LLM 호출 경로를 다시 만들지 않는다.

## 09-23 작업 (`refactor/agents_db-full연동` 브랜치 — hotspots/visitor_profile/content_type 다지역 실측화)

### 19. hotspots·visitor_profile 신규 에이전트 스크립트로 실측 전환
계획 문서는 `docs/data-pipeline/agents_db_full연동_계획.md`. §17에서 확인한 대로 실측 여부를 전수 조사한 결과 `hotspots`/`visitor_profile`은 DB에 소스가 있는데 변환 스크립트가 없어서 목업이었다 — 이 둘을 채웠다.

- `collection/db_export.py`에 `major_attraction_visitors_monthly`(관광지 단위 방문자수, `attraction_region_map`으로 canonical_region_id 조인), `datalab_detail_row`(성연령/거리/거주지/소비/동반유형 원자료, `data_group` 7종 + 사례 지역 필터)를 추가.
- `agents/agent_hotspots.py` 신규: 지역당 상위 10곳 내외를 방문자수·전월 대비 증감률로 뽑는다. `spatial_type`(매뉴얼 p.13 4분류)은 DB에 없어 사람이 채운 소규모 룩업 테이블(`POI_SPATIAL_TYPE`)로 분류 — 분류가 없는 POI는 순위에서 제외했다(발명 금지). `coord`/`visitor_mix`/`congestion_level`/`bottleneck`은 이 DB로 못 구해 비웠다.
- `agents/agent_visitor_profile.py` 신규: `datalab_detail_row`는 같은 항목도 여러 수집 시점(`query_start_month`~`query_end_month`)으로 중복 적재돼 있어 **가장 최근 구간만** 쓴다. DB 거리 구간(6개)·연령 구간(8개)·동반유형(9개)을 스키마 구간으로 재매핑했고(경계가 안 맞는 거리 구간은 폭 비례 분할), `spending`은 내국인 데이터에 금액 필드가 없어 외국인 소비 데이터(금액 있음)로 대체했다 — caveat에 명시. `total_visitors`는 `datalab_monthly_panel`(signal_status와 동일 소스)에서 가져왔다.
- 6개 사례 지역(`CASE_REGIONS`) 전부 생성 확인 (`hotspots.json`/`hotspots_{region}.json`, `visitor_profile.json`/`visitor_profile_{region}.json`).

### 20. content_type 5개 지역 확장 (표본 축소 명시)
`agent2_apply.py`는 거제 하나만 처리했다(수집 원본 JSON이 지역당 1개 파일). 나머지 5개 지역은 그 원본이 없어(`data/raw/youtube/`는 gitignore 대상) DB 스냅샷(`youtube_case.csv`, 지역당 950~1500개)을 대신 쓰되, 전량 분류는 이번 범위를 벗어나 **조회수 상위 15개만** 분류했다(거제도 원래 "검색 결과 상위 영상만 수집"이었으므로 같은 성격의 표본 제한 — caveat에 명시). 분류는 제목·채널명·검색어 텍스트만으로 판정했다(설명·태그가 이 스냅샷엔 없음).

지역별 특징: 울릉·속초는 "바가지 요금" 논란 뉴스가 조회수 상위권에 몰려 있어 데드존(수요 이탈) 신호가 다수 잡혔다. 영월은 단종 역사 다큐 채널이 상위권 다수라 관광무관 비중이 높았고, 인제는 검색어("인제")와 우연히 겹치는 무관 콘텐츠(중국 인재전쟁 다큐, 밈 애니메이션 등)가 상위권에 많았다.

### 21. checklist 실측 전환, briefing은 여전히 목업(정상)
`hotspots`/`visitor_profile`이 실측이 되자 `agent3_match.py`(거제, 단일 지역)를 재실행 — 입력 4개(signal_status/hotspots/visitor_profile/content_type)가 전부 실측이 돼 `checklist.json`의 `_mock`이 `true`→`false`로 바뀌었다. `agent5_briefing.py`도 재실행했으나 입력에 `forecast`(별도 브랜치 진행 중, 이번 범위 제외)가 포함돼 `briefing.json`은 의도대로 `_mock:true`로 남았다 — forecast 브랜치가 합쳐져야 완전한 실측이 된다.

### 22. 재생성물의 DB 적재는 하지 않기로 결정
계획 단계에서 "재생성되는 prod JSON을 DB에 적재해서 보관해야 하나"라는 논의가 있었다. 결론은 하지 않는 것 — 이 프로젝트는 추세/히스토리가 필요하면 매번 원천 DB에서 다시 계산하는 방식(`signal_status`의 `history[]`처럼)으로 이미 해결돼 있어 옛 JSON 버전 자체를 보존할 제품상 이유가 없고, `agents/` 파이프라인은 현재 읽기 전용으로만 DB에 접속해 쓰기 경로를 새로 만드는 비용이 크다. `data/mock/*.json`은 기존 관례대로(계약/폴백/토글 용도) 계속 유지하되 삭제하지 않는다.

`_mock:false`로 새로 바뀐 파일: `data/prod/checklist.json`. 신규 생성: `hotspots*.json`(6개), `visitor_profile*.json`(6개), `content_type_{51750,12130,47940,51210,51810}.json`(5개). `data/mock/hotspots.json`/`visitor_profile.json`/`checklist.json`은 그대로 유지.

**범위 밖**: `forecast`(별도 브랜치), `web/` 쪽 `manifest.js`/`dataManifest.js` 연동(산출물만 만드는 게 이번 브랜치 목표라 화면 반영은 별도 작업).

### 23. 데이터 담당 팀 공유 필요 — `youtube_video` 테이블에 description/tags 컬럼이 없음

`agent2_apply.py`(콘텐츠 유형 분류)를 하드코딩(`RESULTS`)에서 실제 LLM 호출로 교체하는 과정에서 확인함: DB `youtube_video` 테이블에 `description`/`tags` 컬럼 자체가 없다(`DESCRIBE youtube_video`로 직접 확인 — `video_id/region_id/title/channel_name/view_count/...`만 있음. `collection/db_export.py`의 쿼리가 빠뜨린 게 아니라 테이블에 원천적으로 없다).

문제는 `agents/prompts/agent2_content_type.md`의 판단 규칙이 "**근거는 영상에 실제로 있는 표현을 인용한다. 제목·설명·태그에서 가져온다**"고 명시할 만큼 이 필드가 분류 품질에 실제로 쓰인다는 점이다 — 제목만으로는 "예능·방송 노출형"과 "관광무관"처럼 미묘한 구분을 판정하기 어렵다.

지금은 `collection/youtube_collect.py`(YouTube Data API 직접 재수집, description/tags 포함)로 우회했다. 다만 이 재수집을 매번 반복하는 대신, **데이터 담당 팀이 애초에 `youtube_video` 테이블 적재 시 description/tags를 함께 받아주면** 이 우회가 필요 없어진다 — 컬럼 추가를 제안할 가치가 있다는 정도로 이번에는 기록만 남긴다(DB는 조회 전용 계정이라 이 프로젝트가 직접 스키마를 바꿀 수 없고, 바꾸는 것 자체도 우리 결정 사항이 아니다).

---

## 09-24~09-25 작업 (UI/UX 브랜치 — hotspots/visitor_profile/content_type 프론트 반영 + content_type 지역 오분류 수정 + checklist 다지역 확장)

### 24. hotspots/visitor_profile/content_type(거제·영월) 프론트 반영 + 컴포넌트 버그 2건 수정

`refactor/agents_db-full연동` 브랜치(§19~23)가 develop에 PR#10으로 병합된 뒤, `manifest.js`/`dataManifest.js`가 아직 그 산출물을 안 가리키고 있어 산출물은 있는데 화면엔 안 뜨는 상태였다. 범위는 **기존 지역(영월·거제)만** — 여수·울릉·속초·인제는 이미 실측 파일이 있지만 `REGIONS` 선택지 자체에 없어 이번엔 손대지 않았다(사용자 결정: "우선 기존 지역 위주로 프론트를 완성한 뒤 시계열 예측 모델이 잘 맞는 지역 기준으로 지역을 늘린다").

manifest만 바꾸면 안 됐다 — 실측 데이터는 목업과 달리 스키마상 선택 필드를 의도적으로 비워두는데(발명 금지 원칙), 렌더 컴포넌트 두 곳이 그 필드가 항상 있다고 가정하고 있었다:
- `VisitorProfileCard.jsx` — `local_external_mix.local`을 무조건 읽어 실측 데이터 연결 시 `Cannot read properties of undefined` 크래시. `local_external_mix`가 있을 때만 렌더링하도록 수정.
- `HotspotRanking.jsx` — `congestion_level`을 무조건 문자열에 끼워 넣어 "혼잡도 undefined/5"로 표시됨. 있을 때만 "· 혼잡도 N/5"를 붙이도록 수정.

`manifest.js`/`dataManifest.js`: 거제 `hotspots`/`visitor_profile`을 mock→real로, `checklist`의 `kind` 라벨을 실제 상태(`_mock:false`)에 맞게 정정, 영월에 `hotspots`/`visitor_profile`/`content_type` 3종 추가. 로컬 dev 서버 + 임시 설치한 Playwright로 두 지역 모두 크래시·콘솔 에러 없이 렌더링되는 것을 확인했다.

### 25. content_type — 영월 재수집 데이터에 강릉(다른 지역) 영상이 섞여 들어온 것을 발견·부분 수정

영월 content_type 화면을 보다가 강릉 관련 영상이 섞여 있는 것을 발견해 조사했다. 원인은 두 겹:
1. **수집 단계**(`collection/youtube_collect.py`): YouTube Data API의 `search.list`가 정확한 키워드 매칭이 아니라 의미 기반 유사도 검색이라, "영월 맛집" 등으로 검색해도 "영월"이라는 단어를 제목·설명·태그 어디에도 포함하지 않는 순수 강릉 콘텐츠가 섞여 들어왔다(재수집 63건 중 14건).
2. **분류 단계**(`agents/prompts/agent2_content_type.md`): "관광무관" 정의(v1.1)가 "지역명만 겹치고 방문 수요와 무관한 콘텐츠"만 다뤄서, "아예 대상 지역이 아닌 콘텐츠"를 걸러내라는 지시가 없었다. 그 결과 조회수 상위 50건에 포함된 강릉 영상 11건 중 2건만 관광무관으로 걸러지고 9건이 맛집형 등으로 정상 분류돼, "맛집형 40%(16건)" 같은 집계 수치에 다른 지역 콘텐츠가 섞여 있었다.

**조치**: 프롬프트 v1.2 — 판단 규칙 1번으로 "제목·설명·태그 어디에도 대상 지역명이 없으면 관광무관으로 분류"를 추가하고, `agent2_apply.py`에 `--region` 필터를 추가해 영월만 재실행했다.

**검증 결과**: 강릉 영상 11건 중 관광무관으로 걸러진 건수가 2건 → 5건으로 늘었다(3건 추가 정정, 신뢰도도 0.95로 상승). 전체 `unclassified_count`도 5건 → 17건으로 늘었다. **다만 완전히 해결되지는 않았다** — 나머지 6건은 프롬프트에 규칙을 명시했는데도 여전히 맛집형/코스·일정형으로 분류됐다. LLM이 규칙을 항상 따르지는 않는다는 뜻이라, 근본적으로는 수집 단계에서 지역명 포함 여부로 사전 필터링하는 것도 함께 검토해야 한다 — 다음 작업으로 남겨둔다.

### 26. agent3_match.py/agent5_briefing.py에 지역 인자 추가, 영월 checklist 실측 생성

`agent3_match.py`(checklist)와 `agent5_briefing.py`(briefing)는 원래 거제 단일 지역만 처리했다 — `agents/common.py`의 `load_input(name)`이 지역 구분 없이 항상 `{name}.json`(거제 전용 파일명)만 읽었기 때문이다. `load_input(name, region)`으로 확장해 `region` 인자가 있으면 `{name}_{region}.json`을 찾도록 하고(`agent_hotspots.py` 등 다른 지역별 산출물과 같은 파일명 규칙), 두 스크립트에 `--region` 옵션을 추가했다. 다른 지역 파일로 대신 채우지 않는다(발명 금지) — 지역별 파일이 없으면 그대로 에러를 낸다.

`python agents/agent3_match.py --region 51750 --provider upstage`로 영월 `checklist_51750.json`을 생성했다 — "주의" 단계·혼잡도 미측정 상황에서 22건 후보 중 19건 발동으로 매칭됐다(거제와 다른 조합).

**`agent5_briefing.py`는 영월에서 실행 불가**: `forecast`를 필수 입력으로 요구하는데, 영월은 forecast 데이터가 mock조차 없다(시계열 브랜치 미완 — `manifest.js`에도 영월 forecast 항목 자체가 없었음). 임시 mock forecast를 지어내 우회할 수도 있었지만 실제 값이 아닌 것을 화면에 올리는 셈이라(발명 금지 원칙과 상충) 보류했다 — forecast가 실측이든 목업이든 먼저 생기면 그때 실행한다.

`manifest.js`/`dataManifest.js`에 영월 `checklist` 추가(real).

### 27. 문서화 — 에이전트 현황 및 프론트 매핑 문서 작성, AREA1 스크린샷 클리핑 버그 발견

`docs/meeting-notes/UI/에이전트_현황_및_프론트_매핑.md` 신규 작성 — 프로젝트가 원래 번호를 붙인 5개 에이전트(①타임라인 ②콘텐츠 유형 ③매뉴얼 매칭 ④선례 조사 ⑤브리핑)를 하나씩(LLM 여부·프롬프트·모델·상태·프론트 위치), 그 번호에 속하지 않는 규칙 기반 스크립트(signal_status/hotspots/visitor_profile)를 별도로 정리하고 거제·영월 실제 화면 캡처를 붙였다.

캡처 과정에서 발견한 것: AREA1/AREA2는 `panel-scroll`(고정 높이 82vh + 내부 스크롤)인데, Playwright의 엘리먼트 스크린샷은 스크롤 전 보이는 부분만 캡처한다 — 그 결과 첫 AREA1 캡처엔 신호등급만 담기고 **핫스팟 랭킹이 통째로 안 담겨 있었다**. 스크롤을 임시로 해제(`overflow: visible`)하고 다시 캡처해 신호등급/핫스팟 랭킹 두 부분으로 나눠 저장했다. 실제 앱 동작에는 문제가 없는, 문서용 캡처 방법의 함정이었다.

---

## 확인된 사실 — 목업 수치의 성격

`scripts/gen_mock.py`를 직접 확인한 결과: `signal_status.json`의 `congestion_level`/`density`는 계산 로직이 아니라 **사람이 손으로 넣은 고정값**이다. 반면 `forecast`의 일별 방문객, `hotspots`의 방문객 수는 실제 공식(계절성+주말가중+노이즈, 순위감쇠+노이즈)으로 계산된다.

---

## 알려진 이슈 · 한계

| # | 이슈 | 상태 |
| --- | --- | --- |
| ① | 로컬에서 `/api/*` 서버리스 함수 테스트 | **해결** — `web/dev-server.mjs` + Vite 프록시로 `vercel dev` 없이도 로컬에서 전체 기능(스트리밍 포함) 확인 가능 |
| ② | `vercel dev` 자체는 이 환경에서 yarn 미설치·npm 레지스트리 오류로 계속 실패 | 미해결이지만 ①의 대체 서버로 실사용에는 지장 없음. 근본 해결하려면 로컬에 yarn 설치 또는 Vercel 프로젝트 Install Command를 npm으로 override(대시보드 작업) 필요 |
| ③ | Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY`/`YOUTUBE_API_KEY`가 등록 안 돼 있는 것을 확인함 (로컬 `.env`에만 존재) | **`UPSTAGE_API_KEY`는 등록 완료 확인됨(09-23).** `YOUTUBE_API_KEY` 등록 여부는 미확인 |
| ④ | AREA 2 "SNS 언급량"/"실제 검색 장소" 탭 근사치 대체 | 데이터 계약에 지점별 검색 세분화 파일 아직 없음 |
| ⑤ | agents 브랜치 스키마 변경 Tier 2/3 | Tier 3(브리핑 아키텍처)는 §18에서 해결(agent5 정적 파일로 전환). Tier 2(지역별 파일 확장, `signal_status.history` 추이 그래프 노출 등)는 여전히 미착수 |
| ⑩ | §17~18 작업(agents 산출물 전환, briefing 라이브 호출 폐기)이 아직 미커밋 | 커밋 필요 |
| ⑥ | 경주(MVP 2번째 후보 지역) 미지원 | `manifest.js`에 영월·거제·충주만 있음 |
| ⑦ | ~~작업이 커밋·푸시 안 됨~~ | **해결** — 09-17까지 및 09-20~09-23 MySQL 연동 작업(§16) 전부 `UI/UX` 브랜치에 커밋·푸시됨 |
| ⑧ | ~~`vw_daily_anomaly_scored`가 지역 필터링해도 180초+ 걸림~~ | **무의미해짐** — §17에서 이 뷰를 직접 쓰는 코드 자체를 폐기함. 다만 `agents/judge_signal_status.py`가 이 DB를 쓴다면 동일 성능 이슈가 있을 수 있어 참고 공유는 여전히 유효 |
| ⑨ | 세션 중 실수로 MySQL 비밀번호가 대화 로그에 노출된 적 있음 | **권장** — DB 관리자에게 `tour_team*` 계정 비밀번호 교체 요청 |
| ⑪ | `youtube_video` 테이블에 `description`/`tags` 컬럼이 없어 content_type 분류 품질이 제한됨(§23) | 미해결 — 데이터 담당 팀에 컬럼 추가 제안, 지금은 로컬 재수집으로 우회 |
| ⑫ | content_type 분류에 다른 지역(강릉 등) 영상이 섞여 들어와 일부가 정상 유형으로 오분류됨(§25) | **부분 해결(09-24)** — 프롬프트에 지역 검증 규칙 추가로 11건 중 5건은 정정됐으나 6건은 여전히 오분류. 수집 단계 사전 필터링 검토 필요 |
| ⑬ | `UI/UX` 브랜치가 이번 세션 커밋 4개만큼 `develop`보다 앞서 있고 아직 PR 안 됨(원격엔 push됨) | 미해결 — PR 생성 필요 |

---

## 남은 작업

| 순서 | 작업 | 상태 |
| --- | --- | --- |
| 1 | ~~Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY` 등록~~ | **완료** — `YOUTUBE_API_KEY` 등록 여부만 확인 필요 |
| 2 | ~~`develop`으로 PR 생성~~ | **완료** |
| 3 | ~~agents 브랜치 develop 병합 후 실데이터로 AREA 0/1/3/4 재확인~~ | **완료(09-24/25)** — 영월·거제 hotspots/visitor_profile/content_type/checklist 반영·검증(§24~26). 나머지 4개 지역은 10번 항목 참고 |
| 4 | Tier 2 반영 (지역 5곳 추가, `signal_status.history` 추이 그래프, checklist 신규 필드 등) | 미착수 — "지역 5곳 추가"는 10번과 중복, 시계열 모델이 확정될 때까지 의도적으로 보류 |
| 5 | ~~Tier 3 — 브리핑 아키텍처(`web/api/briefing.js` vs `data/prod/briefing.json`) 팀 논의~~ | **완료(09-23, §18)** — `data/prod/briefing.json`(agent5) 채택, 라이브 API 폐기 |
| 6 | 공공데이터포털(data.go.kr) API 키 신청 | 미착수 |
| 7 | 경주 지역 지원 추가 | 미착수 |
| 8 | 실 화면 클릭스루 QA (배포 URL, 브라우저 직접) | 미확인 — 09-24/25 검증은 전부 로컬 dev 서버 기준. 배포 URL에서는 아직 확인 안 됨 |
| 9 | ~~MySQL 연동 작업(§16) 커밋~~ | **완료** — `b79dfb2`~`27755b8` (§17에서 이 중 라이브 API/생성스크립트 부분은 되돌림) |
| 10 | 여수(`12130`)·울릉(`47940`)·속초(`51210`)·인제(`51810`)도 `agents/` 산출물이 이미 있음(`signal_status_*.json`, `timeline_*.json` 외 hotspots/visitor_profile/content_type도 09-23에 추가됨) — `manifest.js`에 지역 추가만 하면 바로 씀 | 미착수, 난이도 낮음(영월과 동일 패턴 반복) — 다만 09-24 기준 "시계열 모델이 잘 맞는 지역 먼저 고른다"는 정책으로 의도적 보류 |
| 11 | `briefing`(agent5)이 forecast 입력 때문에 `_mock:true`로 남음(거제) / 영월은 forecast 자체가 없어 아예 생성 불가 | 미착수 — forecast 브랜치 완료 대기(§26) |
| 11-1 | `checklist`/`content_type`을 다른 4개 지역(여수·울릉·속초·인제)까지 확장 | 미착수 — `--region` 옵션은 이미 만들어둠(09-24), 10번과 함께 결정되면 바로 실행 가능 |
| 12 | 24시간 자동 재수집이 시작되면 `agents/` 파이프라인(judge_signal_status.py 등) 재실행 주기 확인 | 미착수 — 이건 이제 우리(프론트) 담당이 아니라 agents 담당자의 자동화 범위, 조율만 필요 |
| 13 | `UI/UX` → `develop` PR 생성(이번 세션 커밋 4개) | 미착수 |
| 14 | content_type 지역 오분류 잔여 6건 해결 — `collection/youtube_collect.py` 수집 단계 사전 필터링 검토(§25) | 미착수 |
| 15 | `youtube_video` 테이블에 `description`/`tags` 컬럼 추가 요청(§23) | 미착수 — 데이터 담당 팀 결정 사항 |

---

## 산출물 위치

```
web/
  package.json, vite.config.js, index.html, .env.example, dev-server.mjs   ← dev-server.mjs 09-17 신규
  api/
    query.js                   ← 09-17 신규: 자연어 질의 인터페이스 (tool-calling + 스트리밍)
    (briefing.js는 09-23 §18에서 삭제 — data/prod/briefing.json 정적 표시로 전환)
    _lib/
      dataManifest.js          ← 09-17 신규: manifest.js의 서버 전용 복제본. 09-23 §17: signal_status/timeline/checklist를 agents/ 산출물로 전환
  src/
    main.jsx, App.jsx, index.css
    data/
      loadData.js, manifest.js
    hooks/
      useRegionData.js
    lib/
      format.js                 ← 09-23: briefingTemplate.js(규칙 기반 폴백)는 §18에서 삭제, 라이브 LLM 폴백이 더 이상 필요 없음
    components/
      common/                  ← SourceBadge, CaveatNote, MockBanner, ManualRefCite,
                                  Header, DataState, StageGauge, ConfidenceBox, TrendChart,
                                  ChatWidget.jsx (09-17 신규)
      area0-dashboard/         ← SignalStatusPanel(거제), LifecyclePanel(충주)
      area1-signal-scan/       ← CrossValidationLights, ForecastChart, HotspotRanking,
                                  VisitorProfileCard
      area2-content/           ← ContentTypeTabs, VideoCard, ContentTypeSummary, ZoneSignalBadge
      area3-briefing/          ← ChecklistPanel, PrecedentCards, BriefingGenerator
      area4-performance/       ← PerformanceReport, LeadTimeTimeline
    pages/
      Area0Dashboard.jsx ~ Area4Performance.jsx

docs/meeting-notes/UI/
  프론트구조_기능조사_및_에이전트연동계획.md   ← 09-17 신규
  자연어_질의_인터페이스_구현계획.md            ← 09-17 신규
  MySQL_실데이터_연동_계획.md                   ← 09-23 신규
  에이전트_현황_및_프론트_매핑.md               ← 09-25 신규: 5개 에이전트+규칙 스크립트별 LLM 여부·상태·화면 캡처 정리
  screenshots/                                  ← 09-25 신규: 거제·영월 AREA0~4 실제 화면 캡처

data/mock/chungju_signal_status.json, chungju_content_type.json   ← 충주 참고 사례
data/prod/                                                        ← agents/ 파이프라인 산출물 (실측)
  signal_status.json, signal_status_{12130,47940,51210,51750,51810}.json   ← judge_signal_status.py
  timeline.json, timeline_{12130,47940,51210,51750,51810}.json            ← agent1_timeline.py
  content_type.json, content_type_{12130,47940,51210,51750,51810}.json    ← agent2_apply.py (51750은 09-24 프롬프트 v1.2로 재분류)
  hotspots.json, hotspots_{12130,47940,51210,51750,51810}.json            ← agent_hotspots.py
  visitor_profile.json, visitor_profile_{12130,47940,51210,51750,51810}.json ← agent_visitor_profile.py
  checklist.json, checklist_51750.json (agent3_match.py, --region 지원 09-24 추가)
  briefing.json (agent5_briefing.py, 아직 _mock:true — forecast 입력이 mock. 영월은 forecast 부재로 파일 자체가 없음)
```

### 실행 명령

```bash
cd web
npm install

# 터미널 1 — 로컬 API 서버 (vercel dev 대체)
npm run dev:api

# 터미널 2 — 프론트
npm run dev              # http://localhost:5173, /api/* 도 정상 동작 (dev-server.mjs 경유)

npm run build             # 프로덕션 빌드 검증

# signal_status/timeline/checklist 등 실데이터 재생성은 이제 이 프로젝트가 아니라
# agents/ 쪽 스크립트 담당 (judge_signal_status.py, agent1_timeline.py 등, §17 참고)
```

---

## 사용자가 직접 해야 하는 항목 (Claude Code가 대신할 수 없음)

- ~~Vercel 계정 생성 및 배포~~ — **완료**
- ~~YouTube Data API v3 키 발급~~ — **완료**
- ~~Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY` 등록~~ — **완료(09-23 확인)**. `YOUTUBE_API_KEY` 등록 여부만 별도 확인 필요
- ~~`develop`으로 PR 생성~~ — **완료(09-23)**
- **agents 브랜치 PR과의 조율** — Tier 2/3 반영 시점, 공동 스키마 확정 논의
- **공공데이터포털 API 키 발급** — data.go.kr 로그인 필요
- **배포 URL 공유 + 실제 브라우저로 5개 화면 클릭스루 확인**
- ~~MySQL 연동 커밋~~ — **완료** (`b79dfb2`~`27755b8`, `UI/UX` 브랜치, §17에서 라이브 API/생성스크립트 부분은 agents/ 산출물 사용으로 되돌림)
- **MySQL 계정(`tour_team*`) 비밀번호 교체 요청** — 세션 중 실수로 대화 로그에 노출된 적 있음
- **agents 담당자와 조율**: 여수·울릉·속초·인제 4개 지역도 `signal_status`/`timeline`/`hotspots`/`visitor_profile`/`content_type` 실측 파일이 이미 있음(09-23) — 우리 쪽 `manifest.js`에 언제 추가할지(시계열 모델 확정 시점과 맞출지) 결정, `briefing`을 언제 실측 전환할지(forecast 브랜치 일정), 24시간 자동 재수집 시작 시 agents 파이프라인 재실행 주기는 어떻게 되는지
- **`UI/UX` → `develop` PR 생성** (09-24/25 커밋 4개, 원격엔 이미 push됨)
- **데이터 담당 팀에 `youtube_video` 테이블 `description`/`tags` 컬럼 추가 제안**(§23) — 지금은 로컬 재수집으로 우회 중
- **forecast 브랜치 완료 대기** — 끝나야 거제 briefing이 완전한 실측(`_mock:false`)이 되고, 영월 briefing도 그때부터 생성 가능해짐(§26)
