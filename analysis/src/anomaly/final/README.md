# 최종 이상탐지 분석 패키지

축제·휴일·외부 근거·ASOS 날씨를 450개 이상탐지 에피소드에 연결합니다.

## 실행

1. `00_setup.cmd`
2. `.env`의 `MYSQL_PASSWORD` 수정
3. `01_run_final_analysis.cmd`

결과는 `analysis_output` 폴더에 생성됩니다.

## 주요 결과 파일

- `anomaly_final_450.csv`: 450개 전체 에피소드
- `festival_matched_episodes.csv`: 축제 전후 기간과 매칭된 에피소드
- `festival_leadtime.csv`: 검색·방문 피크의 축제 시작 대비 선행일
- `unexplained_candidates.csv`: 축제·달력·강한 외부 근거로 설명되지 않은 후보
- `final_metrics.csv`: 최종 요약 지표
- `explanation_group_summary.csv`: 설명 유형별 건수와 평균 점수
- `yeongwol_geoje_cases.csv`: 영월·거제 발표 사례

## 해석 주의

- 축제 매칭은 인과관계 확정이 아니라 지역·시간 일치입니다.
- `search_to_festival_lead_days > 0`이면 검색 피크가 축제 시작보다 먼저 발생했습니다.
- 기상은 광역시 대표지점 또는 지역명과 관측소명이 유일하게 일치할 때만 연결합니다.
- `conservative_explained_flag`는 축제·휴일·강한 외부 근거 중 하나가 있는 경우입니다.
- 정답 라벨의 완전한 전국 모집단이 아니므로 재현율은 계산하지 않습니다.
