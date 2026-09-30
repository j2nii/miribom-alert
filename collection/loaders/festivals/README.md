# 문화축제 표준데이터 적재기

문화 빅데이터 플랫폼의 `KC_488_WNTY_CLTFSTVL_2019~2025.csv`를 정제하여
기존 `tour_earlywarning.event`, `event_point`에 적재합니다.

## 처리 기준

- 실제 행사 시작일 `FSTVL_BEGIN_DE` 기준 `2023-01-01~2026-08-31`만 사용
- 축제명·시도·시군구·시작일·종료일 기준 중복 제거
- 같은 축제가 여러 스냅샷에 있으면 더 최신 파일의 행을 사용
- `FSTVL_BEGIN_DE` → `event_point.T0`
- `FSTVL_END_DE` → `event_point.end`
- 지역은 법정동 코드와 `dim_region`의 시도·지역명으로 이중 확인
- 매핑되지 않은 행이 있으면 실제 적재를 중단하고 `festival_unmapped.csv` 생성
- 기존 수동 이벤트는 수정하거나 삭제하지 않음

## 실행 순서

1. 폴더를 `C:\Users\han\yaho\festival_calendar_loader`에 압축 해제
2. `00_setup.cmd` 실행
3. `.env`의 `MYSQL_PASSWORD`를 실제 `yaho_loader` 비밀번호로 변경
4. `01_check_festivals.cmd` 실행
5. 검증이 통과하면 `02_load_festivals.cmd` 실행
6. `03_validate.cmd` 실행

`01_check_festivals.cmd`는 DB를 변경하지 않습니다. 같은 파일을 다시 적재해도
`event_key` 기준으로 갱신되므로 중복 행이 생기지 않습니다.

