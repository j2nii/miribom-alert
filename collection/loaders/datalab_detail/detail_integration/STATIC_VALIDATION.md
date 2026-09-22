# 패키지 정적 검증

- Python 파일 2개 문법 검사 통과
- MySQL 방언 SQL 파싱 통과
- SQL 실행 파일 수: 4개
- 적용 SQL 문장 수: 58개
- Windows CMD 파일: ASCII 인코딩 확인
- 원천 테이블은 `UPDATE`, `DELETE`, `TRUNCATE`하지 않음
- 재계산 시 `TRUNCATE`되는 대상은 이 패키지가 생성한 파생 테이블뿐임

실제 지역 매핑률과 에피소드 결합률은 사용자 PC의 MySQL에서 `11_apply_detail_integration.cmd` 실행 후 검증됩니다.
