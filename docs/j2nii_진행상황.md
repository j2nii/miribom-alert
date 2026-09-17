# 진행 상황 (j2nii · 프론트엔드)

> 최종 갱신: **2026-09-17(목)** · 작성 담당: 역할3(프론트엔드) — j2nii
> 관련 문서: `docs/진행상황.md`(전체 프로젝트), `docs/설계결정.md`(D-01~D-13), `docs/meeting-notes/UI/`(자연어 질의 인터페이스 조사·계획)

---

## 한 줄 요약

**`web/`에 실제 Vite+React 앱을 새로 세우고, 9종 스키마(mock+prod)를 실제로 읽어 그리는 AREA 0~4 화면을 전부 완성했다. AI 정책 초안 도우미는 서버리스 함수로 LLM(Upstage Solar)을 호출하도록 복원했고, 이번에 AREA 0에 자연어 질의 채팅(실제 tool-calling + 스트리밍)을 새로 추가했다. agents 브랜치가 안내한 `signal_status`/`checklist`/`timeline` 스키마 변경 중 화면이 깨지는 부분(Tier 1)은 반영 완료. 커밋은 `UI/UX` 브랜치에 전부 푸시됐고, `develop`으로의 PR 본문 초안도 준비됨.**

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

## 확인된 사실 — 목업 수치의 성격

`scripts/gen_mock.py`를 직접 확인한 결과: `signal_status.json`의 `congestion_level`/`density`는 계산 로직이 아니라 **사람이 손으로 넣은 고정값**이다. 반면 `forecast`의 일별 방문객, `hotspots`의 방문객 수는 실제 공식(계절성+주말가중+노이즈, 순위감쇠+노이즈)으로 계산된다.

---

## 알려진 이슈 · 한계

| # | 이슈 | 상태 |
| --- | --- | --- |
| ① | 로컬에서 `/api/*` 서버리스 함수 테스트 | **해결** — `web/dev-server.mjs` + Vite 프록시로 `vercel dev` 없이도 로컬에서 전체 기능(스트리밍 포함) 확인 가능 |
| ② | `vercel dev` 자체는 이 환경에서 yarn 미설치·npm 레지스트리 오류로 계속 실패 | 미해결이지만 ①의 대체 서버로 실사용에는 지장 없음. 근본 해결하려면 로컬에 yarn 설치 또는 Vercel 프로젝트 Install Command를 npm으로 override(대시보드 작업) 필요 |
| ③ | Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY`/`YOUTUBE_API_KEY`가 등록 안 돼 있는 것을 확인함 (로컬 `.env`에만 존재) | **미해결** — 배포된 URL에서는 AI 브리핑·채팅이 지금 이 이유로 계속 실패 중일 가능성이 높음. 대시보드 접근 권한자가 등록해야 함 |
| ④ | AREA 2 "SNS 언급량"/"실제 검색 장소" 탭 근사치 대체 | 데이터 계약에 지점별 검색 세분화 파일 아직 없음 |
| ⑤ | agents 브랜치 스키마 변경 Tier 2/3 | 위 §12 참고 — 화면이 깨지진 않지만 새 데이터(지역별 파일, 이력, 대기 상태 등)를 아직 못 보여줌 |
| ⑥ | 경주(MVP 2번째 후보 지역) 미지원 | `manifest.js`에 거제·충주만 있음 |
| ⑦ | ~~오늘 작업이 커밋·푸시 안 됨~~ | **해결** — `UI/UX` 브랜치 전부 `origin/UI/UX`에 푸시됨 |

---

## 남은 작업

| 순서 | 작업 | 상태 |
| --- | --- | --- |
| 1 | Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY`/`YOUTUBE_API_KEY` 등록 | **미확인 — 최우선.** 대시보드 접근 권한자 필요 |
| 2 | `develop`으로 PR 생성 | 본문 초안 완료, 실제 생성은 대기 중 |
| 3 | agents 브랜치 develop 병합 후 실데이터로 AREA 0/1/3/4 재확인 | 대기 (Tier 1만 선반영된 상태) |
| 4 | Tier 2 반영 (지역 5곳 추가, `signal_status.history` 추이 그래프, checklist 신규 필드 등) | 미착수 |
| 5 | Tier 3 — 브리핑 아키텍처(`web/api/briefing.js` vs `data/prod/briefing.json`) 팀 논의 | 미착수 |
| 6 | 공공데이터포털(data.go.kr) API 키 신청 | 미착수 |
| 7 | 경주 지역 지원 추가 | 미착수 |
| 8 | 실 화면 클릭스루 QA (배포 URL, 브라우저 직접) | 미확인 — 3번 항목과 함께 확인 권장 |

---

## 산출물 위치

```
web/
  package.json, vite.config.js, index.html, .env.example, dev-server.mjs   ← dev-server.mjs 09-17 신규
  api/
    briefing.js                ← AI 정책 초안 도우미 (Upstage Solar 서버리스 함수)
    query.js                   ← 09-17 신규: 자연어 질의 인터페이스 (tool-calling + 스트리밍)
    _lib/
      dataManifest.js          ← 09-17 신규: manifest.js의 서버 전용 복제본
  src/
    main.jsx, App.jsx, index.css
    data/
      loadData.js, manifest.js
    hooks/
      useRegionData.js
    lib/
      briefingTemplate.js       ← 규칙 기반 폴백 생성기
      format.js
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

data/mock/chungju_signal_status.json, chungju_content_type.json   ← 충주 참고 사례
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
```

---

## 사용자가 직접 해야 하는 항목 (Claude Code가 대신할 수 없음)

- ~~Vercel 계정 생성 및 배포~~ — **완료**
- ~~YouTube Data API v3 키 발급~~ — **완료**
- **Vercel 프로젝트 Environment Variables에 `UPSTAGE_API_KEY`/`YOUTUBE_API_KEY` 등록** — 최우선. 미등록 시 배포본에서 AI 브리핑·채팅 모두 실패
- **`develop`으로 PR 생성** — 본문 초안은 준비됨
- **agents 브랜치 PR과의 조율** — Tier 2/3 반영 시점, 공동 스키마 확정 논의
- **공공데이터포털 API 키 발급** — data.go.kr 로그인 필요
- **배포 URL 공유 + 실제 브라우저로 5개 화면 클릭스루 확인**
