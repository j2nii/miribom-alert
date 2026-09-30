# 영월·거제 콘텐츠 검색어 파일럿

## 실행

1. `00_setup.cmd`
2. `.env`의 MySQL 비밀번호와 `NAVER_KEY_ID`, `NAVER_KEY_SECRET` 수정
3. `01_create_tables.cmd`
4. `02_prepare_keywords.cmd`
5. `pilot_output\keyword_review.csv`를 Excel에서 열어 `include`를 1 또는 0으로 검토
6. `03_collect_pilot.cmd`
7. `04_analyze_pilot.cmd`

## 검토 원칙

- `include=1`: 실제 사례와 직접 관련된 지역명·관광지·행사·인물·콘텐츠명
- `include=0`: 일반 단어, 다른 지역, 사례 기간 이후에 등장한 용어
- 각 지역·유형별 최대 20개만 API에 사용됩니다.
- 콘텐츠를 보고 사후 선정한 검색어이므로 결과는 회고적 파일럿이며 전체 모델 성능이 아닙니다.

## 출력

- `keyword_review.csv`: 검색어 후보 검토표
- `pilot_search_daily.csv`: 일별 검색어 그룹 지수
- `pilot_peak_summary.csv`: 검색 그룹별 피크와 방문 피크 비교
- `yeongwol_keyword_pilot.png`, `geoje_keyword_pilot.png`: 시계열 그래프
