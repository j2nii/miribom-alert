# 네이버 검색량 2023-01 ~ 2026-08 확장 수집

데이터랩 브라우저 크롤러와 서로 독립적이므로 **별도 CMD 창에서 병렬 실행**해도 됩니다. 기존 데이터랩 크롤러를 끄지 마세요.

## 1. 폴더 배치

압축을 풀어 다음 구조로 둡니다.

```text
C:\Users\han\yaho\
├─ signals_visitors_v2.csv
├─ region_master.csv
├─ naver_all_daily_v2.csv
├─ .env
├─ yaho_mysql_setup\
│  └─ .env
└─ naver_extended\
   ├─ 00_setup.cmd
   ├─ 01_collect_and_merge.cmd
   └─ ...
```

기존 CSV는 지우거나 덮어쓰지 않습니다. 새 결과는 `naver_extended` 폴더에 별도 생성됩니다.

## 2. API 키 설정

`C:\Users\han\yaho\.env`에 다음 두 줄을 추가합니다.

```dotenv
NAVER_KEY_ID=실제_API_KEY_ID
NAVER_KEY_SECRET=실제_API_KEY_SECRET
```

반드시 실제 값으로 바꾸어야 합니다. `.env`는 팀원에게 보내지 마세요.

> 기존 파이썬 파일에 API 인증정보가 직접 들어 있었습니다. 이 버전에서는 제거했으며, 안전을 위해 네이버 콘솔에서 기존 키를 재발급하는 것을 권장합니다.

## 3. 실행 순서

데이터랩 수집이 돌아가는 창은 두고, 새 CMD 창을 열어 실행합니다.

1. `00_setup.cmd`
2. `01_collect_and_merge.cmd`
3. `02_check_mysql_load.cmd` — CSV만 검증, DB 변경 없음
4. 검증이 통과하면 `03_load_mysql.cmd`
5. 명령 프롬프트에서:

```bat
mysql -u yaho_loader -p tour_earlywarning < 04_validate_mysql.sql
```

## 4. 수집 구간과 결과

| 단계 | 기간 | 의미 |
|---|---|---|
| 앞 구간 | 2023-01-01 ~ 2024-12-31 | 과거 확장 |
| 뒤 구간 | 2024-07-01 ~ 2026-08-31 | 기존 구간 포함 |
| 겹침 | 2024-07-01 ~ 2024-12-31 | 두 구간 스케일 연결·검증 |
| 최종 | 2023-01-01 ~ 2026-08-31 | 228개 지역 × 1,339일 = 305,292행 |

최종 파일은 `naver_all_daily_202301_202608.csv`입니다. 앞 구간 스케일은 6개월 겹침 구간으로 보정하고, 겹침 시계열 상관계수가 기준에 못 미치면 병합을 중단합니다.

## 5. 중단·재시작

API 한도, 통신 오류, PC 재부팅으로 중단되면 `01_collect_and_merge.cmd`를 다시 실행하세요. 기간별 `naver_progress_*.json`에 저장된 완료 호출은 건너뜁니다.

- 기간과 progress 파일이 맞지 않으면 스크립트가 즉시 중단됩니다.
- 배치 실패, 중복, 일수 누락, 지역 누락이 있으면 성공 코드로 넘어가지 않습니다.
- 이 수집기는 브라우저를 쓰지 않으므로 데이터랩 로그인 세션과 무관합니다.

## 6. DB 반영 방식

`03_load_mysql.cmd`는 `fact_signal`의 다음 조건을 UPSERT합니다.

```text
metric        = interest_naver
source_system = naver_search_trend
granularity   = day
segment       = ''
```

2025-01 이후 기존 행은 새로 연결된 스케일의 값으로 갱신되고, 2023-01~2024-12 행은 추가됩니다. CSV 구조 검증 또는 DB 참조 검증이 실패하면 트랜잭션을 롤백합니다.

## 7. 팀원 공지용 요약

```text
기존 DB와 방문자수·YouTube 적재는 완료됐습니다.
데이터랩 공식 다운로드는 로그인 세션 만료로 지연 중이며 계속 수집 중입니다.
동시에 네이버 검색지수를 2023-01~2026-08로 확장 수집 중이고,
6개월 겹침 구간 검증 후 MySQL에 반영할 예정입니다.
```
