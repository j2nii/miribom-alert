# 관광 바이럴 이상탐지 MVP

## 이번 단계에서 하는 일

기존 일별 외지인 방문자수와 네이버 검색지수를 지역·날짜 기준으로 결합하고,
각 지역의 같은 요일 직전 8주와 비교해 이상점수를 계산합니다.

원천 `fact_signal`과 데이터랩 테이블은 수정하지 않습니다.

## 실행

폴더를 다음 위치에 풉니다.

```text
C:\Users\han\yaho\anomaly_mvp
```

다음 파일을 실행합니다.

```bat
15_apply_anomaly_mvp.cmd
```

세 단계마다 `yaho_loader` 비밀번호를 입력합니다. 마지막 검증은 윈도우 함수로
전체 일별 데이터를 계산하므로 컴퓨터에 따라 수십 초에서 수분이 걸릴 수 있습니다.

## 탐지 방식

1. 네이버와 외지인 방문자수를 `LN(1+x)`로 변환합니다.
2. 지역별·요일별 직전 8개 관측일의 평균과 표준편차를 계산합니다.
3. 네이버 `z >= 3`, 외지인 방문자 `z >= 2`를 이상으로 표시합니다.
4. 방문자 이상 발생일을 기준으로 당일 포함 직전 14일 안에 네이버 이상이 있으면
   `viral_candidate`로 표시합니다.

이 결과는 바이럴 확정이 아니라 검토 후보입니다. 공휴일, 축제, 사건, 날씨를
연결하여 원인을 검증해야 합니다.

## 주요 조회

전체 일별 점수:

```sql
SELECT *
FROM tour_earlywarning.vw_daily_anomaly_scored;
```

검토 후보와 데이터랩 월별 문맥:

```sql
SELECT *
FROM tour_earlywarning.vw_anomaly_candidate_context
WHERE is_viral_candidate = 1
ORDER BY anomaly_score DESC;
```

지역 하나 확인:

```sql
SELECT region_id, region_name, observed_date,
       naver_interest, visitors_external,
       naver_z_max_prior_14d, visitor_z,
       anomaly_score, candidate_type,
       matched_event_names
FROM tour_earlywarning.vw_anomaly_candidate_context
WHERE region_id = '48310'
ORDER BY observed_date;
```

## 지표 해석

- `naver_z`: 해당 지역의 평소 같은 요일 대비 네이버 검색 이상도
- `visitor_z`: 해당 지역의 평소 같은 요일 대비 외지인 방문 이상도
- `naver_z_max_prior_14d`: 현재 날짜까지 최근 14일 중 가장 큰 검색 이상도
- `is_viral_candidate`: 검색 이상 뒤 방문자 이상이 관찰된 후보
- `anomaly_score`: 검색 이상 45%, 방문자 이상 55%로 결합한 우선순위 점수

YouTube는 6개 사례 지역의 월별 상위 영상 표본이므로 점수에는 사용하지 않고
후보 설명용으로만 표시합니다. 데이터랩도 월별이고 발표 지연이 있을 수 있으므로
탐지 점수에는 사용하지 않고 후보 설명용으로만 연결합니다.

## 이벤트 적재

`events_template.csv`를 복사해 실제 이벤트 CSV를 작성합니다. 최소 필수 열은
`event_key`, `region_id`, `event_name`, `t0_date`입니다.

날짜 의미:

- `t0_date`: 바이럴 게시물 공개, 축제 시작 등 사건의 최초 기준일
- `ta_date`: 시스템이나 관찰자가 관심 이상을 확인한 날짜(선택)
- `tb_date`: 실제 방문 반응을 확인한 날짜(선택)
- `end_date`: 행사나 영향 기간 종료일(선택)

먼저 검증합니다.

```bat
py load_events_mysql.py events.csv
```

검증이 통과하면 적재합니다.

```bat
py load_events_mysql.py events.csv --commit
```

## 현재 남은 보완

- `analysis_calendar`의 공휴일 정보는 아직 비어 있습니다.
- 날씨 데이터는 아직 연결하지 않았습니다.
- `event`와 `event_point`는 실제 이벤트 CSV를 넣어야 채워집니다.
- 현재 평균·표준편차 기반 MVP를 검증한 다음, 계절성이 강하면 STL 또는
  median/MAD 기반 탐지기로 고도화합니다.

