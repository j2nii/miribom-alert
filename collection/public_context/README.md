# 최종 데이터 수집 패키지 — 2026-09-22 마감

이 패키지는 관광 바이럴 이상탐지 프로젝트에서 **화요일 2026-09-22 23:59:59
KST까지 가능한 원천 수집을 끝내고 이후 신규 수집을 중단**하기 위한 마지막 실행본입니다.
마감 후에도 기존 데이터의 정제·매핑·분석·내보내기는 계속할 수 있습니다.

## 이번에 추가하는 데이터

| 원천 | 기간 | 저장 테이블 | 분석 목적 |
|---|---:|---|---|
| 한국관광공사 TourAPI 행사·축제 | 2023-01-01~2026-08-31 | `raw_tourapi_festival` | 이상 에피소드 주변 공식 행사 확인 |
| 기상청 ASOS 일자료 | 2023-01-01~2026-08-31 | `raw_kma_asos_daily` | 폭염·강수·기온·강풍 등 외생 요인 통제 |
| 기상청 기상특보 목록 | API가 허용하는 최근 7일만 | `raw_kma_warning` | 실시간 운영용 특보 원천 확인 |
| 네이버 뉴스·블로그·웹문서 | 남은 P1/P2/P3 에피소드 | 기존 `event_evidence_*` | 120건 미수집 및 미해결 근거 보강 |

ASOS는 `asos_stations.csv`에 담긴 전국 주요 관측소 96개를 수집합니다. 관측소 자료는
원천 그대로 저장하며, 228개 분석 지역으로의 최근접 관측소 매핑은 수집 종료 뒤 분석
단계에서 처리합니다. 지금 임의 매핑해 값을 복제하지 않습니다.

## 0. API 활용신청

공공데이터포털에서 아래 3개 API를 각각 활용신청합니다. 기상청 2개는 개발계정
자동승인이고 일 10,000회, TourAPI는 개발계정 자동승인이고 일 1,000회입니다.

1. TourAPI: https://www.data.go.kr/data/15101578/openapi.do
2. ASOS 일자료: https://www.data.go.kr/data/15059093/openapi.do
3. 기상특보: https://www.data.go.kr/data/15000415/openapi.do

승인된 공공데이터포털 **일반 인증키(Decoding)** 하나를 사용할 수 있습니다. API별로
키가 다르면 `.env`의 `TOUR_API_SERVICE_KEY`, `KMA_API_SERVICE_KEY`를 따로 채웁니다.

## 1. 설치와 환경설정

압축을 다음 위치에 풉니다.

```text
C:\Users\han\yaho\final_collection_20260922
```

기존 폴더가 있어도 이 이름의 새 폴더이므로 데이터랩·네이버·이벤트 수집 폴더를
삭제하지 않습니다. 다음을 실행합니다.

```bat
00_setup.cmd
```

Windows에서 `No time zone found with key Asia/Seoul` 오류가 났다면 기존 `.venv`를
삭제하지 말고, 이 수정본으로 덮어쓴 뒤 `00_setup.cmd`를 다시 실행합니다. 설치 파일이
`tzdata`를 먼저 설치하며, 코드에도 UTC+9 대체 처리가 포함되어 있습니다.

생성된 `.env`를 열고 최소 두 값을 바꿉니다.

```text
MYSQL_PASSWORD=실제_yaho_loader_비밀번호
DATA_GO_KR_SERVICE_KEY=공공데이터포털_일반인증키_Decoding
```

따옴표는 넣지 않습니다. 이미 URL 인코딩된 Encoding 키를 넣어도 코드가 한 번
디코딩하지만, 가능하면 Decoding 키를 사용하십시오.

## 2. DB 테이블 생성

```bat
01_create_tables.cmd
```

비밀번호를 별도로 묻지 않습니다. `.env` 값을 사용합니다.

## 3. 공식 원천 수집

한 번에 모두 실행:

```bat
04_collect_all_public.cmd
```

문제가 생긴 원천만 다시 받을 때:

```bat
02_collect_festivals.cmd
03_collect_weather.cmd
04_collect_warnings.cmd
```

`API 오류 99: 데이터요청은 한번에 최대 1,000건`이 표시된 이전 버전은 ASOS의
페이지 크기가 2,000으로 설정된 버전입니다. 수정본은 999건씩 자동 페이지 처리합니다.
행사 API가 오류 없이 0건을 반환하는 것은 인증 오류가 아니라 현재 API에서 해당 과거
기간 자료를 제공하지 않은 경우입니다. 이때에도 기상·특보 수집은 별도로 진행할 수 있습니다.
폐기된 `KorService1`은 호출하지 않으며, `KorService2`가 정상 응답으로 0건을 반환하면
행사 원천을 0건 정상 완료로 기록합니다.
특보 API의 `최대 조회 기간은 오늘 기준으로 6일 전까지`는 과거 구간을 7일씩 나누라는
뜻이 아니라 최근 7일만 제공한다는 제한입니다. 분석 범위가 그보다 이전이면 코드가 API를
반복 호출하지 않고 `특보 제외`로 기록합니다. 과거 특보는 이 API로 소급 수집할 수 없으며,
기상 일자료와 뉴스·웹 근거로 외생 충격을 확인합니다.

모든 적재는 기본키 기준 `UPSERT`이므로 같은 파일을 다시 실행해도 중복 행이 생기지
않습니다. API 또는 인터넷이 끊기면 같은 명령을 다시 실행하십시오.

결과는 MySQL과 `collected_data`의 UTF-8 BOM CSV에 함께 저장됩니다.

## 4. 남은 외부 근거 수집

이 폴더와 `event_evidence_collector`가 아래처럼 나란히 있어야 합니다.

```text
C:\Users\han\yaho\final_collection_20260922
C:\Users\han\yaho\event_evidence_collector
```

다음 파일 하나를 실행합니다.

```bat
05_collect_remaining_evidence.cmd
```

이 명령은 기존 체크포인트를 이용해 이미 성공한 요청을 건너뛰고 P1/P2/P3의 남은
기본 검색과 원인 유형별 검색을 마친 뒤 분석 뷰 및 팀 CSV를 다시 생성합니다.
`--refresh`를 사용하지 않으므로 기존 결과를 삭제하지 않습니다.

최신 결합 패키지에서는 이어서 형제 폴더 `detail_integration`의 450개 통합 에피소드
스냅샷과 `team_integration_export` CSV도 자동으로 갱신합니다. 따라서 두 폴더가
아래처럼 함께 있어야 합니다.

```text
C:\Users\han\yaho\event_evidence_collector
C:\Users\han\yaho\detail_integration
C:\Users\han\yaho\final_collection_20260922
```

## 5. 검증

```bat
06_validate.cmd
```

확인할 기준:

- `asos`에 0보다 큰 행 수가 있어야 함
- `festival`은 현재 API가 과거 행사를 반환하지 않으면 0건일 수 있음
- `warnings`는 최근 7일 제한 때문에 분석 종료일이 이전이면 0건 정상 제외
- `runs`에 최근 `success` 실행이 있어야 함
- `failed` 실행이 있으면 해당 수집 CMD를 마감 전에 한 번 더 실행
- 기존 `anomaly_ready`는 450개 에피소드가 유지되어야 함
- `anomaly_enriched`도 450개이고 `no_new_detail=0`이어야 함
- `mapping_gaps`의 두 값이 모두 0이어야 함

## 6. 최종 동결과 백업

모든 수집과 검증을 마친 뒤 한 번 실행합니다.

```bat
90_freeze_and_backup.cmd
```

MySQL `root` 비밀번호를 입력하면 다음이 생성됩니다.

- `collected_data\tour_earlywarning_freeze_20260922.sql`
- `collected_data\collection_freeze_manifest_20260922.json`

매니페스트에는 주요 테이블 행 수·기간, 산출 파일 크기와 SHA-256이 기록됩니다.

## 마감 규칙

- 신규 API 수집 허용: **2026-09-22 23:59:59 KST까지**
- 그 이후: `02`~`05` 수집 명령이 자동 중단
- 마감 후 허용: `06_validate.cmd`, SQL 백업 복원, 정제, 매핑, 통계·모델 분석,
  보고서와 시각화 생성
- 마감 후 금지: 새로운 API 호출, 새로운 크롤링, 기존 검색의 `--refresh`

이는 수집 기준이 계속 바뀌어 분석 결과가 흔들리는 것을 막기 위한 데이터 동결입니다.
