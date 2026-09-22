# MySQL 실데이터 연동 계획 (tour_earlywarning DB)

> 2026-09-20 작성

## Context

지금까지 `web/`의 9개 데이터 계약(`data/schema/*.json`)은 전부 정적 mock JSON(`data/mock/*.json`)으로 구현돼 있었다. 이번에 실제로 데이터가 적재된 MySQL 서버(`tour_earlywarning`, 관리자는 별도 팀원)에 연결이 확인됐고, DB 관리자로부터 테이블 구조 설명도 받았다. 목표는 이 실데이터로 최소 일부 화면(우선 `signal_status`, 잠재적으로 `content_type`)을 mock에서 실측으로 전환하는 것.

접속 검증 완료 사항 (이미 실행함, 코드 변경 아님):
- 서버는 `SSL Required` 계정이라, `mysql2`로 연결 시 `ssl: { rejectUnauthorized: false }` 옵션이 반드시 필요함 (없으면 IP/자격증명이 맞아도 `ER_ACCESS_DENIED_ERROR`가 남 — 실제로 이 문제로 한참 헤맸음).
- `mysql2` 패키지는 `web/package.json`에 이미 설치됨.
- `web/.env`에 `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` 값이 이미 채워져 있고 접속 확인됨. `MYSQL_SSL=true` 플래그를 추가하고 코드에서 이 값을 읽게 만들 예정.
- 직접 `information_schema.COLUMNS` 조회 + 관리자 설명을 종합해 43개 테이블/뷰의 구조를 파악함.

## 관리자 설명 vs 직접 조회 결과 비교

관리자가 "주요 분석 테이블"로 짚어준 건 `dim_region`, `fact_signal`, `youtube_video`, `datalab_monthly_panel` 4개 + 보조 테이블(`region_alias`, `source_file`, `stg_region_master/scope`, `event`, `event_point`, `crawl_run`, `crawl_checkpoint`, `raw_payload`)이다. 실제 DB에는 이 외에도 **이상탐지/근거수집 파이프라인 전체가 별도로 존재한다** — `anomaly_detection_config`(+`_v2`), `anomaly_candidate_snapshot_v3`, `vw_anomaly_analysis_explained/ready/unresolved`, `vw_anomaly_candidate_context`, `vw_anomaly_episode_*`, `vw_daily_anomaly_candidates/features/scored`, `event_evidence_*`, `analysis_calendar`, `special_calendar_day` 등 약 20개. 관리자 설명에는 이 그룹이 전혀 언급되지 않았다.

이 뷰들은 이미 `naver_z`, `visitor_z`, `anomaly_score`, `is_viral_candidate`, threshold 값(`naver_z_threshold` 등)까지 계산되어 있어서 — 내용상 우리 `signal_status` 계약의 `alert_level`/교차검증 개념과 거의 그대로 맞아떨어진다. 확인 결과 이 값들은 실제 적재된 `fact_signal` 데이터를 기반으로 계산된 것이 맞으므로(관리자가 단순히 설명에서 빠뜨린 것으로 판단), **재사용하기로 결정**했다 — 읽기 전용 조회이므로 브랜치/팀 경계를 침범하지 않는다.

그 외 작은 차이점: `fact_signal`에 관리자가 언급 안 한 `source_region_id`(varchar(20), MUL) 컬럼이 실제로 존재하나, 확인 결과 236만 건 전부 `region_id`와 동일(`diff 0`)이라 실무적으로는 무시하고 `region_id`만 쓰면 된다.

## 9개 데이터 계약과의 매핑

| 계약 | DB 대응 여부 | 비고 |
|---|---|---|
| `signal_status` | 가능 | `vw_daily_anomaly_scored` 하나로 원값+판정 다 해결 (아래 참고) |
| `content_type` | 부분 가능 | `youtube_video`(6개 지역, 6,338건 원본 메타데이터만 있음). "핫존/데드존" 같은 우리 분류 라벨은 DB에 없음 → 우리가 직접 분류 로직을 얹어야 함 |
| `forecast` | 불가 | 대응 테이블 없음, mock 유지 |
| `visitor_profile` | 불가 | 대응 테이블 없음, mock 유지 (단 `fact_signal`/`vw_daily_core_signal`의 local/external/foreign 구성비는 아주 거친 수준으로 제공) |
| `hotspots` | 불가 | 대응 테이블 없음, mock 유지 |
| `checklist` / `precedent` / `before_after` / `timeline` | 불가 | 대응 테이블 없음(`event`/`event_point`도 현재 비어 있음), mock 유지 |

## 지역 매핑 확인 결과

- `youtube_video`에 데이터가 있는 6개 지역: 거제시(`48310`), 여수시(`12130`), 울릉군(`47940`), 속초시(`51210`), 영월군(`51750`), 인제군(`51810`).
- `dim_region`에 거제시=`48310`, 충주시=`43130` 둘 다 존재.
- `fact_signal.region_id`와 `source_region_id`는 현재 전부 동일 — 구분 불필요.
- **결론: 거제(`geoje` → DB `region_id='48310'`)가 `signal_status`와 `content_type` 둘 다 실데이터 전환 가능한 유일한 지역.** 충주는 원래 기획상 "스키마 독립적 참고 사례"라 실데이터 전환 대상이 아니었던 지역과 일치하므로 그대로 mock 유지.
- **지역 우선순위: 거제부터 시작.**

## `vw_daily_anomaly_scored`로 단순화 (D-05 기준)

**중요한 정정**: 처음엔 `anomaly_candidate_snapshot_v3`가 "지역별 현재 상태 1행"이라고 가정했는데, 실제로 조회해보니 **틀렸다.** 이 테이블은 "임계 초과한 날만" 골라 담은 과거 이벤트 로그다 (거제 3년치 중 딱 40일만 존재, 최근 항목이 2026-07-01). 매일 빠짐없이 기록되는 게 아니라서, 여기서 "최신 행"을 뽑으면 훨씬 예전의 스파이크가 "현재 상태"인 것처럼 잘못 표시된다.

대신 `vw_daily_anomaly_scored`(지역×전체 날짜, 301,416행)를 쓴다 — 이 뷰 하나에 원값과 판정이 전부 들어있다:
- 원값: `naver_interest`, `visitors_external/local/foreign`, `youtube_sample_videos/views`
- 판정: `naver_z`, `visitor_z`, `is_interest_spike_current`, `is_demand_spike_current`, `is_viral_candidate`, `anomaly_score`, `naver_z_threshold`, `visitor_z_threshold`

실제로 거제 최신 날짜(2026-08-13, DB 적재 데이터의 최신 시점)를 조회해보면 세 플래그 전부 0(평상시)이었다 — `anomaly_candidate_snapshot_v3`의 "최근 후보일 2026-07-01"과는 다른, 올바른 "현재" 값이다.

`docs/설계결정.md` D-05 — 경보 등급은 "3개 신호 중 몇 개가 임계 초과했는가"로 정의돼 있다:

| 전이 | 조건 |
|---|---|
| 관심 → 주의 | 3개 신호 중 1개 초과 |
| 주의 → 경계 | 3개 신호 중 2개 초과 |
| 경계 → 심각 | 3개 신호 중 3개 초과 또는 혼잡도 단계 5 실측 |
| 하향 | 2회 연속 관측에서 미달일 때만 1단계 내림 (깜빡임 방지) |

`is_interest_spike_current`/`is_demand_spike_current`/`is_viral_candidate` 3개 불리언이 정확히 이 "3개 신호"다 ("혼잡도 단계 5 실측" OR 조건은 DB에 대응 데이터가 없어 제외).

**단순화된 설계**: `vw_daily_anomaly_scored`에서 region_id로 최근 N일(예: 90일)을 한 번에 조회 →
- 가장 최근 날짜 1행 → 3개 불리언 true 개수 → D-05 표로 `alert_level` 산출, `naver_z`/`visitor_z`/`anomaly_score`/원값은 판정 근거로 노출.
- 나머지 과거 행들 → D-05 "하향 2회 연속 미달" 판단 + `TrendChart`용 추이 데이터.

별도로 `vw_daily_core_signal`이나 `anomaly_candidate_snapshot_v3`/`vw_daily_anomaly_candidates`를 조회할 필요가 없다 — 뷰 하나로 끝난다.

**데이터 최신성 주의**: DB에 적재된 데이터의 최신일이 2026-08-13인데, 오늘(구현 시점)은 2026-09-20이다 — **5주 이상 차이가 난다.** 이건 접속/코드 문제가 아니라 원본 수집 주기 문제로 보인다. 화면에 "현재 상태"라고 표시할 때 실제로는 "8/13 기준"이라는 걸 `caveat`/`period`에 명시해야 하고, 이 수집 주기(며칠에 한 번 갱신되는지)는 관리자에게 확인이 필요하다.

## 구현 방향

1. **`web/api/_lib/db.js` 신규**: `mysql2/promise` 커넥션 풀 모듈. `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE/SSL` 환경변수 사용, `ssl: process.env.MYSQL_SSL === "true" ? { rejectUnauthorized: false } : undefined`. 서버리스 특성상 모듈 스코프에 풀을 한 번만 생성해 재사용.
2. **새 서버리스 엔드포인트**: `loadData.js`는 정적 JSON을 `fetch`하는 구조라 DB 조회를 직접 못 함 → `web/api/signal-status.js` 라우트 신규, region을 쿼리 파라미터로 받아 DB 조회 결과를 기존 envelope 포맷(`{_mock:false, source, period, caveat, data}`)으로 변환해 반환.
3. **어댑터 함수**: `web/api/_lib/adapters/signalStatus.js` — `vw_daily_anomaly_scored`에서 region_id로 최근 N일 조회 후 위 "단순화된 설계"대로 envelope 생성.
4. **매니페스트 갱신**: `web/src/data/manifest.js`/`web/api/_lib/dataManifest.js`에 거제의 `signal_status` 항목을 `kind: "db"`(또는 기존 `"real"`)로 전환. region 키(`geoje`) ↔ DB `region_id`(`48310`) 매핑 상수 추가.
5. **env/문서**: `web/.env.example`에 `MYSQL_SSL=true` 안내 추가, Vercel 프로젝트 환경변수에도 `MYSQL_*` 전체(SSL 포함) 등록 필요함을 안내.
6. **임시 파일 정리**: 조사용으로 만든 `web/_inspect_schema_local.mjs`는 구현 착수 시 삭제.

## 남은 확인 사항 (구현 중 조사)

- 원본 데이터 수집/적재 주기 — 최신일이 2026-08-13으로 오늘 대비 5주 이상 뒤처져 있음. 관리자에게 갱신 주기 확인 필요 (화면에 "OO일 기준" 문구를 정확히 넣기 위함).

## 검증 방법

- 로컬에서 `vercel dev`로 새 API 라우트 호출 → 응답이 `data/schema/signal_status.schema.json`을 만족하는지 확인.
- 응답의 `_mock`이 `false`, `source`에 `tour_earlywarning.fact_signal`(또는 사용한 뷰 이름) 명시되는지 확인.
- 화면(AREA0/AREA1)에서 거제 선택 시 배지가 "실측"으로 바뀌는지 확인.
- 기존 mock 전용 지역(충주 등)은 그대로 동작하는지 회귀 확인.
