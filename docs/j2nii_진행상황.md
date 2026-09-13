# 진행 상황 (j2nii · 프론트엔드)

> 최종 갱신: **2026-09-13(일)** · 작성 담당: 역할3(프론트엔드) — j2nii
> 관련 문서: `docs/진행상황.md`(전체 프로젝트), `docs/설계결정.md`(D-01~D-06)

---

## 한 줄 요약

**`web/`에 실제 Vite+React 앱을 새로 세우고, 9종 스키마(mock+prod)를 실제로 읽어 그리는 AREA 0~4 화면을 전부 완성했다. 레이아웃은 `docs/meeting-notes/tourism-radar-demo.html`의 실제 CSS/그리드를 그대로 재사용했고, AI 정책 초안 도우미는 서버리스 함수로 LLM(Upstage Solar)을 호출하도록 복원했다. 아직 Vercel 배포·YouTube/공공데이터포털 키 발급은 안 됐다.**

---

## 오늘 한 일 (완료)

### 1. `web/` 프로젝트 셋업
- `package.json`/`vite.config.js`/`index.html`/`main.jsx` 신규 — 번들러 없던 빈 폴더에 실제 Vite+React 앱을 처음부터 구축
- `vite.config.js`의 `publicDir`을 리포지토리 루트 `data/`로 지정 — `data/mock/*.json`은 `/mock/*.json`, `data/prod/*.json`은 `/prod/*.json`으로 그대로 서빙됨. 복사 스크립트 없이 `scripts/gen_mock.py` 재실행 결과가 즉시 반영된다
- `npm run build` 통과 확인 완료 (여러 차례 재검증)

### 2. 데이터 로더 (`web/src/data/`)
- `loadData.js` — `loadData(dataType, {region})`: 매니페스트 조회 → `fetch` → 봉투(envelope) 반환. 실패/미지원 시 상태 코드로 구분
- `manifest.js` — `REGION_MANIFEST`: 지역별 데이터 타입 → `{url, kind: "real"|"mock"|"unsupported"}`. 목업→실데이터 전환은 이 파일 한 줄만 바꾸면 됨
- `VITE_USE_PROD` 토글이 실제로 `content_type`(현재 유일하게 mock/prod 둘 다 있는 데이터)에 적용되도록 연결

### 3. AREA 0~4 전 화면 실동작
`docs/진행상황.md`의 화면-JSON 매핑을 그대로 따름:

| 화면 | 구현 내용 |
| --- | --- |
| AREA 0 관제 대시보드 | `signal_status`+`forecast` 기반 경보 배지·게이지, 오늘자 예측 티저. 거제(alert_level 스키마)와 충주(lifecycle 스키마)를 데이터 모양으로 자동 분기 |
| AREA 1 신호 스캔 | 3중 교차검증(확신도 박스로 시각화), 90일 예측 차트, 인기 관광지 랭킹, 방문객 프로파일 |
| AREA 2 콘텐츠·유형 | 4탭(유튜브/SNS 언급량/실제 검색 장소/콘텐츠 유형 요약), `content_type.json`(실데이터) 기반 |
| AREA 3 정책 브리핑 | 체크리스트(phase별 그룹, top5+더보기, 매뉴얼 인용), 선례 카드, AI 정책 초안 도우미 |
| AREA 4 성과 리포트 | 리드타임 타임라인, 조치 전후 KPI 비교(`direction` 기준 개선/악화 판정) |

공통 원칙(`SourceBadge`/`CaveatNote`/`MockBanner`/`ManualRefCite`)을 모든 데이터 블록에 일괄 적용 — "출처 없는 값은 표시되지 않는다"를 화면에서 강제.

### 4. 레이아웃을 참조 데모와 최대한 일치시킴
`docs/meeting-notes/tourism-radar-demo.html`의 실제 CSS를 직접 읽어 그대로 가져왔다:
- `:root` 색상 토큰(`--abyss` #0E1E2E, `--mist`, `--teal`, `--amber`, `--crimson`, `--ink`, `--ink-soft` 등), 폰트(`--font-kr`/`--font-mono`)
- `.app-grid`의 원본 `grid-template-columns: 1.15fr .85fr; grid-template-areas: "scan summary" "briefing briefing"`를 그대로 쓰고, 원본엔 없던 AREA 0/4를 위아래 전체 폭 행으로 확장
- 영역당 패널 1개(원본처럼) — 하위 기능은 패널 내부 `.section-block`으로만 구분
- `panel-eyebrow`/`tab-switch`/`rank-list`/`source-tag-real`/`briefing-item`/`btn-primary` 등 원본 클래스명 재사용
- 지역 선택을 헤더에서 AREA 1(scan) 패널 안으로 이동(원본처럼) — 단 지도 대신 드롭다운
- `panel-scan`/`panel-summary`(원본에서 나란히 있던 두 컬럼)는 고정 높이(82vh)+숨김 스크롤바 적용

### 5. AI 정책 초안 도우미 — 실제 LLM 호출로 복원
- 기존 데모의 브라우저 직접 `api.anthropic.com` 호출(키 없음, 보안 문제)을 제거
- 1차: 규칙 기반 순수 함수 생성기(`web/src/lib/briefingTemplate.js`, D-04 규칙 강제)로 교체
- 2차(요청에 따라): `web/api/briefing.js`(Vercel 서버리스 함수)를 만들어 **서버 사이드에서만** LLM을 호출하도록 복원 — API 키는 절대 브라우저에 노출 안 됨
- 3차(요청에 따라): Claude → **Upstage Solar**로 교체. `openai` 패키지로 Upstage의 OpenAI 호환 엔드포인트(`https://api.upstage.ai/v1`, 모델 `solar-pro4`) 호출 — 사용자가 콘솔에서 직접 복사해 준 코드 스니펫으로 엔드포인트/모델명 확정
- 규칙 기반 생성기는 LLM 호출 실패 시 자동 폴백으로 유지(로컬 `vite dev`에서는 `/api` 함수가 안 뜨므로 항상 폴백 경로를 탐 — `vercel dev` 또는 배포 후에만 실제 LLM 응답)

### 6. 시각화 보강 (참조 데모의 게이지/확신도 박스/임계선 차트 스타일 확장)
- `StageGauge`(공통) — 반원 게이지+바늘. 경보 4단계(관심/주의/경계/심각)와 생애주기 4단계(발화/확산/피크/쇠퇴) 양쪽에 재사용
- `ConfidenceBox`(공통) — "지금 확신할 수 있을까요?" + 확신도 배지(N/M 지표 일치) + 신호별 라인
- `TrendChart`(공통) — 점선 임계선 + 구간별 색 전환 + 마우스오버 툴팁, 라이브러리 없이 SVG
- `LifecyclePanel`(충주 전용) 신규 — **버그 수정**: 기존엔 충주를 선택하면 `alert_level`/`density` 등이 없어 AREA 0이 깨졌음. 이제 발화/확산/피크/쇠퇴 게이지+확신도 박스(신호 1개뿐이라 "0/1 지표 일치"로 의도적으로 낮게 — 3중 교차검증의 필요성을 대비시키는 장치)+전월 대비 %변화 추이 차트+서술형 인사이트로 구현
- `data/mock/chungju_signal_status.json`에 `thresholds`(확산 +12%/쇠퇴 -6%), `confidence` 필드 추가 — 판정 문장이 컴포넌트 하드코딩이 아니라 데이터에서 계산되도록 함

### 7. 충주 데이터 재구성
- `data/mock/chungju_signal_status.json`, `data/mock/chungju_content_type.json` 신규 — 9종 공식 스키마 대상은 아니지만 동일한 봉투(`_mock`/`source`/`period`/`caveat`) 구조를 따름. `REGION_MANIFEST.chungju`에 이 두 데이터 타입만 등록, 나머지는 "데이터 준비 전"으로 자동 표시

---

## 확인된 사실 — 목업 수치의 성격

`scripts/gen_mock.py`를 직접 확인한 결과: `signal_status.json`의 `congestion_level`/`density`는 계산 로직이 아니라 **사람이 손으로 넣은 고정값**이다(스키마 문서의 임계값 표와 일관되게 골랐을 뿐, 그 매핑을 계산하는 코드는 없음). 반면 `forecast`의 일별 방문객, `hotspots`의 방문객 수는 실제 공식(계절성+주말가중+노이즈, 순위감쇠+노이즈)으로 계산된다. 프론트는 두 경우 모두 JSON 값을 그대로 표시할 뿐 자체 계산 로직은 없다.

---

## 알려진 이슈 · 한계

| # | 이슈 | 비고 |
| --- | --- | --- |
| ① | 로컬 `npm run dev`(`vite dev`)만으로는 `/api/briefing`이 뜨지 않음 | Vercel 서버리스 함수는 `vercel dev`로 실행하거나 배포 후에만 테스트 가능. 그 전까진 자동으로 규칙 기반 폴백이 동작(화면은 안 깨짐) |
| ② | AREA 2 "SNS 언급량"/"실제 검색 장소" 탭은 세분화 스키마가 없어 근사치(교차검증 신호, 방문 기준 랭킹)로 대체 | `docs/진행상황.md`의 데이터 계약에 지점별 검색 세분화 파일이 아직 없음 |
| ③ | Upstage `UPSTAGE_API_KEY`가 대화 중 평문으로 한 번 노출된 적 있음 | **사용자에게 콘솔에서 키 재발급을 권고함** — 아직 재발급 확인 안 됨 |
| ④ | Vercel 배포가 아직 한 번도 실행되지 않음 | 계정 연결·환경변수 등록이 사용자 쪽 작업이라 대기 중 |
| ⑤ | `docs/meeting-notes/tourism-radar-demo.html`은 원본 그대로 보존, 수정 안 함 | 회의 시점 스냅샷으로 유지하기로 결정됨 |
| ⑥ | 오늘 작업이 아직 커밋·푸시 안 됨 | `UI/UX` 브랜치가 `origin/UI/UX`보다 10커밋 앞선 상태이고 오늘 만든 파일은 전부 untracked — **사용자 지시로 커밋 보류 중.** 배포 URL이 404인 근본 원인이 이것 |

---

## 남은 작업

| 순서 | 작업 | 상태 |
| --- | --- | --- |
| 1 | Vercel 프로젝트 생성 + 배포 | 프로젝트/URL(`https://tourism-early-warning.vercel.app/`)은 만들어짐, 단 **현재 404** — 원인은 브랜치 병합 문제가 아니라 오늘 작업이 `UI/UX` 브랜치에조차 아직 커밋·푸시가 안 됐기 때문(로컬 10커밋 앞선 상태, 오늘 파일은 전부 untracked). **커밋/푸시는 사용자 지시로 보류 중** |
| 2 | YouTube Data API v3 키 발급 | **완료** (사용자 확인) — 루트 `.env`에 반영 완료(아래 "오늘 추가로 정리한 것" 참고) |
| 3 | Vercel 환경변수에 `UPSTAGE_API_KEY`(+ 필요 시 `UPSTAGE_MODEL`) 등록 | 미확인 — 로컬 `.env`와 별개로 Vercel 대시보드에도 등록해야 배포본에서 실제 LLM이 호출됨 |
| 4 | 공공데이터포털(data.go.kr) API 키 신청 | 미착수 |
| 5 | JSON 스키마 필드 확정 팀 논의 참여 | 미착수 |
| 6 | 실 화면 클릭스루 QA (브라우저로 직접) | 미확인 — 배포 URL 공유 시 함께 점검 |
| 7 | Agent ①(사례 타임라인)·③(매뉴얼 매칭)·④(선례 조사) 백엔드 미구현 | `checklist`/`precedent`/`timeline`은 여전히 mock 파일 |

### 오늘 추가로 정리한 것 (2026-09-13)

- **`web/.env`의 오타 수정**: `UPSTAGE_API` → `UPSTAGE_API_KEY`로 이름을 바로잡았다(`web/api/briefing.js`가 실제로 읽는 변수명과 일치시킴). 이름이 틀리면 로컬/Vercel 어느 쪽이든 조용히 규칙 기반 폴백으로만 동작하고 실제 LLM은 절대 호출되지 않는다 — **Vercel 대시보드에 같은 이름으로 잘못 등록했다면 거기도 `UPSTAGE_API_KEY`로 고쳐야 한다.**
- **루트 `.env` 신규 생성**: `collection/youtube_collect.py`는 `web/.env`가 아니라 **리포지토리 루트의 `.env`**를 읽는다(`ROOT = Path(__file__).resolve().parent.parent`). 발급받은 YouTube 키가 `web/.env`에만 있어서 수집 스크립트가 못 읽는 상태였다 — 루트 `.env`를 새로 만들고 값을 옮겨 넣었다(값은 셸 리다이렉션으로만 복사해 대화창에는 노출하지 않음).

---

## 산출물 위치

```
web/
  package.json, vite.config.js, index.html, .env.example
  api/
    briefing.js              ← AI 정책 초안 도우미 (Upstage Solar 서버리스 함수)
  src/
    main.jsx, App.jsx, index.css
    data/
      loadData.js, manifest.js
    hooks/
      useRegionData.js
    lib/
      briefingTemplate.js     ← 규칙 기반 폴백 생성기
      format.js
    components/
      common/                 ← SourceBadge, CaveatNote, MockBanner, ManualRefCite,
                                 Header, DataState, StageGauge, ConfidenceBox, TrendChart
      area0-dashboard/         ← SignalStatusPanel(거제), LifecyclePanel(충주)
      area1-signal-scan/       ← CrossValidationLights, ForecastChart, HotspotRanking,
                                 VisitorProfileCard
      area2-content/           ← ContentTypeTabs, VideoCard, ContentTypeSummary, ZoneSignalBadge
      area3-briefing/          ← ChecklistPanel, PrecedentCards, BriefingGenerator
      area4-performance/       ← PerformanceReport, LeadTimeTimeline
    pages/
      Area0Dashboard.jsx ~ Area4Performance.jsx

data/mock/chungju_signal_status.json, chungju_content_type.json   ← 신규 (충주 참고 사례)
```

### 실행 명령

```bash
cd web
npm install
npm run dev              # http://localhost:5173, /api 함수는 안 뜸(폴백 동작)
npm run build             # 프로덕션 빌드 검증
```

---

## 사용자가 직접 해야 하는 항목 (Claude Code가 대신할 수 없음)

- ~~Vercel 계정 생성 및 배포~~ — **완료**
- ~~YouTube Data API v3 키 발급~~ — **완료**
- **Upstage API 키 재발급** — 대화 중 평문으로 노출된 키를 콘솔에서 폐기·재발급 (아직 미확인)
- **Vercel 프로젝트 설정 확인** — Root Directory가 `web`으로 되어 있는지, 환경변수에 `UPSTAGE_API_KEY`(오타 아닌 정확한 이름으로)가 등록되어 있는지
- **공공데이터포털 API 키 발급** — data.go.kr 로그인 필요
- **JSON 스키마 확정 논의 참여** — 팀 합의가 필요한 의사결정
- **배포 URL 공유 + 실제 브라우저로 5개 화면 클릭스루 확인**
