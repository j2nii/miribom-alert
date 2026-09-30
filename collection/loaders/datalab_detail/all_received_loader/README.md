# 받은 데이터 전체 추가 적재

기존 `tour_earlywarning`의 방문자·네이버·YouTube·DataLab 월별 패널은 그대로 두고, 지금까지 받아 둔 원본 중 **목록만 등록되었거나 일부 필드만 사용되던 데이터**를 추가 적재합니다. 같은 명령을 다시 실행해도 논리 키 기준으로 갱신되므로 중복 행이 늘지 않습니다.

## 이번에 실제로 들어가는 데이터

| 원본 | 적재 대상 | 예상 규모(현재 받은 파일 기준) |
|---|---|---:|
| DataLab 탭 2~5 전체 다운로드 ZIP | 31종 CSV의 모든 원본 행 | 전체 수집 폴더에 따라 결정 |
| 관광지식정보시스템 XLS 16개 | 관광지·내/외국인 구분 월별 입장객 | 약 847,656행 |
| 제주 관광지 추이 CSV | 관광지별 일별 입장객 | 6,640행 |
| 거주지별 내국인 관광객 CSV | 연도·거주지별 응답자/구성비 | 80행 |
| 실측 방문자 보도자료 사례 | 지역별 사례와 원문 수치 | 6행 |
| 내국인 관심 관광지 순위 CSV 2개 | 지역별 TOP 10 (중복 파일은 1회 보존) | 원천 120행, DB 고유 60행 |
| PDF 30개 및 XLS 16개 | 참고문서 카탈로그 | 46개 |

PDF 본문을 억지로 표로 바꾸지는 않습니다. 파일명·제목·원본 ZIP을 추적할 수 있게 `reference_document_catalog`에 등록합니다. 반면 CSV/XLS의 분석 가능한 값은 실제 행으로 적재합니다.

## 실행 순서

1. 이 폴더를 `C:\Users\han\yaho\all_received_loader`에 풉니다.
2. `00_setup.cmd`를 실행합니다.
3. 생성된 `.env`를 메모장으로 열고 아래 네 항목을 확인합니다.

```text
MYSQL_PASSWORD=실제_yaho_loader_비밀번호
DATALAB_DOWNLOADS=C:\Users\han\yaho\datalab_collector\datalab_downloads
PORTAL_ZIP=C:\Users\han\yaho\포털추가수집.zip
KNOWLEDGE_ZIP=C:\Users\han\yaho\관광지식정보시스템_데이터.zip
```

ZIP 파일의 실제 위치가 다르면 경로만 실제 위치로 바꿉니다. 공인 IP는 여기에서 바꾸는 값이 아닙니다. 이 작업은 호스트 PC의 로컬 MySQL에 접속하므로 `MYSQL_HOST=127.0.0.1`을 유지합니다.

4. `01_create_tables.cmd`
5. `02_scan_received.cmd` — 원본을 읽어 행 수만 확인하며 DB는 변경하지 않습니다.
6. `03_load_all_received.cmd` — 실제 적재입니다. 관광지 월별 입장객 약 84.8만 행 때문에 PC에 따라 수 분 걸릴 수 있습니다.
7. `04_validate.cmd`

중간에 끊겼다면 `03_load_all_received.cmd`를 다시 실행하면 됩니다.

## 핵심 테이블

| 테이블/뷰 | 내용 |
|---|---|
| `datalab_detail_row` | DataLab 31종 CSV 전체 원본 행. `row_json`이 원 컬럼을 그대로 보존 |
| `vw_datalab_sns_companion_monthly` | 동반유형별 월별 SNS 언급량 |
| `vw_datalab_sns_travel_type_monthly` | 여행유형/트렌드별 월별 SNS 언급량 |
| `vw_datalab_navigation_destination_monthly` | 목적지 유형별 월별 내비 검색량 |
| `vw_datalab_spend_industry_monthly` | 내국인·현지인·외지인 업종별 월별 소비 |
| `vw_datalab_keyword_snapshot` | 수집 기간별 동반/여행 키워드 순위 |
| `major_attraction_visitors_monthly` | 주요 관광지 월별 입장객(2004-07~2026-06 또는 제공 범위) |
| `jeju_attraction_visitors_daily` | 제주 관광지 일별 입장객 |
| `domestic_tourist_residence_annual` | 거주지별 내국인 관광객 통계 |
| `observed_visitors_case` | 실측 방문자 보도자료 6개 사례 |
| `domestic_interest_attraction_rank` | 사례 지역 관심 관광지 TOP 10 |
| `external_collection_catalog` | 거제·제주 추가수집 카탈로그 |
| `reference_document_catalog` | PDF/XLS 참고자료 목록 |
| `ingest_source_file`, `ingest_archive_member` | 어떤 ZIP·내부 파일이 몇 행 적재됐는지 추적 |

기존 분석용 정본은 계속 `vw_datalab_canonical_monthly`, `vw_anomaly_analysis_ready`를 사용합니다. 이번 테이블은 그 결과를 설명하거나 더 세분화할 때 조인하는 보강 데이터입니다.

## DataLab 세부 행 조회 방법

DataLab 파일 유형마다 컬럼이 달라서 원본 행을 JSON으로 보존했습니다. 자주 쓰는 항목은 위의 뷰로 바로 조회할 수 있고, 나머지는 다음처럼 조회합니다.

```sql
SELECT source_region_code, observed_month, data_group, row_json
FROM datalab_detail_row
WHERE data_group = '외국인 방문 현황'
  AND source_region_code = '11110';
```

전체 예시는 `TEAM_QUERY_EXAMPLES.sql`에 있습니다.

## 정상 완료 기준

- `04_validate.cmd`의 `적재 실패 파일`이 `0`
- DataLab 파일 유형이 샘플 기준 `31`
- `major_attraction_visitors_monthly`가 약 `847,656`행
- `jeju_attraction_visitors_daily`가 `6,640`행
- `domestic_interest_attraction_rank`가 `60`행

DataLab 행 수는 실제 `datalab_downloads` 안의 전체 수집 기간과 지역 수에 따라 달라집니다.
