# 이벤트 근거 수집기

`vw_event_research_queue`의 미설명 에피소드에 대해 네이버 검색 API의 뉴스·블로그·
웹문서 결과를 수집합니다. 검색 결과를 이벤트 정답으로 자동 확정하지 않고 검토용
근거 후보로만 저장합니다.

## 처리 흐름

1. 동일 날짜 다지역 급증과 동일 지역·월 반복을 계산해 P1/P2/P3 우선순위 생성
2. 네이버 뉴스·블로그·웹문서에서 에피소드별 근거 후보 수집
3. 공식기관 도메인, 지역명, 행사 키워드, 발행일 거리를 이용해 근거 순위 계산
4. 에피소드별 상위 검색 근거를 분석 뷰로 자동 연결
5. 확정 이벤트 정답셋이 필요할 때만 CSV를 선택적으로 검토
6. `accepted`로 승인한 행만 `event`와 `event_point`에 적재

## 1. 설치

폴더를 다음 위치에 풉니다.

```text
C:\Users\han\yaho\event_evidence_collector
```

실행:

```bat
00_setup.cmd
```

생성된 `.env`를 메모장으로 열고 다음 값을 실제 값으로 변경합니다.

```text
MYSQL_PASSWORD=MySQL의 yaho_loader 비밀번호
NAVER_API_HUB_CLIENT_ID=NAVER API HUB의 Client ID
NAVER_API_HUB_CLIENT_SECRET=NAVER API HUB의 Client Secret
```

따옴표는 넣지 않습니다. 이 값은 구형 네이버 개발자센터 키나 검색광고 API 키가
아니라, 네이버 클라우드 플랫폼의 `NAVER API HUB > Application > 인증 정보`에서
발급한 값이어야 합니다. 해당 애플리케이션에서 뉴스·블로그·웹문서 검색 API를
사용할 수 있도록 등록해야 합니다.

기존 버전을 이미 설치했다면 압축을 덮어쓴 뒤 기존 `.env`를 직접 열어 예전
`NAVER_KEY_ID`, `NAVER_KEY_SECRET` 대신 위의 API HUB 변수 두 줄을 추가합니다.
설치 스크립트는 기존 `.env`를 덮어쓰지 않습니다.

`401`은 API HUB Client ID 또는 Client Secret이 틀렸거나 애플리케이션의 API 권한이
설정되지 않았다는 뜻입니다. 수집기는 시작할 때 인증 요청 한 번이 실패하면 추가 호출
없이 즉시 중단합니다. `429`는 API HUB의 일일 호출 한도 초과이므로 한도가 초기화된
뒤 다시 실행합니다.

## 2. DB 테이블 생성

```bat
01_create_tables.cmd
```

MySQL 비밀번호를 한 번 입력합니다. 출력되는 P1/P2/P3 건수는 오류가 아니라 수집
우선순위 현황입니다.

## 3. 10건 파일럿

```bat
02_collect_pilot.cmd
```

10개 에피소드 × 검색 종류 3개로 최대 30회를 호출합니다. 성공한 항목은 체크포인트에
기록되므로 같은 명령을 다시 실행하면 건너뜁니다.

## 4. 우선순위 수집

파일럿이 정상일 때 실행합니다.

```bat
03_collect_priority.cmd
```

P1·P2 중 상위 100개 에피소드를 수집합니다. 이후 전체 220건을 받으려면 직접 다음을
실행합니다.

```bat
py collect_event_evidence.py --tiers P1,P2,P3 --limit 0 --display 10
```

검색 결과를 새로 받고 싶을 때만 `--refresh`를 추가합니다. 이 옵션은 해당 대상의
기존 검색 근거를 삭제한 뒤 다시 수집하므로 평상시에는 사용하지 않습니다.

## 5. 분석용 자동 근거 뷰 생성

수집이 끝나면 다음을 실행합니다.

```bat
07_create_analysis_views.cmd
```

사람이 500행을 검토하지 않아도 다음 뷰에서 에피소드별 상위 검색 근거를 바로
분석할 수 있습니다.

```sql
SELECT *
FROM tour_earlywarning.vw_anomaly_episode_top_evidence
ORDER BY research_priority, research_priority_score DESC;
```

- `vw_anomaly_episode_top_evidence`: 에피소드별 최상위 근거 1개
- `vw_anomaly_episode_evidence_top3`: 에피소드별 상위 근거 3개
- `auto_cause_type`: `tourism_event/disruption/viral_media/access_offer/other`
- `auto_confidence`: 제목의 지역·원인어, 기사 발행일과 방문 피크의 30일 이내
  근접성, 문서 유형을 반영한 `high/medium/low` (`webkr` 무날짜 문서는 최대 `medium`)
- `evidence_status='unverified'`: 자동 순위 검색 근거이며 이벤트 정답은 아님
- `evidence_status='verified'`: 사람이 승인한 확정 근거

팀 분석과 사례 탐색에는 자동 근거 뷰를 사용하고, 논문용 정답셋이나 성능 평가처럼
정확한 이벤트 라벨이 필요할 때만 아래 CSV 검토를 진행합니다.

자동 분석에서는 우선 `auto_confidence IN ('high', 'medium')`만 사용하십시오. `low`는
검색 결과가 부족한 에피소드이므로 이벤트가 확인됐다는 근거로 사용하면 안 됩니다.

초기 검색 결과가 전국 축제 목록이나 일반 공문 위주라면 다음을 한 번 실행합니다.

```bat
08_collect_targeted_evidence.cmd
```

행사뿐 아니라 재난·통제, 방송·촬영지·바이럴, 개장·개통·혜택을 분리 검색합니다.
기존 검색 결과를 삭제하지 않으며, 중단돼도 같은 명령을 다시 실행하면 완료된
지역·검색 범주를 건너뛰고 이어서 수집합니다. 완료 후 `07_create_analysis_views.cmd`를
다시 실행해 순위를 갱신합니다.

## 6. 팀 분석용 최종 통합 뷰 생성

자동 근거 순위가 확정되면 다음을 실행합니다.

```bat
09_create_analysis_ready_view.cmd
```

생성되는 뷰는 다음과 같습니다.

- `vw_anomaly_analysis_ready`: 450개 전체 이상 에피소드의 통합 분석 테이블
- `vw_anomaly_analysis_explained`: 달력·기존 이벤트·외부 근거가 있는 사례
- `vw_anomaly_analysis_unresolved`: 아직 설명되지 않은 사례

`vw_anomaly_analysis_ready`에는 네이버/방문자 이상 점수와 비율, 검색-방문 시차,
자동 이벤트 근거, 데이터랩 월별 방문·SNS·길찾기·숙박검색·관광소비 및 전월 대비
변화율이 한 행에 포함됩니다.

```sql
SELECT *
FROM tour_earlywarning.vw_anomaly_analysis_ready
ORDER BY peak_anomaly_score DESC;
```

`explanation_status`는 확정 이벤트, 달력 효과, 강한 외부 후보, 보조 외부 후보,
검색했지만 미해결, 미수집을 구분합니다. 자동 외부 후보는 확정 인과관계가 아닙니다.

팀 공유용 CSV를 만들려면 다음을 실행합니다.

```bat
10_export_team_analysis.cmd
```

`team_analysis_export` 폴더에 전체 450건, 외부 근거 후보, 미설명 에피소드, 상태 요약,
원인 유형 요약 CSV가 생성됩니다. 핵심 변수 정의는 `TEAM_ANALYSIS_COLUMNS.md`,
Workbench용 기본 분석 쿼리는 `34_team_analysis_queries.sql`을 참고합니다.

## 7. 선택 사항: 확정 이벤트 검토 CSV 생성

```bat
04_export_review.cmd
```

`event_review_candidates.csv`가 생성됩니다. Excel에서 근거 URL을 확인한 후 다음
열을 작성합니다.

| 열 | 입력값 |
|---|---|
| `decision` | 승인 `accepted`, 제외 `rejected`, 중복 `duplicate` |
| `event_name` | 공식 행사명 |
| `event_type` | 축제, 스포츠, 공연, 박람회, 정책행사 등 |
| `event_start` | `YYYY-MM-DD` |
| `event_end` | `YYYY-MM-DD` |
| `review_note` | 판단 근거와 주의사항 |

승인하지 않을 행의 다른 입력칸은 비워도 됩니다. 동일 이벤트의 검색 결과 여러 개를
동시에 `accepted`로 표시하지 말고 가장 신뢰도 높은 근거 하나만 승인합니다.

## 8. 선택 사항: 검증 후 확정 이벤트 적재

먼저 DB를 바꾸지 않는 검증을 실행합니다.

```bat
05_check_reviewed.cmd
```

문제가 없을 때만 실제 적재합니다.

```bat
06_load_reviewed.cmd
```

적재 후 `22_apply_episode_review.cmd`를 다시 실행할 필요는 없습니다. 다음 쿼리로
기존 450개 에피소드의 이벤트 매칭이 즉시 반영되는지 확인합니다.

```sql
SELECT review_status, COUNT(*) AS episodes
FROM tour_earlywarning.vw_anomaly_episode_review
GROUP BY review_status;
```

## 네이버 API 기준

- API HUB 개요: https://api.ncloud-docs.com/docs/naver-api-hub-overview
- 뉴스 검색: https://api.ncloud-docs.com/docs/naver-api-hub-search-news
- 블로그 검색: https://api.ncloud-docs.com/docs/naver-api-hub-search-blog
- 웹문서 검색: https://api.ncloud-docs.com/docs/naver-api-hub-search-webkr

요청 주소는 `https://naverapihub.apigw.ntruss.com/search/v1/...`이며, API HUB에서
발급한 Client ID와 Client Secret을 `X-NCP-APIGW-API-KEY-ID`,
`X-NCP-APIGW-API-KEY` 헤더에 넣습니다.
