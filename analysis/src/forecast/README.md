# forecast — 시계열 예측과 탐지 (담당: 재은)

방문자 예측 모델과 검색 신호의 선행성 검증 코드입니다. 수영님의 수집·이상탐지 파이프라인(`../anomaly/`, `../review/`, `../../collection/`)과는 별개로 돌아갑니다.

## 실행 순서

전 과정을 한 번에 돌리려면 이것 하나면 된다.

```bash
uv run python analysis/src/forecast/run_all.py            # 전체 재실행 + 동결본 대조 (20~40분)
uv run python analysis/src/forecast/run_all.py --offline  # DB 없이 (패널이 이미 있을 때)
uv run python analysis/src/forecast/freeze.py --check     # 수치가 그대로인지만 확인 (10초)
```

단계별로 돌릴 때의 순서는 아래와 같다.

```bash
uv run python analysis/src/forecast/build_panel.py      # 1. DB → 분석 패널 (먼저 실행)
uv run python analysis/src/forecast/build_external.py   # 1-2. DB → 데이터랩 월간·근거기사·바이럴 키워드
uv run python analysis/src/forecast/baseline.py         # 2. 예측 사다리 (--horizon 1 도 가능)
uv run python analysis/src/forecast/models.py           # 3. 모델 계열 비교
uv run python analysis/src/forecast/detect.py           # 4. 급증 탐지와 검색 선행성
uv run python analysis/src/forecast/review_checks.py    # 5. 전면 검토 (누출·위약·기저율·민감도)
uv run python analysis/src/forecast/ablation.py         # 5-2. 추가 데이터 기여도 (씨앗·위약·붓스트랩)
uv run python analysis/src/forecast/detect_ablation.py  # 5-3. 추가 데이터로 조기경보가 되는가
uv run python analysis/src/forecast/evidence_check.py   # 5-4. 근거 기사를 입력으로 쓸 수 있는가
uv run python analysis/src/forecast/compare_pipelines.py# 5-5. 수영님 450건과 대조 · 명절 정렬 재검
uv run python analysis/src/forecast/point_level.py      # 5-6. 전국 관광지점 vs 시군구 총량 (사각지대)
uv run python analysis/src/forecast/point_level_rigor.py# 5-7. 그 결과에 대한 반론 8가지 검증
uv run python analysis/src/forecast/figures.py          # 6. 서식4용 그림 6장
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
| `build_external.py` | 데이터랩 월간·근거기사·바이럴 키워드 내려받기 | `datalab_monthly.csv` 외 |
| `ablation.py` | 블록별 기여도. 씨앗 잡음·전진후진·붓스트랩·위약 대조군 | `ablation_h7.json` |
| `detect_ablation.py` | 월 단위 조기경보 실험(AUC·상승도) | `detect_ablation.json` |
| `evidence_check.py` | 근거 기사 사용 가능성 판정 | `evidence_check.json` |
| `compare_pipelines.py` | 수영님 파이프라인과 대조, 명절 정렬 재검 | `pipeline_comparison.json` |
| `point_level.py` | 전국 관광지점 배율 vs 시군구 총량, 총량 감시 사각지대 | `point_level.json` |
| `point_level_rigor.py` | 감지 불가능성·연도 재현·균형 패널·경보 부담 등 반론 8종 | `point_level_rigor.json` |
| `figures.py` | 그림 8장 | `docs/submission/figures/` |
| `freeze.py` | 서식4에 쓸 수치 동결·대조 | `frozen_numbers.json` · `docs/확정수치_0924.md` |
| `run_all.py` | 전 과정 재실행 + 동결본 대조 | 콘솔 |

`baseline.py`의 `build_features`·`SPLITS`는 다른 스크립트들이 공통으로 가져다 씁니다. 분할이나 지연 규칙을 바꾸려면 여기만 고치면 됩니다.

## 결과 문서

- **`docs/시계열파트_안내서.md` — 처음 보는 사람은 이것부터. 이 파트 전체가 한 문서에 정리되어 있다**

- `docs/분석_검증_추가데이터_0924.md` — **추가 데이터 검증의 결론과 정정 사항 (최신)**
- `docs/분석_지점쏠림_반론검증_0924.md` — **핵심 주장에 대한 반론 8가지와 답**
- `docs/확정수치_0924.md` — **서식4에 옮길 숫자는 전부 여기서 가져온다**
- `docs/작업기록_0922.md` — 9/22까지의 전체 파악
- `docs/분석_누출점검표.md` — 어떤 변수를 왜 썼는가·안 썼는가
- `docs/분석_결과_예측사다리.md` · `docs/분석_결과_탐지와모델비교.md`
