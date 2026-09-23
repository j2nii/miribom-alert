# forecast — 시계열 예측과 탐지 (담당: 재은)

방문자 예측 모델과 검색 신호의 선행성 검증 코드입니다. 수영님의 수집·이상탐지 파이프라인(`../anomaly/`, `../review/`, `../../collection/`)과는 별개로 돌아갑니다.

## 실행 순서

```bash
uv run python analysis/src/forecast/build_panel.py      # 1. DB → 분석 패널 (먼저 실행)
uv run python analysis/src/forecast/baseline.py         # 2. 예측 사다리 (--horizon 1 도 가능)
uv run python analysis/src/forecast/models.py           # 3. 모델 계열 비교
uv run python analysis/src/forecast/detect.py           # 4. 급증 탐지와 검색 선행성
uv run python analysis/src/forecast/review_checks.py    # 5. 전면 검토 (누출·위약·기저율·민감도)
uv run python analysis/src/forecast/figures.py          # 6. 서식4용 그림 4장
```

`build_panel.py`는 `.env`의 DB 계정을 씁니다. 나머지는 `data/interim/panel_daily.csv`만 있으면 오프라인으로 돕니다.

## 파일

| 파일 | 하는 일 | 주요 출력 |
| --- | --- | --- |
| `build_panel.py` | 일별 신호 + 달력 + 날씨 + 축제를 한 표로 | `data/interim/panel_daily.csv` (301,416행) |
| `baseline.py` | 변수를 한 층씩 올리며 오차 측정. 누출 규칙(방문자 4일·검색 1일 지연) 구현 | `baseline_h7.json` |
| `models.py` | Ridge·GBM 3종·지역별·ETS·SARIMAX 비교 | `model_comparison.json` |
| `detect.py` | 급증 사건 추출(잔차·전년대비), 검색 신호의 적중률·기저율·상승도 | `detection_summary.json` |
| `review_checks.py` | 결과를 믿어도 되는지 검사 5종 | 콘솔 출력 |
| `figures.py` | 그림 4장 | `docs/submission/figures/` |

`baseline.py`의 `build_features`·`SPLITS`는 다른 스크립트들이 공통으로 가져다 씁니다. 분할이나 지연 규칙을 바꾸려면 여기만 고치면 됩니다.

## 결과 문서

- `docs/작업기록_0922.md` — **이것만 보면 전체 파악됨**
- `docs/분석_누출점검표.md` — 어떤 변수를 왜 썼는가·안 썼는가
- `docs/분석_결과_예측사다리.md` · `docs/분석_결과_탐지와모델비교.md`
