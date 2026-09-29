# 관광 조기경보 UI

## 팀원이 UI 실행하기

[Node.js 20.11 이상](https://nodejs.org/)을 설치한 뒤 저장소를 받아 아래 명령을 실행합니다. 명령은 저장소의 `web` 폴더에서 실행해야 합니다.

```bash
git clone https://github.com/j2nii/tourism-early-warning.git
cd tourism-early-warning
git switch poolhan/ui-improvement
cd web
npm ci
npm run dev:full
```

터미널에 표시되는 주소 또는 [영월 화면](http://localhost:5173/?region=yeongwol)을 브라우저에서 엽니다. `Ctrl+C`로 종료합니다. 다른 팀원도 자신의 컴퓨터에서 같은 주소를 열 수 있지만, `localhost`는 각자의 컴퓨터를 가리킵니다.

이 명령은 화면과 로컬 질의 API를 함께 실행합니다. 화면에 쓰는 지역별 JSON 자료는 저장소의 `data/prod`와 `data/mock`에서 읽으므로 UI 확인에 DB 접속은 필요하지 않습니다. 챗봇 질의까지 사용하려면 `web/.env.example`을 `web/.env`로 복사하고 `UPSTAGE_API_KEY`를 채워야 합니다. 키가 없어도 나머지 UI는 확인할 수 있습니다. 비밀 키가 든 `.env` 파일은 GitHub에 올리지 마세요.

화면만 확인할 때는 `web` 폴더에서 `npm run dev`를 실행해도 됩니다. 이 경우 챗봇 질의 API는 실행되지 않습니다.

## 공유 주소

위 명령은 팀원 컴퓨터에서 실행하는 방법입니다. 설치 없이 브라우저 링크 하나로 보려면 별도 웹 배포가 필요합니다. `localhost` 주소를 팀원에게 보내도 팀원의 컴퓨터에서 실행한 서버가 없으면 화면이 열리지 않습니다.
