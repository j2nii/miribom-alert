# 신규 세부 데이터 228개 지역·이상탐지 결합

방금 적재한 DataLab 세부 원본과 관광지 입장객을 기존 228개 분석 지역 및 450개 이상탐지 에피소드에 연결합니다. 원천 테이블은 수정하지 않고 매핑·파생 테이블과 조회 뷰만 새로 만듭니다.

## 생성되는 결과

| 테이블·뷰 | 내용 |
|---|---|
| `datalab_detail_region_map` | DataLab 원천 코드·지역명 → 228개 정본 지역 |
| `attraction_region_map` | 관광지식정보시스템 시도·시군구 → 228개 정본 지역 |
| `datalab_sns_companion_monthly_canonical` | 지역·월·동반유형별 SNS 언급량 |
| `datalab_sns_travel_monthly_canonical` | 지역·월·여행유형별 SNS 언급량 |
| `datalab_navigation_destination_monthly_canonical` | 지역·월·목적지 유형별 내비 검색량 |
| `datalab_spend_industry_monthly_canonical` | 지역·월·방문자 구분·업종별 소비 |
| `attraction_visitors_monthly_canonical` | 지역·월 관광지 입장객 합계와 상위 관광지 |
| `vw_datalab_detail_monthly_summary` | 위 세부지표를 한 행의 월별 특징으로 요약 |
| `vw_anomaly_analysis_enriched` | 기존 450개 이상 에피소드에 세부지표 결합 |
| `vw_additional_collection_priority` | 화요일 전 추가수집·검증 우선순위 |

DataLab의 나머지 상세 분포와 키워드도 삭제되지 않습니다. 전체 원본은 `datalab_detail_row`, 기간별 키워드는 `vw_datalab_keyword_canonical`에서 조회할 수 있습니다.

## 실행 순서

1. 압축을 다음 위치에 풉니다.

```text
C:\Users\han\yaho\detail_integration
```

2. `00_setup.cmd` 실행

바로 옆의 `all_received_loader\.env`가 있으면 DB 설정을 자동 복사합니다. 없으면 생성된 `.env`의 `MYSQL_PASSWORD`를 실제 `yaho_loader` 비밀번호로 바꿉니다.

3. `11_apply_detail_integration.cmd` 실행

2백만 행이 넘는 원본에서 필요한 파일 유형을 선별하고 최신 중복값을 정리하기 때문에 수 분에서 수십 분 걸릴 수 있습니다. 실행 중 MySQL과 PC를 끄지 마세요. 같은 명령을 다시 실행해도 파생 테이블을 다시 계산하므로 중복은 생기지 않습니다.

4. `12_export_collection_queue.cmd` 실행

`team_integration_export` 폴더에 다음 파일이 생성됩니다.

- `anomaly_analysis_enriched.csv`: 세부정보가 결합된 전체 450개 에피소드
- `additional_collection_priority.csv`: 화요일 전 추가수집·수동검증 대상
- `datalab_detail_monthly_summary.csv`: 228개 지역 월별 세부지표
- `datalab_detail_unmapped.csv`: DataLab 미매핑 지역
- `attraction_region_unmapped.csv`: 관광지 자료 미매핑 시군구
- `integration_status_summary.csv`: 결합 상태 요약

5. 필요하면 `13_validate.cmd`를 다시 실행합니다.

### 미매핑 CSV를 확인한 뒤 보정하는 경우

`datalab_detail_unmapped.csv`와 `attraction_region_unmapped.csv`에서 확인된
일반구·특례시·행정개편 전 명칭은 `15_apply_missing_mappings.cmd`로 반영합니다.
이 명령은 확정된 매핑을 적용한 뒤 41~43번 단계의 상세 피처, 통합 스냅샷과
검증 결과를 모두 다시 계산합니다. 정상 완료 후 `12_export_collection_queue.cmd`를
다시 실행하여 기존 CSV를 최신 결과로 갱신하세요.

정상 완료 시 `unmapped_pairs=0`, `unmapped_rows=0`,
`unmapped_districts=0`이어야 합니다. DataLab 상세 월별 요약은
228개 지역 × 80개월인 18,240행이 됩니다.

### 검증 중 `#sql... doesn't exist` 오류가 발생한 경우

MySQL이 복합 월별 집계 뷰를 현재월과 전월에 동시에 펼칠 때 발생할 수 있는
내부 임시 테이블 오류입니다. 원본과 1~3단계 결과를 다시 적재할 필요는 없습니다.
수정본을 기존 폴더에 덮어쓴 뒤 `14_fix_enriched_view.cmd`를 실행하면 기존 이상
에피소드, 에피소드별 YouTube 집계, 월별 상세 집계와 최종 결합 결과를 각각 물리
스냅샷으로 만든 다음 단순 조회 뷰를 재생성하고 검증합니다. 성공하면
`12_export_collection_queue.cmd`를 실행하세요.

## 추가수집 우선순위 해석

| 우선순위 | 의미 |
|---|---|
| `P1` | 이상점수가 높고 아직 원인이 확인되지 않은 에피소드. 먼저 신규 검색 |
| `P2` | 원인 미확인 에피소드지만 P1보다 점수가 낮음 |
| `P3` | 자동 근거가 이미 있으므로 신규 수집보다 날짜·지역·원인 수동검증 우선 |

`suggested_search_query`는 네이버 검색 API나 수동 검색에 바로 사용할 초안입니다. 자동 순위가 원인 확정을 의미하지는 않습니다.

## 정상 완료 기준

- `enriched_episodes = 450`
- `duplicate_episode_keys = 0`
- `datalab_detail_unmapped`와 `attraction_region_unmapped`가 가능한 한 0에 가까움
- 기존 `vw_anomaly_analysis_ready`와 신규 `vw_anomaly_analysis_enriched`의 에피소드 수가 동일함

미매핑이 남아도 원천 데이터가 사라지는 것은 아닙니다. 해당 지역만 파생지표에서 제외되므로, 출력 결과를 보내주면 수동 매핑 규칙을 추가할 수 있습니다.

## 분석에서의 사용 위치

이번 작업은 이상탐지 모델을 다시 학습시키는 단계가 아닙니다. 우선 기존 이상 에피소드에 다음 맥락을 붙여 원인과 추가 수집 필요성을 판별합니다.

- 검색량 상승과 함께 어떤 여행유형·동반유형이 증가했는가
- 내비 검색에서 어떤 목적지 유형이 가장 컸는가
- 외지인 소비가 어떤 업종에 집중됐는가
- 해당 월 실제 관광지 입장객도 함께 증가했는가
- 같은 시기에 YouTube 영상 근거가 존재하는가

결합 결과를 확인한 뒤 유효한 변수를 골라 이상탐지 v3의 입력 또는 사후 설명변수로 사용합니다.
