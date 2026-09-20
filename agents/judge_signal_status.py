"""3중 교차검증 판정 — data/prod/signal_status*.json을 실데이터로 만든다 (규칙 처리, LLM 미사용).

신호 (v3 회의안 A, 설계결정 D-13)
- 관심: SNS 언급량 — 전년 동월 대비 증가율에서 같은 달 전국 중앙값을 뺀 초과분(%p)
- 의도: 내비게이션 검색건수 — 같은 방식
- 실현: 외지인 방문자수(일별) — 전년 동요일 대비 배율의 7일 중앙값이 7일간 유지된 수준의 월중 최고치.
  임계 이상이면 그 달에 7일 연속 초과가 있었다는 뜻이다 (D-12와 같은 규칙)

09.20: 패널이 2020-01까지 확장돼 전년 동월 대비로 바꿨다(그 전에는 12개월뿐이라 전월 대비를 썼다).
전년 대비가 계절성을 지우고, 전국 중앙값을 빼서 명절 이동·전국 공통 변동까지 지운다.

경보 단계는 D-05 규칙을 첫 달부터 차례로 적용한다:
상향은 한 달에 한 단계, 하향은 현 단계 요건 미달이 2개월 연속일 때 한 단계.

사용법:
    uv run python collection/db_export.py        # DB 스냅샷이 없을 때
    uv run python agents/judge_signal_status.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "scripts"))

from signals import MIN_DURATION, SignalFrames  # noqa: E402
from validate_data import ALERT_ORDER, REQUIRED_FOR_NEXT, validate_payload  # noqa: E402

DB_DIR = ROOT / "data" / "raw" / "db"
PROD = ROOT / "data" / "prod"
DEFAULT_REGION = "48310"
CASE_REGIONS = ["48310", "51750", "12130", "47940", "51210", "51810"]

MONTHLY_PERCENTILE = 0.90   # 주의 단계는 민감하게 (D-05) — 월 단위 표본이 작아 99백분위는 쓰지 않는다
TREND_BAND = 0.05
HISTORY_MONTHS = 24         # 경보 이력으로 실을 개월 수 (판정 자체는 첫 달부터 이어서 계산)

PANEL_SIGNALS = [
    ("관심", "sns_mentions", "SNS 언급량 전년 동월 대비 증가율(전국 중앙값 대비 초과분)", "한국관광공사(데이터랩 소셜미디어)"),
    ("의도", "navigation_searches", "내비게이션 검색건수 전년 동월 대비 증가율(전국 중앙값 대비 초과분)", "한국관광공사(데이터랩 내비게이션)"),
]
REALIZATION_SIGNAL = "외지인 방문자수 전년 동요일 대비 배율(7일 중앙값이 7일간 유지된 수준)"
REALIZATION_PROVIDER = "한국관광공사 지역별 방문자수(data.go.kr 15101972)"

MANUAL_REF = {
    "document": "지속가능한 관광지 혼잡도 운영 관리 매뉴얼(한국관광공사, 2026.03)",
    "page": 20,
    "section": "II. 기획·설계 및 준비 > 관광지 혼잡도 운영관리 시나리오 > 임계치 기반 경보·알림 운용",
    "quote": "경보 기준 설정: 혼잡 단계(4~5), 지속시간, 유입증가율, 정체 고착시간 기준값 정의",
}


def josa_ro(word: str) -> str:
    code = ord(word[-1]) - 0xAC00
    jong = code % 28 if 0 <= code < 11172 else 0
    return "로" if jong in (0, 8) else "으로"


def josa_eul(word: str) -> str:
    code = ord(word[-1]) - 0xAC00
    return "을" if 0 <= code < 11172 and code % 28 else "를"


def trend(change: float | None) -> str:
    if change is None or pd.isna(change):
        return "유지"
    return "상승" if change > TREND_BAND else "하락" if change < -TREND_BAND else "유지"


def load_panel() -> tuple[pd.DataFrame, dict]:
    panel = pd.read_csv(DB_DIR / "datalab_monthly_panel.csv", dtype={"canonical_region_id": str},
                        parse_dates=["period_start"])
    # 일반구 등 canonical이 비어 있는 행은 시 코드와 이중 계상이라 제외한다 (stg_region_scope)
    panel = panel.dropna(subset=["canonical_region_id"]).sort_values(["canonical_region_id", "period_start"])
    thresholds = {}
    for _, col, _, _ in PANEL_SIGNALS:
        panel[f"{col}_mom"] = panel.groupby("canonical_region_id")[col].pct_change(12, fill_method=None)
        national = panel.groupby("period_start")[f"{col}_mom"].transform("median")
        panel[f"{col}_exc"] = panel[f"{col}_mom"] - national
        thresholds[col] = round(float(panel[f"{col}_exc"].dropna().quantile(MONTHLY_PERCENTILE)) * 100, 1)
    return panel, thresholds


def realization(frames: SignalFrames, region: str, month: pd.Timestamp) -> dict:
    """값 = 그 달에 7일간 '유지된' 수준의 최고치 (7일 중앙값의 최근 7일 최솟값).
    이 값이 임계 이상이면 곧 7일 연속 초과이므로, 표시값과 초과 판정이 어긋나지 않는다."""
    metric = "realization_visitors"
    sustained = frames.stat[metric][region].rolling(MIN_DURATION, min_periods=MIN_DURATION).min()
    month_end = month + pd.offsets.MonthEnd(0)
    level = float(sustained.loc[month:month_end].max())
    raw = frames.raw[metric][region]
    this_sum = raw.loc[month:month_end].sum()
    prev_sum = raw.loc[month - pd.offsets.MonthBegin(1):month - pd.Timedelta(days=1)].sum()
    threshold = frames.threshold[metric]
    return {
        "value": round(level, 2),
        "threshold": threshold,
        "exceeded": bool(level >= threshold),
        "trend": trend(this_sum / prev_sum - 1 if prev_sum else None),
        "complete": bool(frames.data_end[metric] >= month_end),
    }


def monthly_signals(panel: pd.DataFrame, thresholds: dict, frames: SignalFrames, region: str) -> list[dict]:
    rows = panel[panel["canonical_region_id"] == region]
    months = []
    for _, row in rows.iterrows():
        month = row["period_start"]
        if pd.isna(row["sns_mentions_mom"]) and pd.isna(row["navigation_searches_mom"]):
            continue  # 전년 같은 달이 없는 구간
        signals = []
        for stage, col, label, provider in PANEL_SIGNALS:
            exc = row[f"{col}_exc"]
            missing = bool(pd.isna(exc))
            sig = {
                "stage": stage,
                "signal": label,
                "provider": provider,
                "value": None if missing else round(float(exc) * 100, 1),
                "threshold": thresholds[col],
                "unit": "%p",
                "exceeded": False if missing else bool(round(float(exc) * 100, 1) >= thresholds[col]),
                "_missing": missing,
            }
            if missing:
                sig["missing_reason"] = "데이터랩 패널에 이번 달 또는 전월 값이 없다"
            else:
                sig["trend"] = trend(row[f"{col}_mom"])
            signals.append(sig)
        real = realization(frames, region, month)
        signals.append({
            "stage": "실현",
            "signal": REALIZATION_SIGNAL,
            "provider": REALIZATION_PROVIDER,
            "value": real["value"],
            "threshold": real["threshold"],
            "unit": "배",
            "exceeded": real["exceeded"],
            "trend": real["trend"],
            "_missing": False,
            "_complete": real["complete"],
        })
        months.append({"month": month, "signals": signals})
    return months


def apply_d05(months: list[dict]) -> list[dict]:
    level, misses = "관심", 0
    history = []
    for m in months:
        exceeded = [s["stage"] for s in m["signals"] if s["exceeded"]]
        n = len(exceeded)
        change = "유지"
        idx = ALERT_ORDER.index(level)
        if level != "심각" and n >= REQUIRED_FOR_NEXT[ALERT_ORDER[idx + 1]]:
            level, misses, change = ALERT_ORDER[idx + 1], 0, "상향"
        elif level != "관심" and n < REQUIRED_FOR_NEXT[level]:
            misses += 1
            if misses >= 2:
                level, misses, change = ALERT_ORDER[idx - 1], 0, "하향"
        else:
            misses = 0
        history.append({
            "as_of": (m["month"] + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d"),
            "alert_level": level,
            "exceeded_count": n,
            "exceeded_stages": exceeded,
            "change": change,
            "_misses": misses,
        })
    return history


def basis_sentence(region_name: str, month: pd.Timestamp, history: list[dict], signals: list[dict]) -> str:
    cur = history[-1]
    prev = history[-2]["alert_level"] if len(history) > 1 else None
    over = [s["stage"] for s in signals if s["exceeded"]]
    head = f"{month.month}월 판정: "
    if over:
        head += f"{'·'.join(over)} 신호가 임계를 넘었다({len(over)}/3). "
    else:
        head += "세 신호 모두 임계 미달이다. "
    level = cur["alert_level"]
    if cur["change"] == "상향":
        return head + f"경보를 {prev}에서 {level}{josa_ro(level)} 올렸다."
    if cur["change"] == "하향":
        return head + f"{prev} 요건 미달이 2개월 연속이어서 {level}{josa_ro(level)} 내렸다."
    if cur["_misses"] == 1:
        return head + f"{level} 요건에 못 미쳤지만 하향은 2개월 연속 미달일 때만 하므로 {level}{josa_eul(level)} 유지한다."
    return head + f"{region_name} 경보는 {level}{josa_eul(level)} 유지한다."


def build(region: str, region_name: str, panel: pd.DataFrame, thresholds: dict, frames: SignalFrames,
          meta: dict) -> dict:
    months = monthly_signals(panel, thresholds, frames, region)
    history = apply_d05(months)[-HISTORY_MONTHS:]
    current, last = history[-1], months[-1]
    signals = last["signals"]
    exceeded = sum(s["exceeded"] for s in signals)
    level = current["alert_level"]

    data = {
        "region": {"code": region, "name": region_name},
        "as_of": current["as_of"],
        "alert_level": level,
    }
    if len(history) > 1:
        data["previous_alert_level"] = history[-2]["alert_level"]
    data["cross_validation"] = [{k: v for k, v in s.items() if not k.startswith("_")} for s in signals]
    data["agreement"] = {"exceeded_count": exceeded, "total": 3}
    if level != "심각":
        nxt = ALERT_ORDER[ALERT_ORDER.index(level) + 1]
        esc = {
            "next_level": nxt,
            "required_exceeded": REQUIRED_FOR_NEXT[nxt],
            "current_exceeded": exceeded,
            "met": exceeded >= REQUIRED_FOR_NEXT[nxt],
        }
        if nxt == "심각":
            esc["note"] = "경계→심각은 혼잡도 5단계 실측으로도 충족하나, 현재 혼잡도 실측이 없다."
        else:
            esc["note"] = "상향은 한 달에 한 단계, 하향은 현 단계 요건 미달이 2개월 연속일 때만 한다 (D-05)."
        data["escalation"] = esc
    data["history"] = [{k: v for k, v in h.items() if not k.startswith("_")} for h in history]
    data["basis"] = basis_sentence(region_name, last["month"], history, signals)
    data["manual_ref"] = MANUAL_REF

    caveat = [
        ("관심·의도는 전년 동월 대비 증가율에서 같은 달 전국 중앙값을 뺀 값이다. 전년 대비가 계절성을, "
        "전국 중앙값을 빼는 것이 명절 이동·전국 공통 변동을 지운다 (09.20 패널이 2020-01까지 확장돼 "
        "전월 대비에서 전년 대비로 바꿨다)."),
        (f"관심·의도 임계는 패널 전 기간 전국 {int(MONTHLY_PERCENTILE * 100)}백분위다. 지난 달 판정(history)에도 "
        "그 뒤 데이터가 반영된 임계를 썼다(표본 내 판정) — 백테스트 성과로 쓰려면 역할2가 시점별 임계로 다시 계산해야 한다."),
        ("실현 신호는 데이터랩 패널의 전년 대비 방문자 증감률 대신 일별 외지인 방문자수를 썼다. "
        "패널의 해당 열은 3,108행 중 539행에만 값이 있다. 일별 판정 규칙은 D-12와 같다(7일 지속)."),
        "혼잡도 단계는 실측이 없어 비워 두었다. 에이전트③은 현장 조치를 모두 '대기'로 둔다(D-07).",
        "시군구 단위 신호라 해수욕장·점포 같은 지점 쏠림은 보이지 않는다(에이전트① 거제·영월 사례 참조).",
        f"데이터랩 패널의 최신 월이 {data['as_of'][:7]}이라 판정 기준일이 조회일({meta['exported_at'][:10]})보다 늦다. 실시간 경보가 아니라 월 단위 사후 판정이다.",
        f"경보 이력은 최근 {HISTORY_MONTHS}개월만 싣는다. 경보 단계 자체는 패널 첫 달부터 D-05 규칙을 이어서 적용한 결과다.",
    ]
    if any(s.get("_missing") for s in signals):
        caveat.append("이번 달 패널 값이 비어 있는 신호는 미달로 처리했다.")
    if not signals[2].get("_complete", True):
        caveat.append("외지인 방문자수 일별 데이터가 기준 월 말일까지 없어 실현 신호는 월 일부로 판정했다.")

    return {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": [
            {
                "name": "한국관광 데이터랩 월별 패널 (SNS 언급량, 내비게이션 검색건수)",
                "provider": "한국관광공사 — 팀 DB datalab_monthly_panel",
                "retrieved_at": meta["exported_at"][:10],
                "url": "https://datalab.visitkorea.or.kr/",
                "note": f"적재 {meta['panel_loaded_at']}. 전월 대비 증가율 − 같은 달 전국(canonical 지역) 중앙값",
            },
            {
                "name": "지역별 방문자수 일별 (외지인)",
                "provider": "한국관광공사 data.go.kr 15101972 — 팀 DB fact_signal",
                "retrieved_at": meta["exported_at"][:10],
                "note": "전년 동요일(364일 전) 대비 배율의 7일 중앙값, 임계 초과 7일 지속 (agents/signals.py)",
            },
        ],
        "period": {
            "start": data["history"][0]["as_of"][:8] + "01",
            "end": data["as_of"],
            "granularity": "월",
        },
        "caveat": caveat,
        "data": data,
    }


def main() -> None:
    manifest = json.loads((DB_DIR / "manifest.json").read_text(encoding="utf-8"))
    files = pd.read_csv(DB_DIR / "source_file.csv")
    panel_loaded = str(files.loc[files["file_name"].str.startswith("관광_월별패널"), "loaded_at"].iloc[0])[:10]
    regions = pd.read_csv(DB_DIR / "dim_region.csv", dtype={"region_id": str}).set_index("region_id")["region_name"]
    panel, thresholds = load_panel()
    frames = SignalFrames()
    meta = {"exported_at": manifest["exported_at"], "panel_loaded_at": panel_loaded}

    print(f"임계: 관심 {thresholds['sns_mentions']}%p / 의도 {thresholds['navigation_searches']}%p "
          f"(전국 {int(MONTHLY_PERCENTILE * 100)}백분위) / 실현 {frames.threshold['realization_visitors']}배 {MIN_DURATION}일 지속\n")
    PROD.mkdir(parents=True, exist_ok=True)
    for region in CASE_REGIONS:
        payload = build(region, regions[region], panel, thresholds, frames, meta)
        errors = validate_payload("signal_status", payload)
        if errors:
            sys.exit(f"[스키마 실패] {region}: {errors[:3]}")
        name = "signal_status.json" if region == DEFAULT_REGION else f"signal_status_{region}.json"
        (PROD / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        d = payload["data"]
        track = " → ".join(f"{h['as_of'][5:7]}월 {h['alert_level']}({h['exceeded_count']})" for h in d["history"])
        print(f"{regions[region]:<5} {d['as_of']} {d['alert_level']}  | {track}")
        for s in d["cross_validation"]:
            print(f"        {s['stage']} {s['value']!s:>7}{s['unit']:<2} 임계 {s['threshold']}{s['unit']} {'초과' if s['exceeded'] else '미달'} {s.get('trend', s.get('missing_reason', ''))}")
        print(f"        {d['basis']}  → data/prod/{name}")


if __name__ == "__main__":
    main()
