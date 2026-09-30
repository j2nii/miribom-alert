# 팀 분석용 핵심 변수

기본 분석 뷰는 `tour_earlywarning.vw_anomaly_analysis_ready`입니다. 한 행은 한 지역의
한 이상 에피소드를 의미하며 `(region_id, episode_no)`가 고유키입니다.

| 변수 | 의미 | 해석 주의 |
|---|---|---|
| `search_peak_date` | 네이버 검색 급증 피크 | 방문 피크보다 최대 14일 앞선 검색 급증일 |
| `visitor_peak_date` | 방문 이상 피크 | 외부 근거의 날짜 거리 계산 기준 |
| `search_to_visit_lag_days` | 검색 피크에서 방문 피크까지 일수 | 양수이면 검색이 방문보다 먼저 증가 |
| `peak_anomaly_score` | 네이버·방문자 결합 이상 점수 | 지역 간 우선순위 비교용이며 확률이 아님 |
| `peak_naver_z` | 네이버 검색 이상 Z-score | 지역·시점별 기준선 대비 표준화 값 |
| `peak_visitor_z` | 방문자 이상 Z-score | 지역·시점별 기준선 대비 표준화 값 |
| `peak_naver_ratio` | 네이버 기준선 대비 배율 | `1`이면 기준선과 동일 |
| `peak_visitor_ratio` | 방문자 기준선 대비 배율 | `2`이면 기준선의 약 2배 |
| `explanation_status` | 현재 설명 상태 | 자동 후보와 확정 이벤트를 반드시 구분 |
| `auto_cause_type` | 외부 근거 유형 | 관광행사·재난·바이럴·개장/혜택 등 |
| `auto_confidence` | 자동 근거 신뢰도 | `high`도 인과관계 확정을 의미하지 않음 |
| `evidence_title`, `evidence_url` | 연결된 상위 외부 근거 | 논문 정답 라벨로 사용하려면 사람 확인 필요 |
| `datalab_*_mom_pct` | 데이터랩 지표 전월 대비 변화율 | 월별 지표이므로 일별 이상과 동일 시점 측정이 아님 |

## explanation_status

| 값 | 의미 |
|---|---|
| `verified_event` | 기존 `event` 테이블의 확정 이벤트와 날짜가 매칭됨 |
| `calendar_related` | 공휴일·선거일 등 달력 효과와 근접 |
| `verified_external_evidence` | 사람이 승인한 외부 근거 |
| `strong_external_candidate` | 자동 검색의 강한 후보, 미확정 |
| `possible_external_candidate` | 날짜 없는 공식 페이지 등 보조 후보 |
| `researched_unresolved` | 검색했지만 신뢰할 근거를 찾지 못함 |
| `not_researched` | 아직 외부 근거 수집 대상에 포함되지 않음 |

분석 보고에서는 자동 외부 근거를 “원인”이 아니라 “설명 후보”로 표현합니다.
