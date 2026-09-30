# 야호레이더 로컬 MySQL 구성

이 묶음은 현재 제공된 CSV를 MySQL에 적재하고, 이후 관광 데이터랩 크롤러가
원문·실행 이력·체크포인트를 같은 DB에 저장할 수 있게 만든다.

## 결론

- 로컬 MySQL로 진행 가능하다.
- 팀원 접속은 **호스트 공인 IP + 공유기 포트포워딩** 방식으로 구성한다.
- 259개 데이터랩 원천 지역과 228개 분석 정본 지역은 별도 계층으로 저장한다.
- `events.json`이 없어도 DB 생성과 기존 데이터 적재에는 영향이 없다.

## 1. Windows에 MySQL 설치

MySQL Community Server 8.4 LTS의 MSI와 MySQL Configurator를 사용하는 구성이
가장 단순하다. 설치 시 서버를 Windows 서비스로 등록하고 UTF-8을 사용한다.

공식 문서: <https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html>

Windows 명령 프롬프트(`cmd`)에서 이 폴더로 이동한 뒤:

```powershell
mysql -u root -p < 01_schema.sql
```

`02_users.sql`을 열어 `CHANGE_*` 비밀번호와 팀원 계정/IP를 수정하고 실행한다.

```powershell
mysql -u root -p < 02_users.sql
```

`.env.example`을 `.env`로 복사하고 `MYSQL_PASSWORD`를 방금 만든 loader 비밀번호로
바꾼다. `.env`는 Git에 커밋하지 않는다.

## 2. 기존 데이터 적재

Python 3.10 이상을 권장한다. 패키지를 설치한 뒤 데이터가 있는 폴더를 지정한다.

```powershell
py -m pip install -r requirements.txt
py 02_load_existing_csv.py --data-dir C:\Users\han\yaho
```

필수 파일은 다음과 같다.

- `region_master.csv`, `region_scope.csv`
- `signals_visitors_v2.csv`, `naver_all_daily_v2.csv`
- `yt_videos_top.csv`, `관광_월별패널_259개지역.csv`

두 ZIP이 같은 폴더에 있으면 내부 파일 목록도 자동 등록한다. PDF/XLS 본문은
이번 단계에서 정규화하지 않는다. 적재기는 해시와 UPSERT를 사용해 재실행 가능하다.

검증:

```powershell
mysql -u yaho_loader -p yaho_radar < 03_validate.sql
```

가장 중요한 기대값은 정본 지역 228개, 외지인 방문자 717,744행, 네이버
138,624행, YouTube 6,338건, 데이터랩 월별 3,108행이다.

## 3. 팀원 원격 접속: 공인 IP 방식

호스트 PC의 내부 IPv4를 먼저 고정한다. 예를 들어 공유기 DHCP 예약으로
`192.168.0.50`을 계속 배정한다. `ipconfig`로 현재 주소를 확인할 수 있다.

MySQL의 `my.ini`에서 `[mysqld]` 아래를 실제 내부 IPv4로 설정한다.

```ini
[mysqld]
bind-address=127.0.0.1,192.168.0.50
port=3306
```

MySQL 8.4의 `bind_address`는 쉼표로 구분한 여러 비와일드카드 주소를 지원한다.
`0.0.0.0` 또는 `*`로 모든 인터페이스에 열지 않는다.

공식 문서: <https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html#sysvar_bind_address>

관리자 PowerShell에서 MySQL 서비스를 재시작한다.

```powershell
Restart-Service MySQL84
```

공유기 관리 화면에서 TCP 포트포워딩을 설정한다. 외부 포트는 예를 들어
`53306`, 내부 대상은 `192.168.0.50:3306`으로 둔다. 외부 포트를 바꾸는 것은
공격 방지가 아니라 불필요한 자동 스캔을 줄이는 보조 수단이다.

Windows 방화벽은 가능하면 팀원들의 공인 IP만 허용한다. 관리자 PowerShell에서:

```powershell
New-NetFirewallRule -DisplayName "MySQL 3306 for Yaho team" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3306 `
  -RemoteAddress TEAMMATE_PUBLIC_IP_1,TEAMMATE_PUBLIC_IP_2,TEAMMATE_PUBLIC_IP_3
```

`02_users.sql`의 Host에도 **호스트 PC의 IP가 아니라 각 팀원의 공인 IP**를 넣는다.
팀원 공인 IP가 바뀌면 MySQL 계정 Host와 방화벽 규칙을 함께 갱신한다.

팀원은 호스트의 공인 IP와 공유기의 외부 포트로 접속한다.

```powershell
mysql -h HOST_PUBLIC_IP -P 53306 -u teammate1 -p --ssl-mode=REQUIRED yaho_radar
```

접속이 안 되면 공유기 WAN IP와 인터넷에서 확인한 공인 IP가 같은지 비교한다.
둘이 다르면 통신사 CGNAT일 수 있으며 일반 포트포워딩이 작동하지 않는다.
그 경우 통신사에 공인 IPv4를 요청하거나 VPN/터널 방식으로 전환해야 한다.

기본 팀원 역할은 읽기 전용이다. 크롤러를 맡은 팀원에게만 `yaho_crawler_writer`
역할을 추가한다. `%` Host는 팀원의 공인 IP를 고정할 수 없을 때만 사용하며,
원격 계정에는 `REQUIRE SSL`, 강한 개별 비밀번호, 최소 권한을 유지한다.
로컬 적재 계정은 `127.0.0.1`에서만 접속하도록 분리되어 있다.

## 4. 다음 크롤러가 지켜야 할 저장 순서

1. `crawl_run`에 실행을 `running`으로 생성한다.
2. 응답 원문을 `raw_payload`에 먼저 저장한다.
3. 정규화된 월별 값은 별도 fact 테이블 또는 검증 후 패널에 적재한다.
4. 대상별 결과를 `crawl_checkpoint`에 `success`, `failed`,
   `source_unavailable`로 구분한다.
5. 실행 종료 시 `crawl_run`의 건수와 상태를 갱신한다.

이 구조로 해야 SNS 770개 결측이 “사이트에 값이 없음”인지 “수집 실패”인지
재실행 후에도 구분할 수 있다.

## 파일 설명

- `01_schema.sql`: 스키마와 크롤러 기반 테이블
- `02_users.sql`: 로컬 적재 계정, 팀원 읽기/쓰기 역할 템플릿
- `02_load_existing_csv.py`: 현재 CSV와 ZIP 목록의 멱등 적재기
- `03_validate.sql`: 적재 후 기대 건수 검증
- `DATA_AUDIT.md`: 제공 데이터의 결측·지역 매핑·ZIP 확인 결과
- `.env.example`, `requirements.txt`: 실행 환경 예시
