# `refactor/agents_db-full연동` 브랜치 작업 계획

## Context

지난 세션에서 9개 데이터 계약 중 무엇이 실측이고 무엇이 목업인지, 목업인 것 중 DB에 실제 소스가 있는지를 전수 조사했다. 결과: `signal_status`/`content_type`/`timeline`은 이미 실측, `hotspots`/`visitor_profile`은 DB에 소스가 있는데 변환 스크립트가 없어서 목업, `checklist`/`briefing`은 그 둘에 의존해서 목업, `forecast`는 재료만 있고 모델이 없음(별도 브랜치 진행 중, 이번 범위 제외), `precedent`/`before_after`는 이 DB로는 원천적으로 불가능(정부 조치 기록 자체가 없음).

**이번 브랜치 범위(사용자 확정)**: `agents/` 폴더의 데이터 생성까지만. `forecast`(시계열 모델링, 별도 브랜치 진행 중)와 `web/` 쪽 매니페스트 연동은 제외 — 산출물(`data/prod/*.json`)이 생기는 데까지가 목표.

## 기존 아키텍처 확인 (반드시 따라야 하는 기존 패턴)

- `collection/db_export.py`가 유일하게 실제 MySQL에 접속하는 스크립트다. 조회 전용 계정으로 `data/raw/db/*.csv`에 스냅샷을 내려받고 `manifest.json`(추출 시각·행 수)을 남긴다. "매번 DB를 안 치는 이유"가 문서화돼 있음(적재가 계속 갱신 중이라 재현성을 위해 스냅샷 고정).
- 각 agent 스크립트(`judge_signal_status.py`, `agent1_timeline.py`)는 **이 CSV 스냅샷만 읽는다** — 라이브 DB 쿼리 아님.
- 지역 루프 패턴이 이미 확립돼 있음: `CASE_REGIONS = ["48310","12130","47940","51210","51750","51810"]`(거제·여수·울릉·속초·영월·인제, 유튜브 적재된 6개 지역), `DEFAULT_REGION = "48310"`, 파일명은 `{name}.json`(기본 지역) / `{name}_{region}.json`(나머지). **새로 만드는 것도 전부 이 패턴을 그대로 따른다.**
- `agents/common.py`의 `load_input(name)`은 `data/prod/{name}.json`이 있으면 그걸, 없으면 `data/mock/{name}.json`을 읽는다(지역 구분 없음 — 현재 `agent3_match.py`/`agent5_briefing.py`가 단일 지역(거제)만 처리하는 이유). **이 로더는 건드리지 않는다** — hotspots/visitor_profile 파일만 생기면 자동으로 실측을 읽게 된다.

## 작업 1: `collection/db_export.py`에 쿼리 2개 추가

현재 `QUERIES`에 `major_attraction_visitors_monthly`, `datalab_detail_row`가 없다(확인함). 추가한다:
- `major_attraction_visitors_monthly` — 관광지 단위 방문자 수(4,159개 관광지). `CASE_REGIONS` 지역으로 필터링해서 내려받는다(전체는 847,656행이라 전량은 불필요). `attraction_region_map` 조인이 필요할 수 있음(지역 매핑 확인).
- `datalab_detail_row` — `data_group` 5종만 필터링해서 내려받는다: `'방문자 성연령별 분포'`, `'거리별 방문자 분포'`, `'방문자 거주지 분포'`, `'관광소비_내국인'`/`'관광소비_외국인'`/`'관광소비 추이_...'` 계열, `'동반유형 키워드'`/`'동반유형 언급량'`. 전체(283만 행)가 아니라 `data_group IN (...)` + `CASE_REGIONS`로 좁혀서 받는다. `row_json`은 JSON 컬럼이라 파이썬 쪽에서 파싱 필요(실제 내부 키 구조는 샘플 몇 건 먼저 찍어보고 확정).

## 작업 2: `agents/agent_hotspots.py` 신규 (`hotspots.json` 생성)

`judge_signal_status.py`/`agent1_timeline.py`와 동일한 구조(CASE_REGIONS 루프, `hotspots.json`/`hotspots_{region}.json` 출력, `data/schema/hotspots.schema.json`으로 검증).

**주의**: `major_attraction_visitors_monthly`에서 `rank`/`poi_name`/`visitors`/`change_rate`는 바로 뽑을 수 있지만, 스키마가 요구하는 `spatial_type`(매뉴얼 p.13 4분류: 네트워크 보행 흐름형/지형·경사 이동·저항 흐름형/실내 공간 가치 체류형/실외 공간 가치 체류형)은 **DB에 없는 값이라 별도 분류가 필요하다** — agent2의 콘텐츠 유형 분류처럼 LLM 판정을 붙이거나, 지역당 상위 POI 수가 적을 것이므로(top 10~20 수준으로 예상) 사람이 채운 소규모 룩업 테이블로 가는 게 더 간단할 수 있다. `coord`/`visitor_mix`/`congestion_level`/`bottleneck`은 스키마상 선택 필드라 DB에 없으면 생략하면 된다(발명 금지 원칙).

## 작업 3: `agents/agent_visitor_profile.py` 신규 (`visitor_profile.json` 생성)

같은 구조. `datalab_detail_row`의 5개 `data_group`을 각각 스키마 필드로 매핑:

| data_group | 스키마 필드 |
|---|---|
| 방문자 성연령별 분포 | `gender_age` |
| 거리별 방문자 분포 | `distance` (DB 구간을 스키마의 4단계로 재매핑 필요 — 예: "190~240km" → "200km 이상") |
| 방문자 거주지 분포 | `residence` |
| 관광소비_* | `spending` |
| 동반유형 키워드/언급량 | `companion` |

`total_visitors`, `local_external_mix`는 이미 실측인 `datalab_monthly_panel`/`fact_signal`에서 채울 수 있는지 확인(별도 조회 불필요할 가능성 있음). `profile_tags`는 D-03 매칭에 쓰이는 요약 태그라 값 분포를 보고 규칙으로 생성(예: 특정 연령대 비중 40% 이상 → "XX대비중높음").

## 작업 4: `agents/agent2_apply.py` 다지역 확장

현재 거제(`48310`) 하드코딩 1곳뿐(확인함). `youtube_case.csv`는 이미 6개 지역 다 있으므로, `judge_signal_status.py` 패턴대로 `CASE_REGIONS` 루프를 추가해 `content_type.json`(거제) + `content_type_{region}.json`(나머지 5개)을 만든다. 분류 프롬프트(`agent2_content_type.md`)는 지역 무관하게 재사용 가능.

## 작업 5: `agent3_match.py`, `agent5_briefing.py` 재실행 (코드 변경 없음)

작업 2·3이 끝나 `data/prod/hotspots.json`, `visitor_profile.json`이 생기면 `agent3_match.py`를 다시 돌리는 것만으로 `checklist.json`이 `_mock:false`가 된다(입력 4개가 전부 실측이 되므로, `common.py`의 자동 판정 로직). `agent5_briefing.py`는 입력에 `forecast`가 포함되는데 이번 범위에서 forecast는 그대로 mock이라 **briefing은 이번 브랜치 완료 후에도 `_mock:true`로 남는 게 정상**이다(forecast 브랜치가 합쳐진 뒤에야 완전한 실측이 됨) — 이 사실을 PR 설명에 명시해서 "왜 아직도 mock이냐"는 오해를 막는다.

## `data/mock/*.json` 처리 방침 — 삭제하지 않고 유지

기존 관례 확인함: `data/mock/signal_status.json`/`timeline.json`/`content_type.json`은 이미 `data/prod/`에 실측 버전이 있는데도 삭제되지 않고 그대로 남아있다. 이유: (1) `common.py`의 `load_input()`이 "prod 없으면 mock" 폴백 구조라 안전장치 역할, (2) `content_type`처럼 `VITE_USE_PROD` 토글로 mock/prod를 일부러 전환하는 용도, (3) 루트 `.gitignore` 주석에 "`data/mock`은 계약(contract)이므로 계속 추적함"이라 명시됨. **이번 브랜치도 동일하게: `data/prod/hotspots.json`/`visitor_profile.json`을 새로 만들어도 `data/mock/hotspots.json`/`visitor_profile.json`은 삭제하지 않고 그대로 둔다.** `checklist.json`도 마찬가지로 `data/mock/checklist.json`(09-12, 3건) 유지.

## 재생성물의 DB 적재(archiving) 여부 — 하지 않는다

이번 브랜치 계획을 다듬는 중에 나온 논의: "매번 재생성되는 prod JSON을 옛 버전 삭제 전에 DB에 적재해서 보관해야 하지 않을까?"라는 질문이 있었으나, 다음 이유로 **하지 않기로 결정**했다.

- `signal_status_51750.json`의 `history[]`(24개월치)처럼, 이 프로젝트에서 추세/히스토리가 필요한 값은 이미 "매번 원천 DB 데이터에서 다시 계산"하는 방식으로 해결돼 있다. 옛 JSON 파일 자체를 보존해야 할 제품상의 이유가 없다 — 한 번 대체된 뒤에는 아무 코드도 그 파일을 다시 읽지 않는다.
- `agents/` 파이프라인은 현재 `collection/db_export.py`를 통해 **읽기 전용**으로만 DB에 접속한다(조회 전용 계정). 여기에 쓰기 경로를 추가하는 것은 이 브랜치의 범위(1회성 생성)를 벗어나는 아키텍처 변경이며, 그 DB는 별도 "데이터 담당" 팀이 관리하는 공유 자원이라 쓰기 권한·스키마 설계를 새로 합의해야 하는 비용이 크다.
- 이번 브랜치는 반복 재생성이 아니라 1회성 생성이 목표이므로 이 문제 자체가 아직 발생하지 않는다.

나중에 실제로 주기적 자동 재생성이 결정되면, DB에 되돌려 쓰기보다 (a) git에서 그냥 덮어쓰기(텍스트 diff는 git이 효율적으로 압축) 또는 (b) 생성물을 git 밖의 별도 캐시/스토리지에 두는 방향을 먼저 검토한다.

## 범위 밖 (명시적 제외)

- `forecast` — 실제 시계열 예측 모델링이 필요한 별개 작업, 다른 브랜치에서 진행 중.
- `precedent`/`before_after` — 이 DB에 "실제 시행한 조치와 효과" 기록 자체가 없어 구조적으로 불가능. 만들려면 완전히 다른 소스(정책 대응 기록을 사람이 수집)가 필요 — 이번 브랜치에서는 손대지 않는다.
- `web/` 쪽 `manifest.js`/`dataManifest.js` 연동 — 산출물이 생긴 뒤 별도 작업/PR로 진행.

## 검증 방법

- 각 신규/재실행 산출물이 `data/schema/{hotspots,visitor_profile,checklist}.schema.json`을 만족하는지(기존 스크립트들처럼 `Draft7Validator`로 자체 검증하는 패턴을 그대로 따른다).
- `_mock` 필드가 기대대로 나오는지: `hotspots`/`visitor_profile`/`content_type`(6개 지역) → `false`, `checklist` → `false`, `briefing` → 여전히 `true`(forecast 대기).
- 숫자를 실제로 아는 사실과 대조 — 예: 거제 유튜브 조회수가 다른 지역보다 훨씬 크다는 건 이미 확인된 사실이므로 hotspots/content_type 결과가 이와 모순되지 않는지 육안 확인.
