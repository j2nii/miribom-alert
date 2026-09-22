#!/usr/bin/env python3
"""데이터랩 탭 2~5 ZIP을 32열 월별 업데이트 CSV로 병합한다."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


PANEL_COLUMNS = (
    "방문자수", "방문자수_전년동월", "방문자수_증감률", "순방문자수", "숙박자비율",
    "SNS_언급량", "평균숙박일수", "체류시간_분", "체류시간_전국평균_분",
    "숙박방문자비율", "숙박방문자비율_전국평균", "숙박목적지_검색건수",
    "숙박목적지_검색건수_전년동기", "숙박목적지_검색건수_증감률",
    "내비게이션_목적지검색량_전체", "관광소비_내국인_천원", "관광소비_외지인_천원",
    "관광소비_현지인_천원", "전국대비_관광소비_내국인_비율",
    "전국대비_관광소비_외지인_비율", "전국대비_관광소비_현지인_비율",
    "지역화폐_소비금액_천원", "숙박유형별비율_1박", "숙박유형별비율_2박",
    "숙박유형별비율_3박", "숙박유형별비율_4박", "숙박유형별비율_5박",
    "숙박유형별비율_6박", "숙박유형별비율_7박이상", "숙박유형별비율_전체",
)
HEADERS = ("지역", "기준연월", *PANEL_COLUMNS)
ZIP_RE = re.compile(
    r"^(?P<code>(?:\d{2}|\d{5}))_tab(?P<tab>[2-5])_.+_(?P<start>\d{6})_(?P<end>\d{6})\.zip$",
    re.IGNORECASE,
)
OLD_TO_CANONICAL = {
    "29110": "12210", "29140": "12240", "29155": "12270",
    "29170": "12300", "29200": "12330",
    "46110": "12110", "46130": "12130", "46150": "12150",
    "46170": "12170", "46230": "12190",
    "46710": "12710", "46720": "12720", "46730": "12730",
    "46770": "12740", "46780": "12750", "46790": "12760",
    "46800": "12770", "46810": "12780", "46820": "12790",
    "46830": "12800", "46840": "12810", "46860": "12820",
    "46870": "12830", "46880": "12840", "46890": "12850",
    "46900": "12860", "46910": "12870",
}
NEW_CANONICAL_CODES = set(OLD_TO_CANONICAL.values())
ADMIN_REFORM_MONTH = "202607"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="데이터랩 공식 다운로드 ZIP 병합 및 검증",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--downloads", type=Path, default=Path("datalab_downloads"))
    p.add_argument("--periods", default="202401:202506,202507:202608",
                   help="쉼표로 구분한 START:END 목록")
    p.add_argument("--start", default="", help="단일 구간 호환 옵션")
    p.add_argument("--end", default="", help="단일 구간 호환 옵션")
    p.add_argument("--baseline", type=Path, default=Path("../관광_월별패널_259개지역.csv"))
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--expected-regions", type=int, default=0,
                   help="0이면 발견된 지역 수를 사용. 전체 완료 검증 때 사이트 표시 지역 수 입력 가능")
    return p.parse_args()


def parse_periods(args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.start or args.end:
        if not (args.start and args.end):
            raise SystemExit("--start와 --end는 함께 입력해야 합니다.")
        raw_periods = [(args.start, args.end)]
    else:
        raw_periods = []
        for item in args.periods.split(","):
            match = re.fullmatch(r"\s*(\d{6})\s*:\s*(\d{6})\s*", item)
            if not match:
                raise SystemExit(f"기간 형식 오류: {item!r}")
            raw_periods.append(match.groups())

    occupied: set[str] = set()
    periods = []
    for start, end in raw_periods:
        months = month_range(start, end)
        if len(months) > 18:
            raise SystemExit(f"구간별 최대 18개월입니다: {start}~{end}")
        overlap = occupied.intersection(months)
        if overlap:
            raise SystemExit(f"수집 구간의 월이 중복됩니다: {min(overlap)}")
        occupied.update(months)
        periods.append((start, end))
    return periods


def month_range(start: str, end: str) -> list[str]:
    if not re.fullmatch(r"\d{6}", start) or not re.fullmatch(r"\d{6}", end):
        raise SystemExit("--start/--end는 YYYYMM 6자리여야 합니다.")
    sy, sm = int(start[:4]), int(start[4:])
    ey, em = int(end[:4]), int(end[4:])
    if not (1 <= sm <= 12 and 1 <= em <= 12) or (sy, sm) > (ey, em):
        raise SystemExit("조회 기간이 올바르지 않습니다.")
    result = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        result.append(f"{y:04d}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return result


def decode_csv(data: bytes, member: str) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = data.decode(encoding)
            return list(csv.DictReader(io.StringIO(text)))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSV 인코딩을 읽을 수 없습니다: {member}")


def clean(value: str | None) -> str:
    if value is None:
        return ""
    value = value.strip().replace(",", "")
    if value in {"-", "--", "N/A", "null", "None"}:
        return ""
    return value


def clean_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def set_value(rows: dict[str, dict[str, str]], period: str, column: str, value: str | None) -> None:
    if period in rows:
        rows[period][column] = clean(value)


def zip_csvs(path: Path):
    # 수집기가 공식 미제공으로 기록한 빈 SNS 다운로드는 CSV가 없는 정상
    # 결측이다. 다른 탭은 수집 단계에서 빈 파일을 성공 처리하지 않는다.
    if path.stat().st_size < 100:
        return
    with zipfile.ZipFile(path) as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".csv"):
                continue
            yield member, decode_csv(zf.read(member), member)


def parse_tab2(path: Path, rows: dict[str, dict[str, str]]) -> None:
    found = set()
    for name, data in zip_csvs(path):
        if "방문자 수(연인원) 추이" in name:
            found.add("visitors")
            for r in data:
                period = clean(r.get("기준년월"))
                set_value(rows, period, "방문자수", r.get("방문자수"))
                set_value(rows, period, "방문자수_전년동월", r.get("전년동월방문자수"))
                set_value(rows, period, "방문자수_증감률", r.get("방문자수증감률"))
        elif "내비게이션 목적지 유형별 검색량" in name:
            found.add("navigation")
            for r in data:
                if clean_name(r.get("목적지 유형")) == "전체":
                    set_value(rows, clean(r.get("기준연월")), "내비게이션_목적지검색량_전체", r.get("목적지 검색량"))
    if found != {"visitors", "navigation"}:
        raise ValueError(f"탭2 필수 CSV 누락: {path.name} ({sorted(found)})")


def parse_tab3(path: Path, rows: dict[str, dict[str, str]]) -> None:
    found = set()
    stays = {
        "1박": "숙박유형별비율_1박", "2박": "숙박유형별비율_2박",
        "3박": "숙박유형별비율_3박", "4박": "숙박유형별비율_4박",
        "5박": "숙박유형별비율_5박", "6박": "숙박유형별비율_6박",
        "7박이상": "숙박유형별비율_7박이상", "전체": "숙박유형별비율_전체",
    }
    for name, data in zip_csvs(path):
        if "순 방문자 수 및 숙박 비율" in name:
            found.add("unique")
            for r in data:
                p = clean(r.get("기준연월"))
                set_value(rows, p, "순방문자수", r.get("순 방문자수"))
                set_value(rows, p, "숙박자비율", r.get("숙박자 비율"))
        elif "평균 숙박일" in name and "방문자 체류특성" not in name:
            found.add("avg_nights")
            for r in data:
                set_value(rows, clean(r.get("기준연월")), "평균숙박일수", r.get("평균 숙박일수"))
        elif "숙박방문자 비율 추이" in name:
            found.add("overnight")
            for r in data:
                col = "숙박방문자비율_전국평균" if "전국" in clean_name(r.get("지역명")) else "숙박방문자비율"
                set_value(rows, clean(r.get("기준연월")), col, r.get("숙박방문자 비율"))
        elif "평균 체류시간 추이" in name:
            found.add("stay_minutes")
            for r in data:
                col = "체류시간_전국평균_분" if "전국" in clean_name(r.get("지역명")) else "체류시간_분"
                set_value(rows, clean(r.get("기준연월")), col, r.get("체류시간(분)"))
        elif "숙박 목적지 검색건수" in name:
            found.add("lodging_search")
            for r in data:
                p = clean(r.get("기준연월"))
                set_value(rows, p, "숙박목적지_검색건수", r.get("검색건수"))
                set_value(rows, p, "숙박목적지_검색건수_전년동기", r.get("전년동기 검색건수"))
                set_value(rows, p, "숙박목적지_검색건수_증감률", r.get("전년동기 대비 증감률"))
        elif "숙박 유형별 방문자 비율" in name:
            found.add("stay_type")
            for r in data:
                p = clean(r.get("기준연월"))
                for source, target in stays.items():
                    set_value(rows, p, target, r.get(source))
    expected = {"unique", "avg_nights", "overnight", "stay_minutes", "lodging_search", "stay_type"}
    if found != expected:
        raise ValueError(f"탭3 필수 CSV 누락: {path.name} ({sorted(found)})")


def parse_tab4(path: Path, rows: dict[str, dict[str, str]], names: list[str]) -> None:
    found = set()
    spend_cols = {
        "내국인": "관광소비_내국인_천원", "외지인": "관광소비_외지인_천원",
        "현지인": "관광소비_현지인_천원",
    }
    share_cols = {
        "내국인": "전국대비_관광소비_내국인_비율", "외지인": "전국대비_관광소비_외지인_비율",
        "현지인": "전국대비_관광소비_현지인_비율",
    }
    for name, data in zip_csvs(path):
        match = re.search(r"전국 대비 관광소비 추이_(내국인|외지인|현지인)", name)
        if match:
            kind = match.group(1)
            found.add(f"share_{kind}")
            for r in data:
                set_value(rows, clean(r.get("기준연월")), share_cols[kind], r.get("전국 대비 관광소비율"))
                candidate = clean_name(r.get("지역명"))
                if candidate:
                    names.append(candidate)
            continue
        match = re.search(r"관광소비 추이_(내국인|외지인|현지인)", name)
        if match:
            kind = match.group(1)
            found.add(f"spend_{kind}")
            for r in data:
                if clean_name(r.get("업종대분류명")) == "전체":
                    set_value(rows, clean(r.get("기준연월")), spend_cols[kind], r.get("소비액(천원)"))
            continue
        if "지역화폐 관광소비 추이" in name:
            found.add("local_currency")
            for r in data:
                set_value(rows, clean(r.get("기준년월")), "지역화폐_소비금액_천원", r.get("소비금액(천원)"))
                candidate = clean_name(r.get("시도(시군구) 명"))
                if candidate:
                    names.append(candidate)
    # 지역화폐는 모든 지역에서 제공되는 지표가 아니다. 파일이 없으면 해당
    # 열만 NULL로 남기고, 전국 공통 관광소비 6종이 모두 있을 때 정상 처리한다.
    required = {
        "spend_내국인", "spend_외지인", "spend_현지인",
        "share_내국인", "share_외지인", "share_현지인",
    }
    if not required.issubset(found):
        raise ValueError(f"탭4 필수 CSV 누락: {path.name} ({sorted(found)})")


def parse_tab5(path: Path, rows: dict[str, dict[str, str]], names: list[str]) -> None:
    found = False
    for name, data in zip_csvs(path):
        if "SNS 언급량" not in name:
            continue
        found = True
        for r in data:
            set_value(rows, clean(r.get("기준연월")), "SNS_언급량", r.get("검색량(건)"))
            candidate = clean_name(r.get("지역명"))
            if candidate:
                names.append(candidate)
    # 일부 지역·과거기간에는 SNS 자료가 제공되지 않아 공식 ZIP이 비어 있다.
    # 이 경우 지역 전체를 버리지 않고 SNS_언급량만 NULL로 유지한다.


def find_zip_sets(root: Path, start: str, end: str):
    selected: dict[tuple[str, int], Path] = {}
    duplicates = []
    for path in root.rglob("*.zip"):
        match = ZIP_RE.match(path.name)
        if not match or match.group("start") != start or match.group("end") != end:
            continue
        key = (match.group("code"), int(match.group("tab")))
        old = selected.get(key)
        if old:
            keep, drop = (path, old) if path.stat().st_mtime > old.stat().st_mtime else (old, path)
            selected[key] = keep
            duplicates.append(str(drop))
        else:
            selected[key] = path
    grouped = defaultdict(dict)
    for (code, tab), path in selected.items():
        grouped[code][tab] = path
    return dict(grouped), duplicates


def read_baseline(path: Path):
    if not path.is_file():
        return {}, set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {(r["지역"], r["기준연월"]): r for r in rows}, {r["지역"] for r in rows}


def equal_number(a: str, b: str) -> bool:
    if not a and not b:
        return True
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:
        return a == b


def fallback_name(path: Path, code: str) -> str:
    folder = path.parent.name
    prefix = f"{code}_"
    if folder.startswith(prefix):
        return clean_name(folder[len(prefix):].replace("_", " "))
    return code


def preferred_name(candidates: list[str], fallback: str, baseline_names: set[str]) -> str:
    counts = Counter(candidates)
    exact = [name for name in counts if name in baseline_names]
    if exact:
        return sorted(exact, key=lambda n: (-counts[n], -len(n), n))[0]
    # 데이터랩은 일부 동명 지역을 "시도명 시군구명"으로 내려주지만 기존
    # 패널은 "시군구명" 또는 "상위시 시군구명"을 사용한다. 마지막 한 단어만
    # 비교하면 강서구·고성군·포항시 남/북구를 잘못 고를 수 있으므로, 기존
    # 패널 이름 전체가 데이터랩 이름의 유일한 접미사인지 확인한다.
    suffix_matches = {
        baseline_name for baseline_name in baseline_names
        if any(
            candidate == baseline_name or candidate.endswith(" " + baseline_name)
            for candidate in counts
        )
    }
    if len(suffix_matches) == 1:
        return next(iter(suffix_matches))
    if counts:
        return sorted(counts, key=lambda n: (-counts[n], -len(n), n))[0]
    return fallback


def main() -> int:
    args = parse_args()
    periods = parse_periods(args)
    all_months = [m for start, end in periods for m in month_range(start, end)]
    range_start, range_end = min(all_months), max(all_months)
    base = Path(__file__).resolve().parent
    downloads = args.downloads if args.downloads.is_absolute() else (base / args.downloads).resolve()
    baseline_path = args.baseline if args.baseline.is_absolute() else (base / args.baseline).resolve()
    output = args.output or (base / f"datalab_monthly_update_{range_start}_{range_end}.csv")
    report_path = args.report or (base / f"datalab_merge_report_{range_start}_{range_end}.json")
    if not output.is_absolute():
        output = (base / output).resolve()
    if not report_path.is_absolute():
        report_path = (base / report_path).resolve()

    period_groups = {}
    duplicate_zips = []
    for start, end in periods:
        groups, duplicates = find_zip_sets(downloads, start, end)
        if not groups:
            raise SystemExit(f"{start}~{end} 대상 ZIP을 찾지 못했습니다: {downloads}")
        period_groups[(start, end)] = groups
        duplicate_zips.extend(duplicates)

    incomplete = {}
    complete_sets = []
    for (start, end), groups in period_groups.items():
        for code, tabs in groups.items():
            missing = sorted(set(range(2, 6)) - set(tabs))
            if missing:
                incomplete[f"{start}_{end}:{code}"] = missing
            else:
                complete_sets.append((start, end, code, tabs))
    errors = []
    output_rows = []
    parsed = []
    name_candidates: dict[str, list[str]] = defaultdict(list)
    code_fallbacks = {}
    column_missing = Counter()
    baseline, baseline_names = read_baseline(baseline_path)

    for start, end, code, tabs in complete_sets:
        months = month_range(start, end)
        rows = {m: {c: "" for c in PANEL_COLUMNS} for m in months}
        names: list[str] = []
        try:
            parse_tab2(tabs[2], rows)
            parse_tab3(tabs[3], rows)
            parse_tab4(tabs[4], rows, names)
            parse_tab5(tabs[5], rows, names)
            canonical_code = OLD_TO_CANONICAL.get(code, code)
            name_candidates[canonical_code].extend(names)
            code_fallbacks.setdefault(canonical_code, fallback_name(tabs[2], code))
            parsed.append((start, end, code, canonical_code, rows))
        except Exception as exc:
            errors.append({"period": f"{start}_{end}", "region_code": code, "error": str(exc)})

    code_names = {}
    for canonical_code in {item[3] for item in parsed}:
        code_names[canonical_code] = preferred_name(
            name_candidates[canonical_code], code_fallbacks[canonical_code], baseline_names
        )

    merged: dict[tuple[str, str], dict[str, str]] = {}
    merge_conflicts = []
    for start, end, raw_code, canonical_code, rows in parsed:
        for month in month_range(start, end):
            # 광주·전남 행정개편 경계는 구 코드(2026-06까지)와 신 코드
            # (2026-07부터)를 명시적으로 선택한다. 데이터랩이 양쪽 코드에서
            # 과거 값을 함께 반환해도 같은 월에 섞지 않는다.
            if raw_code in OLD_TO_CANONICAL and month >= ADMIN_REFORM_MONTH:
                continue
            if raw_code in NEW_CANONICAL_CODES and month < ADMIN_REFORM_MONTH:
                continue
            key = (canonical_code, month)
            target = merged.setdefault(key, {c: "" for c in PANEL_COLUMNS})
            for col in PANEL_COLUMNS:
                value = rows[month][col]
                if not value:
                    continue
                if target[col] and not equal_number(target[col], value):
                    merge_conflicts.append({
                        "canonical_code": canonical_code, "raw_code": raw_code,
                        "period": month, "column": col, "existing": target[col], "incoming": value,
                    })
                else:
                    target[col] = value

    for (canonical_code, month), values in merged.items():
        row = {"지역": code_names[canonical_code], "기준연월": month, **values}
        output_rows.append(row)
        for col in PANEL_COLUMNS:
            if not row[col]:
                    column_missing[col] += 1

    keys = [(r["지역"], r["기준연월"]) for r in output_rows]
    duplicate_keys = sorted(k for k, count in Counter(keys).items() if count > 1)
    overlap_cells = 0
    changed_cells = []
    for row in output_rows:
        old = baseline.get((row["지역"], row["기준연월"]))
        if not old:
            continue
        for col in PANEL_COLUMNS:
            if not row[col] or not old.get(col, ""):
                continue
            overlap_cells += 1
            if not equal_number(row[col], clean(old.get(col))):
                changed_cells.append({
                    "region": row["지역"], "period": row["기준연월"], "column": col,
                    "new": row[col], "old": clean(old.get(col)),
                })

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(sorted(output_rows, key=lambda r: (r["지역"], r["기준연월"])))

    unmatched_baseline_regions = (
        sorted(set(code_names.values()) - baseline_names) if baseline_names else []
    )
    report = {
        "periods": [f"{start}_{end}" for start, end in periods],
        "range": f"{range_start}_{range_end}",
        "download_root": str(downloads),
        "zip_region_period_sets_found": sum(len(groups) for groups in period_groups.values()),
        "complete_region_period_sets": len(complete_sets),
        "incomplete_regions": incomplete,
        "parse_errors": errors,
        "output_rows": len(output_rows),
        "output_region_names": len(set(r["지역"] for r in output_rows)),
        "duplicate_output_keys": [list(x) for x in duplicate_keys],
        "administrative_merge_conflicts_count": len(merge_conflicts),
        "administrative_merge_conflicts_sample": merge_conflicts[:100],
        "duplicate_zip_files_ignored": duplicate_zips,
        "unmatched_baseline_regions": unmatched_baseline_regions,
        "baseline_overlap_nonblank_cells": overlap_cells,
        "baseline_changed_cells_count": len(changed_cells),
        "baseline_changed_cells_by_column": dict(
            Counter(item["column"] for item in changed_cells)
        ),
        "baseline_changed_cells_by_period": dict(
            Counter(item["period"] for item in changed_cells)
        ),
        "baseline_changed_cells_sample": changed_cells[:100],
        "missing_values_by_column": dict(column_missing),
        "output_file": str(output),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ZIP] {len(periods)}개 구간 · 지역-구간 {report['zip_region_period_sets_found']:,}세트 · 4개 탭 완비 {len(complete_sets):,}세트")
    print(f"[병합] {len(output_rows):,}행 · 지역명 {report['output_region_names']:,}개 · {range_start}~{range_end}")
    print(f"[대조] 기존 패널 비어 있지 않은 셀 {overlap_cells:,}개 비교 · 변경 {len(changed_cells):,}개")
    print(f"[출력] {output}")
    print(f"[보고서] {report_path}")
    if column_missing:
        print("[결측 상위] " + ", ".join(f"{k}={v:,}" for k, v in column_missing.most_common(6)))

    fatal = bool(incomplete or errors or duplicate_keys or merge_conflicts or unmatched_baseline_regions)
    if args.expected_regions and report["output_region_names"] != args.expected_regions:
        print(f"[오류] 기대 지역 {args.expected_regions:,}개와 결과 {report['output_region_names']:,}개가 다릅니다.")
        fatal = True
    if incomplete:
        print(f"[오류] 탭 누락 지역 {len(incomplete):,}개. 03_retry_failed.cmd 실행 후 다시 병합하세요.")
    if errors:
        print(f"[오류] 파싱 실패 지역 {len(errors):,}개. 보고서를 확인하세요.")
    if duplicate_keys:
        print(f"[오류] 지역명·월 중복 키 {len(duplicate_keys):,}개. 자동 적재하지 마세요.")
    if merge_conflicts:
        print(f"[오류] 행정개편 전후 값 충돌 {len(merge_conflicts):,}개. 보고서를 확인하세요.")
    if unmatched_baseline_regions:
        print(
            f"[오류] 기존 패널과 연결되지 않은 지역명 {len(unmatched_baseline_regions):,}개: "
            + ", ".join(unmatched_baseline_regions[:10])
        )
    return 2 if fatal else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, zipfile.BadZipFile, csv.Error) as exc:
        sys.exit(f"파일 처리 실패: {exc}")
