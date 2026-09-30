# 최종 분석 검토 도구

## 순서

1. `00_setup.cmd` 실행
2. `.env`의 `MYSQL_PASSWORD` 수정
3. `02_prepare_review.cmd` 실행
4. `review_output/human_review_top20.csv`의 `human_label` 20개 입력
5. `03_import_review.cmd` 실행

## human_label 허용값

- `true_signal`: 실제 관광 이슈·축제·바이럴 근거 확인
- `calendar_effect`: 명절·공휴일·휴가철 영향
- `weather_or_disruption`: 날씨·재난·교통 영향
- `false_alarm`: 관광 이상 신호로 보기 어려움
- `uncertain`: 근거 부족

## 자동 생성 파일

- `festival_pre_signal_26.csv`: 축제 전 신호 26건
- `leadtime_metrics.csv`: 검색·방문 선행일 평균·중앙값, 3일·7일 이상 건수
- `human_review_top20.csv`: 미설명 후보 상위 20건 검토표
- `yeongwol_geoje_review.csv`: 영월·거제 사례표

`reviewed_precision_pct`와 `reviewed_false_alarm_pct`는 상위 20건 검토 표본의 수치이며 전체 450건의 정확도가 아닙니다.
