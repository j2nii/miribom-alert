# MySQL 실데이터 연동 계획 (tour_earlywarning DB)

> 2026-09-20 작성 · 2026-09-23 갱신(공식 사용설명서 대조, 메인 사례 변경, 성능 문제로 아키텍처 변경) · 2026-09-23 최종 수정(아래 참고)

## [최종 결론] 이 문서의 라이브 API/생성 스크립트 방식은 폐기됨 — `agents/` 파이프라인 결과물 사용으로 전환

이 문서 본문(아래)은 `web/api/signal-status.js`(라이브 API, 성능 문제로 폐기) → `web/scripts/generate-signal-status.mjs`(1회 생성 스크립트)로 이어진 조사·구현 과정을 그대로 남겨둔 것이다. **최종적으로는 이 스크립트도 폐기했다** — `data/prod/`를 확인해보니 `agents/judge_signal_status.py`(월 단위 관심·의도·실현 3중 교차검증, D-05/D-12/D-13 규칙 그대로 구현, `history` 포함)와 `agents/agent1_timeline.py`가 **이미 영월(`signal_status_51750.json`)·거제(`signal_status.json`) 실측 산출물을 만들어둔 상태**였다. 우리 스크립트(일별 네이버 검색 z-score 기반, 관심·의도·실현 정의와 안 맞음, history 없음)와 역할이 완전히 겹치면서 오히려 프로젝트의 실제 판정 기준과는 덜 맞았기 때문에, **`web/api/_lib/db.js`/`referenceDate.js`/`web/scripts/generate-signal-status.mjs`와 우리가 만든 두 JSON 파일을 전부 삭제**하고 `web/src/data/manifest.js`/`dataManifest.js`가 `agents/` 산출물(`/prod/signal_status.json`, `/prod/signal_status_51750.json`, `/prod/timeline.json`, `/prod/timeline_51750.json`, `/prod/checklist.json`)을 직접 가리키도록 되돌렸다.

**교훈**: `data/prod/`에 이미 뭐가 있는지 먼저 확인하고 시작했어야 했다 — MySQL에 직접 연결하는 게 가능하다고 해서 그게 이 프로젝트의 "정본 생성 경로"라는 뜻은 아니었다. `agents/` 폴더가 이미 DB→JSON 변환을 전담하는 공식 파이프라인이었다.

MySQL 접속 정보(SSL 필수 등)와 DB 구조 조사 내용(§ 이하) 자체는 여전히 유효한 조사 기록이라 남겨둔다.

---

## Context

`web/`의 9개 데이터 계약(`data/schema/*.json`)은 전부 정적 mock JSON(`data/mock/*.json`)으로 구현돼 있었다. 실제로 데이터가 적재된 MySQL 서버(`tour_earlywarning`)에 연결이 확인됐고, 분석팀의 공식 사용설명서(`docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf`, 데이터 동결 2026-09-22)도 확보했다. 목표는 이 실데이터로 `signal_status` 화면을 mock에서 실측으로 전환하는 것 — 이번 라운드는 `signal_status`만, 나머지 8개 계약은 다음 이터레이션.

## 접속 정보

- Host `103.218.161.72:3306`, DB `tour_earlywarning`, **SSL 필수(Require)** — `mysql2` 연결 시 `ssl: { rejectUnauthorized: false }` 없으면 자격증명이 맞아도 `ER_ACCESS_DENIED_ERROR`가 난다(비밀번호 문제로 착각하기 쉬우니 주의).
- 팀 계정은 `SELECT`/`SHOW VIEW` 권한만 있다(원본 적재·수집은 동결, 읽기 전용).
- `web/.env`에 `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE/SSL=true` 설정, `web/api/_lib/db.js`가 커넥션 풀을 관리한다.

## 데이터 동결과 가상 기준시점

PDF §11: "2026년 후반 값은 프로젝트 기준 시점보다 미래 날짜를 포함할 수 있다" — 이건 수집 지연이 아니라 **공모전용으로 의도된 동결**이다. 화면의 "오늘/현재"는 실제 벽시계 시각이 아니라 **고정된 가상 기준시점(`2026-08-14`)**을 쓴다 — `web/api/_lib/referenceDate.js`의 `REFERENCE_DATE` 상수.

> 팀 계획상 **5일 뒤(대략 2026-09-28) 부터 24시간 주기로 데이터가 재수집될 예정**이다. 그때는 `REFERENCE_DATE`를 하드코딩 상수 대신 `SELECT MAX(observed_date) FROM vw_daily_core_signal`로 동적 조회하도록 바꾸고, 아래 생성 스크립트를 매일 실행하는 스케줄러(GitHub Actions 등)를 얹으면 된다 — 스크립트 자체나 프론트 코드는 손댈 필요 없음(자세한 내용은 "향후 24시간 자동 재수집 대응" 절 참고).

## 메인 사례: 영월(대비 사례: 거제)

PDF §13 "팀 작업 권장 순서"의 마지막 항목("영월 주 사례와 거제 대비 사례 시각화")과 일치하는 방향으로, **영월을 메인 실데이터 사례, 거제를 대비 사례**로 확정했다 — 거제는 총량(유튜브 조회수 7.45억, 영월 대비 훨씬 큼)은 크지만, 영월은 신호 자체는 뜨되 총량은 작은 사례로 대비시킨다.

- 영월군 `region_id = 51750`, 거제시 `region_id = 48310` (둘 다 `dim_region`/`youtube_video`에 실데이터 존재 확인).
- `fact_signal.region_id`와 `source_region_id`는 현재 전부 동일 — 구분 불필요.
- 이번 라운드는 두 지역 다 `signal_status`만 실데이터로 전환. 나머지 8개 계약은 지역명이 "거제"로 하드코딩된 기존 목업을 그대로 재사용하면 화면 지역명이 어긋나므로, 영월은 `chungju`와 같은 방식으로 "unsupported"(파일 없음) 처리했다.

## `signal_status` 매핑: `vw_daily_anomaly_scored`

`docs/설계결정.md` D-05 — 경보 등급은 "3개 독립 신호 중 몇 개가 임계 초과했는가"로 정의된다:

| 전이 | 조건 |
|---|---|
| 관심 → 주의 | 3개 신호 중 1개 초과 |
| 주의 → 경계 | 3개 신호 중 2개 초과 |
| 경계 → 심각 | 3개 신호 중 3개 초과 또는 혼잡도 단계 5 실측 |
| 하향 | 2회 연속 관측에서 미달일 때만 1단계 내림 (깜빡임 방지) |

`vw_daily_anomaly_scored`의 `is_interest_spike_current`/`is_demand_spike_current`/`is_viral_candidate` 3개 불리언이 정확히 이 "3개 신호"에 대응한다("혼잡도 단계 5 실측" OR 조건은 실측 센서 데이터가 없어 제외). 이 뷰 하나에 원값(`naver_interest`, `visitors_external/local/foreign`)과 판정(z-score, threshold, 플래그)이 전부 들어있어, 최근 90일을 한 번에 조회해 최신 1행으로 등급을 산출하고 나머지로 하향 판단·트렌드를 구성한다.

**주의**: `anomaly_candidate_snapshot_v3`/`vw_daily_anomaly_candidates`는 "임계 초과한 날만" 골라 담은 과거 이벤트 로그이지 "현재 상태"가 아니다 (거제 3년치 중 40일만 존재, 최근 항목이 2026-07-01). 여기서 최신 행을 뽑으면 훨씬 예전 스파이크가 현재 상태처럼 잘못 표시된다 — 반드시 지역×전체 날짜가 다 있는 `vw_daily_anomaly_scored`를 써야 한다.

## 아키텍처 변경: 라이브 API 대신 1회 생성한 정적 파일

**처음 계획은 `web/api/signal-status.js` 서버리스 함수가 요청마다 DB를 조회하는 방식이었으나, 실제로 구현하며 성능 문제를 발견해 폐기했다.**

`vw_daily_anomaly_scored`는 지역 하나로 필터링해도 **180초 이상** 걸린다(반면 `vw_daily_core_signal`은 244ms, `fact_signal`은 67ms로 정상 — 이 뷰만 유독 느리다. 아마 지역 필터를 걸기 전에 228개 지역×3년치 전체에 대해 윈도우 함수 기반 baseline/z-score를 다 계산한 뒤 걸러내는 구조로 추정). 이건 Vercel 서버리스 함수의 실행 제한 시간을 훌쩍 넘겨 배포 즉시 타임아웃이 나는 수준이다.

DB가 동결되어 값이 바뀌지 않으므로, 요청마다 조회할 필요가 없다는 점에 착안해 **1회 추출 → 정적 JSON 커밋** 방식으로 바꿨다:

- `web/scripts/generate-signal-status.mjs` — 영월/거제 각각에 대해 `vw_daily_anomaly_scored`를 조회(느려도 배치 스크립트라 상관없음, 실제로 영월 162초·거제 132초 걸렸다)해 envelope을 만들고 `data/prod/{region}_signal_status.json`으로 저장.
- `web/src/data/manifest.js`/`web/api/_lib/dataManifest.js`가 이 파일을 `kind: "real"`로 가리킴 — agent②의 `content_type.json`과 완전히 같은 패턴(정적 실측 파일).
- `loadData.js`/컴포넌트 쪽은 아무 변경도 필요 없다 — DB 조회든 정적 파일이든 URL 하나 fetch하는 건 동일하기 때문.

생성된 결과: 영월·거제 둘 다 기준일(2026-08-14) 기준 `alert_level: "관심"`(3개 신호 모두 미달, 평상시 상태).

## 향후 24시간 자동 재수집 대응 (5일 뒤 예정)

수정 비용은 낮은 편이다. 지금 구조가 이미 자동화에 유리하게 짜여 있다 — 이유는:

- DB 조회 로직이 라이브 API가 아니라 독립된 스크립트(`generate-signal-status.mjs`)로 분리돼 있다. 나중에 자동화한다는 건 "이 스크립트를 사람이 손으로 한 번 돌리는 대신 스케줄러가 대신 돌리게" 하는 것뿐이라, 스크립트 자체는 손댈 필요가 거의 없다.
- 결과물(`data/prod/*_signal_status.json`)의 모양과 그걸 읽는 쪽(`manifest.js`)은 수동 생성이든 자동 생성이든 완전히 동일하다. 프론트/매니페스트 코드는 나중에 하나도 안 건드린다.

실제로 바꿔야 할 건 딱 두 가지뿐이다:

1. `REFERENCE_DATE` 하드코딩(`"2026-08-14"`) → `SELECT MAX(observed_date) FROM vw_daily_core_signal`로 매번 동적으로 구하는 방식 — 파일 하나, 몇 줄 수정.
2. 이 스크립트를 매일 실행해주는 트리거 하나 추가 — GitHub Actions 같은 곳에 "하루 한 번 이 스크립트 실행 → 결과 JSON 커밋/배포" 워크플로 파일 하나만 새로 얹으면 된다. 기존 코드를 고치는 게 아니라 위에 얹는 것.

즉 지금처럼 정적 파일로 마무리해도 나중에 "새로 짜야 하는" 부분은 없고, "지금 안 만든 자동화 트리거만 나중에 추가"하는 정도라 이 순서(지금 정적 → 나중에 자동화)가 합리적이다. 5일 뒤로 예정돼 있다면 그때 가서 위 두 가지만 처리하면 된다.

`vw_daily_anomaly_scored`가 여전히 느린 문제는 매일 도는 배치라면 몇 분 정도는 괜찮지만, 데이터가 계속 쌓이면 더 느려질 수 있어 분석팀에 성능 이슈로 공유해두면 좋다.

## 남은 확인 사항

- `youtube_video` 실데이터가 있는 6개 지역(거제·여수·울릉·속초·영월·인제) 중 영월/거제 조합은 확정. `content_type`을 다음 라운드에서 실데이터로 전환할 때 이 목록을 그대로 활용 가능.
- PDF가 새로 소개한 `vw_final_anomaly_analysis`(에피소드 단위 450건, 축제·날씨·근거 연결)는 `precedent`/`timeline` 계약의 "콘텐츠 확산→방문 급증" 앞 2단계만 실데이터화가 가능하나, 두 계약의 핵심인 "실제 조치"와 "효과"는 이 DB에 없는 데이터라 이번 라운드에서는 보류(mock 유지)하기로 결정함.

## 검증 방법 (최종 — agents/ 산출물 기준)

- `data/prod/signal_status.json`(거제)/`signal_status_51750.json`(영월)/`timeline.json`(거제)/`timeline_51750.json`(영월)이 각각의 스키마를 만족하는지 확인(이미 agents/ 스크립트가 생성한 상태 — 재검증만).
- 화면(AREA0/AREA1)에서 영월/거제 선택 시 signal_status·timeline 배지가 "실측"으로 바뀌는지 확인. `checklist`는 agent3 산출물(`/prod/checklist.json`)을 쓰지만 그 안의 `_mock`이 여전히 true라 배지는 "샘플"로 뜨는 게 정상(§checklist 참고).
- 기존 mock 전용 지역(충주)과 나머지 계약(forecast/visitor_profile/hotspots/precedent/before_after)은 그대로 동작하는지 회귀 확인.
- `naver_interest`류 상대지수를 절대값처럼 표현하지 않는지는 이제 agents/ 판정 로직(관심/의도/실현, %p·배 단위)의 책임 — 우리 쪽 표현 규칙은 더 이상 적용 안 됨.

## 24시간 자동 재수집 관련 — 책임 주체 변경

위 "향후 24시간 자동 재수집 대응" 절은 우리가 만든(현재는 삭제된) `generate-signal-status.mjs` 기준으로 쓴 것이라 더 이상 그대로 적용되지 않는다. 실제로 매일 재실행이 필요해질 대상은 `agents/judge_signal_status.py`(및 `agent1_timeline.py` 등 나머지 파이프라인)이며, 이건 우리(프론트)가 아니라 해당 스크립트 담당자의 자동화 범위다. 다만 "REFERENCE_DATE를 동적으로 구해야 한다"는 원칙 자체는 여전히 유효하다 — `judge_signal_status.py` 쪽에도 비슷한 하드코딩이 있다면 같이 확인이 필요하다.
