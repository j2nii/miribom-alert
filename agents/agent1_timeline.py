"""에이전트① 사례 타임라인 — 근거 기록 + DB 신호를 합쳐 timeline JSON을 만든다.

역할 분담 (D-12)
- 사람/LLM 세션: 기사에서 사건·날짜·원문 인용을 찾아 agents/evidence/agent1_timeline_evidence.json에 기록
- 코드: 유튜브 날짜·조회수(DB), 검색 급증 신호(signals.py), 시차 계산, 규칙 검사, 원문 대조

손으로 쓴 숫자가 화면에 가지 않도록, 기사 수치는 value_text가 인용문에 그대로 있어야 하고
영상 수치는 DB에서만 읽는다.

사용법:
    uv run python collection/db_export.py               # DB 스냅샷 (처음 한 번, 또는 DB 갱신 시)
    uv run python agents/agent1_timeline.py --verify-sources
    uv run python agents/agent1_timeline.py              # 원문 대조 생략 (오프라인)

출력:
    data/prod/timeline.json            기본 지역(거제)
    data/prod/timeline_{코드}.json     그 밖의 사례
    data/handoff/event.csv, event_point.csv   DB event 테이블 적재 제안본
"""

import argparse
import csv
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "scripts"))

from signals import METRICS, MIN_DURATION, PERCENTILE, SignalFrames  # noqa: E402
from validate_data import validate_payload  # noqa: E402

EVIDENCE = ROOT / "agents" / "evidence" / "agent1_timeline_evidence.json"
DB_DIR = ROOT / "data" / "raw" / "db"
PROD = ROOT / "data" / "prod"
HANDOFF = ROOT / "data" / "handoff"
DEFAULT_REGION = "48310"

# 기사 날짜 기준 중 '사건 자체의 날짜'인 것 — 보도일보다 늦을 수 없다
EVENT_DAY_BASES = {"사건일", "기간 시작일", "집계 기준일", "발표일", "게시일"}
LEAD_TIME_BASES = {"사건일", "기간 시작일"}


class CheckError(Exception):
    pass


def parse_korean_number(text: str) -> int:
    """'56만723명' → 560723, '1만 641명' → 10641, '2,006명' → 2006"""
    s = re.sub(r"[^\d만]", "", text)
    if "만" in s:
        high, low = s.split("만", 1)
        return int(high) * 10000 + (int(low) if low else 0)
    return int(s)


def fetch_text(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    if resp.encoding in (None, "ISO-8859-1"):
        resp.encoding = resp.apparent_encoding
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", resp.text)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return re.sub(r"\s+", " ", body)


def date_patterns(d: str) -> list[str]:
    y, m, dd = d.split("-")
    mi, di = str(int(m)), str(int(dd))
    return [f"{y}-{m}-{dd}", f"{y}.{m}.{dd}", f"{y}. {mi}. {di}", f"{y}.{mi}.{di}", f"{y}{m}{dd}", f"{y}/{m}/{dd}"]


class SourceVerifier:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.cache: dict[str, str] = {}
        self.checked = 0

    def verify(self, quote: str, source: dict, where: str) -> None:
        if not self.enabled:
            return
        url = source["url"]
        if url not in self.cache:
            self.cache[url] = fetch_text(url)
        page = self.cache[url]
        if re.sub(r"\s+", " ", quote) not in page:
            raise CheckError(f"{where}: 인용문이 원문에 없다 — {url}")
        # 보도일은 페이지 본문이나 URL에 있어야 한다
        if not any(p in page or p in url for p in date_patterns(source["reported_at"])):
            raise CheckError(f"{where}: 보도일 {source['reported_at']}을 원문에서 찾지 못했다 — {url}")
        self.checked += 1


def article_source(src: dict, collected_at: str) -> dict:
    return {
        "name": src["title"],
        "provider": src["publisher"],
        "retrieved_at": collected_at,
        "url": src["url"],
        "note": f"보도 {src['reported_at']}",
    }


def check_article(ev: dict, where: str) -> None:
    for key in ("date", "date_basis", "quote", "source"):
        if not ev.get(key):
            raise CheckError(f"{where}: 기사 이벤트에 {key}가 없다")
    reported = ev["source"]["reported_at"]
    if ev["date_basis"] == "보도일" and ev["date"] != reported:
        raise CheckError(f"{where}: date_basis=보도일인데 date({ev['date']}) ≠ 보도일({reported})")
    if ev["date_basis"] in EVENT_DAY_BASES and ev["date"] > reported:
        raise CheckError(f"{where}: 사건일 {ev['date']}이 보도일 {reported}보다 늦다")
    if "value" in ev:
        if "value_text" not in ev or ev["value_text"] not in ev["quote"]:
            raise CheckError(f"{where}: value_text가 인용문에 그대로 있어야 한다")
        if parse_korean_number(ev["value_text"]) != ev["value"]:
            raise CheckError(f"{where}: value {ev['value']} ≠ value_text '{ev['value_text']}'")
    if ev["type"] == "조치 시행" and ("actor" not in ev or "is_case_response" not in ev):
        raise CheckError(f"{where}: 조치 시행에는 actor와 is_case_response가 필요하다")


def build_case(case: dict, frames: SignalFrames, videos: pd.DataFrame, meta: dict,
               verifier: SourceVerifier) -> tuple[dict, dict]:
    region = case["region_code"]
    cid = case["case_id"]
    events: list[dict] = []
    t0_dates: list[str] = []

    db_retrieved = meta["exported_at"][:10]
    yt_loaded = meta["youtube_loaded_at"]

    for i, ev in enumerate(case["events"]):
        where = f"{cid} 이벤트 {i + 1}"
        out = {k: ev[k] for k in ("type", "description", "actor", "is_case_response") if k in ev}
        if ev["kind"] == "youtube":
            row = videos[videos["video_id"] == ev["video_id"]]
            if row.empty:
                raise CheckError(f"{where}: video_id {ev['video_id']}가 DB에 없다")
            row = row.iloc[0]
            if row["region_id"] != region:
                raise CheckError(f"{where}: 영상 지역 {row['region_id']} ≠ 사례 지역 {region}")
            out["date"] = row["published_at"][:10]
            out["date_basis"] = "게시일"
            out["value"] = int(row["view_count"])
            out["unit"] = "회(조회수)"
            out["source"] = {
                "name": f"YouTube 「{html.unescape(row['title'])}」 ({row['channel_name']})",
                "provider": "YouTube — 팀 DB youtube_video (월별 조회수 상위)",
                "retrieved_at": db_retrieved,
                "url": f"https://www.youtube.com/watch?v={ev['video_id']}",
                "note": f"조회수는 DB 적재 시점({yt_loaded}) 기준",
            }
        elif ev["kind"] == "article":
            check_article(ev, where)
            verifier.verify(ev["quote"], ev["source"], where)
            out.update({k: ev[k] for k in ("date", "date_basis", "quote") if k in ev})
            for k in ("value", "unit"):
                if k in ev:
                    out[k] = ev[k]
            out["source"] = article_source(ev["source"], meta["collected_at"])
        else:
            raise CheckError(f"{where}: 알 수 없는 kind {ev['kind']}")
        for sup in ev.get("supporting", []):
            verifier.verify(sup["quote"], sup["source"], f"{where} 보조근거")
        out["is_signal"] = False
        if ev.get("t0"):
            t0_dates.append(out["date"])
        events.append(out)

    if case["case_kind"] == "비관광 급증":
        if t0_dates:
            raise CheckError(f"{cid}: 비관광 급증 사례에는 콘텐츠 기점(t0)이 없어야 한다")
    elif len(t0_dates) != 1:
        raise CheckError(f"{cid}: 콘텐츠 기점(t0)은 정확히 1개여야 한다 (현재 {len(t0_dates)}개)")

    # 신호: 창마다 지표별로 판정. 신호가 없었던 것도 signal_check에 남긴다
    signal_check = []
    primary_signal: str | None = None
    for w in case["signal_windows"]:
        for metric, label in METRICS.items():
            data_end = frames.data_end[metric]
            if pd.Timestamp(w["start"]) > data_end:
                continue
            end = min(pd.Timestamp(w["end"]), data_end).strftime("%Y-%m-%d")
            mx = frames.window_max(metric, region, w["start"], end)
            if mx is None:
                continue
            eps = [e for e in frames.episodes(metric, region, w["start"], end) if e.confirm <= data_end]
            threshold = frames.threshold[metric]
            entry = {
                "metric": label,
                "window_start": w["start"],
                "window_end": end,
                "max_value": round(mx[0], 2),
                "max_date": mx[1].strftime("%Y-%m-%d"),
                "threshold": threshold,
                "signaled": bool(eps),
            }
            note = w.get("note", "")
            if end != w["end"]:
                note = f"{note} (데이터가 {end}까지라 창을 줄임)".strip()
            if note:
                entry["note"] = note
            signal_check.append(entry)

            # 시스템 신호(D-12)는 검색지수다. 외지인 방문자수는 시군구 단위 확인용이라 signal_check에만 남긴다
            if metric != "interest_naver":
                if eps:
                    entry["note"] = f"{entry.get('note', '')} — {eps[0].start:%m/%d}부터 {MIN_DURATION}일 이상 초과".strip(" —")
                continue
            if eps:
                ep = eps[0]
                events.append({
                    "date": ep.confirm.strftime("%Y-%m-%d"),
                    "date_basis": "관측일",
                    "type": "검색 급증",
                    "description": (
                        f"{label} 전년 동요일 대비 배율의 7일 중앙값이 임계({threshold}배)를 "
                        f"{ep.start:%m/%d}부터 {MIN_DURATION}일 연속 초과 — 시스템 신호 확정. "
                        f"구간 최고 {ep.peak:.2f}배({ep.peak_date:%m/%d})"
                    ),
                    "value": round(float(frames.stat[metric].at[ep.confirm, region]), 2),
                    "unit": "배(전년 동요일 대비 7일 중앙값)",
                    "source": db_source(metric, db_retrieved),
                    "is_signal": True,
                })
                if w.get("primary") and primary_signal is None:
                    primary_signal = ep.confirm.strftime("%Y-%m-%d")
            elif w.get("report_unconfirmed"):
                peak = frames.daily_peak(metric, region, w["start"], end)
                if peak and peak[0] >= threshold:
                    days = frames.days_above(metric, region, w["start"], end)
                    reason = (f"7일 중앙값의 임계 초과가 {days}일에 그쳐" if days
                              else "7일 중앙값은 임계를 넘지 않아")
                    events.append({
                        "date": peak[1].strftime("%Y-%m-%d"),
                        "date_basis": "관측일",
                        "type": "검색 급증",
                        "description": (
                            f"{label}가 하루 전년 동요일의 {peak[0]:.1f}배까지 치솟았으나 {reason} "
                            f"{MIN_DURATION}일 지속 조건 미충족 — 신호를 내지 않음"
                        ),
                        "value": round(peak[0], 2),
                        "unit": "배(전년 동요일 대비 일별)",
                        "source": db_source(metric, db_retrieved),
                        "is_signal": False,
                    })

    order = {"외부 요인": 0, "콘텐츠 확산": 1, "검색 급증": 2, "방문 급증": 3, "혼잡 발생": 4, "민원 발생": 5, "조치 시행": 6, "완화": 7}
    events.sort(key=lambda e: (e["date"], order[e["type"]]))

    data: dict = {
        "case_id": cid,
        "region": {"code": region, "name": case["region_name"]},
        "title": case["title"],
        "case_kind": case["case_kind"],
    }
    if "content_type" in case:
        data["content_type"] = case["content_type"]

    caveats = list(case["caveats"])
    lags: dict = {}
    if t0_dates:
        t0 = t0_dates[0]
        lags["content_date"] = t0
        surge = next((e for e in events if e["type"] == "방문 급증" and not e["is_signal"]
                      and e.get("date_basis") in LEAD_TIME_BASES and e["date"] >= t0), None)
        if surge:
            data["lead_time_days"] = days_between(t0, surge["date"])
        if primary_signal:
            lags["signal_date"] = primary_signal
            lags["content_to_signal_days"] = days_between(t0, primary_signal)
        action = next((e for e in events if e["type"] == "조치 시행" and e.get("actor") == "행정"
                       and e.get("is_case_response") and e["date"] >= t0), None)
        if action:
            lags["first_action_date"] = action["date"]
            lags["content_to_action_days"] = days_between(t0, action["date"])
            if primary_signal:
                lags["signal_to_action_days"] = days_between(primary_signal, action["date"])
            if action["date_basis"] == "보도일":
                caveats.append("첫 행정 조치일은 보도일 기준이라 실제 조치는 더 이를 수 있다 — content_to_action_days는 상한값이다.")
        data["lags"] = lags

    data["signal_rule"] = {
        "metric": "네이버 검색지수 (일별)",
        "statistic": "전년 동요일(364일 전) 대비 배율의 최근 7일 중앙값",
        "threshold": frames.threshold["interest_naver"],
        "threshold_basis": f"2024년 전국 {int(PERCENTILE * 100)}백분위 (합성 지역 제외, 사례 지역을 보고 정하지 않음)",
        "min_duration_days": MIN_DURATION,
    }
    data["signal_check"] = signal_check
    data["events"] = events

    caveats += [
        "시스템 신호 규칙은 임시값(D-12)이다. 역할2의 백테스트로 임계와 지속 조건이 바뀔 수 있다.",
        "기사 이벤트는 웹 검색으로 찾은 것이며 전수 조사가 아니다. 더 이른 조치가 보도되지 않았을 수 있다.",
        "유튜브 게시일은 DB에 적재된 시각의 날짜 부분이며, 조회수는 적재 시점 값이다.",
    ]

    all_dates = [e["date"] for e in events] + [w["start"] for w in case["signal_windows"]] + [w["end"] for w in case["signal_windows"]]
    sources = []
    for e in events:
        if e["source"]["name"] not in {s["name"] for s in sources}:
            sources.append(e["source"])

    payload = {
        "_mock": False,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": sources,
        "period": {"start": min(all_dates), "end": max(all_dates), "granularity": "일"},
        "caveat": caveats,
        "data": data,
    }
    return payload, lags


def db_source(metric: str, retrieved: str) -> dict:
    if metric == "interest_naver":
        return {
            "name": "네이버 데이터랩 검색어 트렌드 일별 검색지수",
            "provider": "NAVER — 팀 DB fact_signal(interest_naver)",
            "retrieved_at": retrieved,
            "note": "전년 동요일(364일 전) 대비 배율의 7일 중앙값 (agents/signals.py)",
        }
    return {
        "name": "지역별 방문자수 일별 (외지인)",
        "provider": "한국관광공사 data.go.kr 15101972 — 팀 DB fact_signal(realization_visitors/external)",
        "retrieved_at": retrieved,
        "note": "전년 동요일(364일 전) 대비 배율의 7일 중앙값 (agents/signals.py)",
    }


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def write_handoff(cases: list[dict], results: list[tuple[dict, dict]]) -> None:
    """DB event/event_point 적재 제안본. point_type 대응은 제안이며 데이터 담당 확인이 필요하다."""
    HANDOFF.mkdir(parents=True, exist_ok=True)
    with (HANDOFF / "event.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["event_key", "region_id", "event_name", "event_type", "evidence_url", "evidence_note"])
        for case, (payload, lags) in zip(cases, results):
            events = payload["data"]["events"]
            # 대표 근거: 콘텐츠 기점 이벤트, 기점이 없는 사례는 첫 기사
            t0 = next((e for e in events if e["date"] == lags.get("content_date") and e["type"] == "콘텐츠 확산"), None)
            anchor = t0 or next((e for e in events if "url" in e["source"] and "quote" in e), None)
            url = anchor["source"]["url"] if anchor else ""
            w.writerow([case["case_id"], case["region_code"], case["title"], case["case_kind"], url,
                        f"근거 전체: data/prod/{output_name(case['region_code'])}"])
    with (HANDOFF / "event_point.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["event_key", "point_type", "point_date", "definition_note"])
        for case, (_, lags) in zip(cases, results):
            for point, key, note in [
                ("T0", "content_date", "콘텐츠 기점 (에이전트① t0)"),
                ("Ta", "signal_date", "시스템 신호 확정일 (D-12 규칙) — 제안 대응"),
                ("Tb", "first_action_date", "첫 행정 대응 (is_case_response) — 제안 대응"),
            ]:
                if key in lags:
                    w.writerow([case["case_id"], point, lags[key], note])


def output_name(region: str) -> str:
    return "timeline.json" if region == DEFAULT_REGION else f"timeline_{region}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-sources", action="store_true", help="기사 원문을 받아 인용문·보도일 대조")
    args = parser.parse_args()

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    manifest = json.loads((DB_DIR / "manifest.json").read_text(encoding="utf-8"))
    files = pd.read_csv(DB_DIR / "source_file.csv")
    yt_loaded = str(files.loc[files["file_name"] == "yt_videos_top.csv", "loaded_at"].iloc[0])[:10]
    videos = pd.read_csv(DB_DIR / "youtube_case.csv", dtype={"region_id": str, "published_at": str})
    frames = SignalFrames()
    meta = {"exported_at": manifest["exported_at"], "collected_at": evidence["collected_at"], "youtube_loaded_at": yt_loaded}
    verifier = SourceVerifier(args.verify_sources)

    results = []
    try:
        for case in evidence["cases"]:
            results.append(build_case(case, frames, videos, meta, verifier))
    except CheckError as e:
        sys.exit(f"[검사 실패] {e}")

    for case, (payload, _) in zip(evidence["cases"], results):
        errors = validate_payload("timeline", payload)
        if errors:
            sys.exit(f"[스키마 실패] {case['case_id']}: {errors[:3]}")

    PROD.mkdir(parents=True, exist_ok=True)
    for case, (payload, _) in zip(evidence["cases"], results):
        path = PROD / output_name(case["region_code"])
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_handoff(evidence["cases"], results)

    print(f"임계: 검색 {frames.threshold['interest_naver']}배 / 외지인 방문자 {frames.threshold['realization_visitors']}배 "
          f"(2024 전국 {int(PERCENTILE * 100)}백분위, {MIN_DURATION}일 지속)")
    print(f"원문 대조: {'인용 ' + str(verifier.checked) + '건 통과' if args.verify_sources else '생략 (--verify-sources)'}\n")
    header = f"{'사례':<8}{'지역':<6}{'성격':<8}{'기점':<12}{'신호':<12}{'첫 행정대응':<12}{'기점→신호':>8}{'신호→대응':>8}{'기점→대응':>8}"
    print(header)
    for case, (_, lags) in zip(evidence["cases"], results):
        print(f"{case['case_id']:<8}{case['region_name']:<6}{case['case_kind']:<8}"
              f"{lags.get('content_date', '-'):<12}{lags.get('signal_date', '-'):<12}{lags.get('first_action_date', '-'):<12}"
              f"{lags.get('content_to_signal_days', '-')!s:>8}{lags.get('signal_to_action_days', '-')!s:>8}"
              f"{lags.get('content_to_action_days', '-')!s:>8}")
    print(f"\n출력: data/prod/timeline*.json {len(results)}건, data/handoff/event.csv·event_point.csv")


if __name__ == "__main__":
    main()
