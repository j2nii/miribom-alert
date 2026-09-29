"""Download district-level daily KT visitors from DataLab's official UI.

The downloaded ZIPs remain intact. ``daily_visitors_case.csv`` contains only
local/external visitors and has the same columns as signals_visitors_v2.csv.
No private DataLab JSON endpoint or login credential is used.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path


URL = "https://datalab.visitkorea.or.kr/datalab/portal/bda/getMetcoAna.do"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "raw" / "datalab_daily"
DEFAULT_PROFILE = Path(__file__).resolve().parent / "browser_profile" / "daily"
REGIONS = {
    "48310": ("경상남도", "거제시"),
    "12130": ("전남광주통합", "여수시"),
    "47940": ("경상북도", "울릉군"),
    "51210": ("강원특별자치도", "속초시"),
    "51750": ("강원특별자치도", "영월군"),
    "51810": ("강원특별자치도", "인제군"),
}
SEGMENTS = {"현지인방문자(a)": "1", "외지인방문자(b)": "2"}
EXPECTED_HEADER = ["기준년월", "기초지자체", "방문자 구분", "방문자 수"]
DOWNLOAD_NAME = re.compile(r"^\d{14}_(.+?)_(\d{8})-(\d{8})_데이터랩_다운로드\.zip$")


def parse_day(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def periods(start: date, end: date):
    if end < start:
        raise ValueError("종료일이 시작일보다 빠릅니다")
    day = start
    while day <= end:
        last = min(end, day + timedelta(days=30))
        yield day, last
        day = last + timedelta(days=1)


def zip_path(output: Path, region_id: str, start: date, end: date) -> Path:
    return output / f"{region_id}_{start:%Y%m%d}_{end:%Y%m%d}.zip"


def read_official_zip(path: Path, region_id: str, start: date, end: date) -> list[dict]:
    """Fail closed if the downloaded chart is the wrong region or period."""
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"CSV가 정확히 1개여야 합니다: {path}")
        rows = list(csv.reader(io.StringIO(archive.read(members[0]).decode("utf-8-sig"))))
    if not rows or rows[0] != EXPECTED_HEADER:
        raise ValueError(f"일별 기초지자체 CSV 형식이 아닙니다: {path}")
    city = REGIONS[region_id][1]
    expected_days = {(start + timedelta(days=n)).strftime("%Y%m%d") for n in range((end - start).days + 1)}
    seen = set()
    result = []
    for row in rows[1:]:
        if len(row) != 4 or row[1] != city or row[0] not in expected_days:
            raise ValueError(f"지역·기간이 예상과 다릅니다: {path}: {row}")
        key = (row[0], row[2])
        if key in seen:
            raise ValueError(f"중복 일별 값: {path}: {key}")
        seen.add(key)
        if row[2] not in (*SEGMENTS, "전체방문자(a+b)"):
            raise ValueError(f"알 수 없는 방문자 구분: {row[2]}")
        number = float(row[3])
        if not number.is_integer() or number < 0:
            raise ValueError(f"방문자 값 오류: {row}")
        if row[2] in SEGMENTS:
            result.append({"region": region_id, "date": datetime.strptime(row[0], "%Y%m%d").strftime("%Y-%m-%d"),
                           "tou_div": SEGMENTS[row[2]], "value": int(number)})
    if len(seen) != len(expected_days) * 3:
        raise ValueError(f"일별 값 누락: {path} ({len(seen)} / {len(expected_days) * 3})")
    return result


def merge_downloads(output: Path) -> Path:
    combined = {}
    for path in sorted(output.glob("*.zip")):
        match = re.fullmatch(r"(\d{5})_(\d{8})_(\d{8})\.zip", path.name)
        if not match or match[1] not in REGIONS:
            continue
        start = datetime.strptime(match[2], "%Y%m%d").date()
        end = datetime.strptime(match[3], "%Y%m%d").date()
        for row in read_official_zip(path, match[1], start, end):
            key = (row["region"], row["date"], row["tou_div"])
            if key in combined and combined[key] != row:
                raise ValueError(f"겹치는 다운로드의 값이 다릅니다: {key}")
            combined[key] = row
    for region in sorted({key[0] for key in combined}):
        days = sorted({parse_day(key[1]) for key in combined if key[0] == region})
        expected = (days[-1] - days[0]).days + 1
        if len(days) != expected:
            raise ValueError(f"{region} 일별 구간에 누락이 있습니다: {len(days)} / {expected}일")
        print(f"{region} {days[0]}~{days[-1]} · {len(days)}일")
    target = output / "daily_visitors_case.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["region", "date", "tou_div", "value"])
        writer.writeheader()
        for key in sorted(combined):
            writer.writerow(combined[key])
    print(f"병합: {target} · {len(combined)}행")
    return target


def compare_api_reference(merged: Path, api_file: Path) -> None:
    """Compare only overlapping KT local/external values; API keeps decimals."""
    with merged.open(encoding="utf-8-sig", newline="") as handle:
        downloaded = {(row["region"], row["date"], row["tou_div"]): float(row["value"])
                      for row in csv.DictReader(handle)}
    matched = 0
    exact = 0
    largest = 0.0
    with api_file.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["region"], row["date"], row["tou_div"])
            if key not in downloaded:
                continue
            difference = abs(downloaded[key] - float(row["value"]))
            matched += 1
            exact += difference == 0
            largest = max(largest, difference)
            if difference > 0.5 + 1e-8:
                raise ValueError(f"API와 값이 0.5명 초과하여 다릅니다: {key} · {difference}")
    print(f"API 중복 구간: {matched}건 대조 · 정확히 일치 {exact}건 · 최대 차이 {largest}명")


def select_region(page, region_id: str) -> None:
    province, city = REGIONS[region_id]
    page.locator("#area-select").click()
    if province == "전남광주통합":
        page.get_by_role("button", name=re.compile("전남광주통합")).click()
    else:
        page.get_by_role("button", name=province, exact=True).click()
    page.get_by_role("button", name=city, exact=True).click()
    page.get_by_role("button", name="확인", exact=True).click()
    if city not in page.locator("#area-select").inner_text():
        raise RuntimeError(f"지역 선택 실패: {region_id} {city}")


def download_period(page, output: Path, region_id: str, start: date, end: date) -> Path:
    from playwright.sync_api import expect

    city = REGIONS[region_id][1]
    target = zip_path(output, region_id, start, end)
    if target.exists():
        read_official_zip(target, region_id, start, end)
        print(f"기존 파일 확인: {target.name}")
        return target
    page.locator("#srchAreaDate").select_option(label="일간")
    # The site's start-date onchange resets the end date to one month later.
    # Set both dates together, then let its date validator update hidden fields.
    page.evaluate(
        """({start, end}) => {
            document.querySelector('#dayStart').value = start;
            document.querySelector('#dayEnd').value = end;
            fn_DatSelect(2);
            if (!window.__datalabOriginalClick) {
                window.__datalabOriginalClick = HTMLAnchorElement.prototype.click;
                HTMLAnchorElement.prototype.click = function() {
                    if (this.download && this.href.startsWith('blob:')) {
                        const filename = this.download;
                        window.__datalabDownload = fetch(this.href)
                            .then(response => response.arrayBuffer())
                            .then(buffer => ({filename, bytes: Array.from(new Uint8Array(buffer))}));
                        return;
                    }
                    return window.__datalabOriginalClick.call(this);
                };
            }
        }""",
        {"start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d")},
    )
    expect(page.locator("#dayStart")).to_have_value(start.strftime("%Y%m%d"))
    expect(page.locator("#dayEnd")).to_have_value(end.strftime("%Y%m%d"))
    for attempt in range(1, 4):
        page.get_by_role("button", name="조회", exact=True).click()
        expect(page.get_by_text("로딩 중입니다.").first).to_be_hidden(timeout=60000)
        expect(page.get_by_role("switch", name=city)).to_be_visible(timeout=60000)
        page.evaluate("window.__datalabDownload = null")
        page.locator('a[href="javascript:checkDn(2104);"]').click()
        page.wait_for_function("Boolean(window.__datalabDownload)", timeout=60000)
        result = page.evaluate("async () => await window.__datalabDownload")
        filename = result["filename"]
        match = DOWNLOAD_NAME.fullmatch(filename)
        if match and (match[1], match[2], match[3]) == (city, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")):
            break
        if attempt == 3:
            raise RuntimeError(
                f"조회 결과가 요청한 지역·기간으로 갱신되지 않았습니다: "
                f"{region_id} {start}~{end} · 마지막 다운로드 파일명={filename!r}"
            )
        print(f"이전 조회 결과 감지 ({attempt}/3): {filename} · 재조회")
        page.wait_for_timeout(1000)
    staging = target.with_suffix(".partial.zip")
    try:
        staging.write_bytes(bytes(result["bytes"]))
        read_official_zip(staging, region_id, start, end)
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    print(f"수집: {target.name}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="데이터랩 일별 방문자 공식 CSV 다운로드")
    parser.add_argument("--start", type=parse_day, help="시작일 YYYY-MM-DD")
    parser.add_argument("--end", type=parse_day, help="종료일 YYYY-MM-DD")
    parser.add_argument("--regions", default=",".join(REGIONS), help="쉼표로 구분한 5자리 지역코드")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--browser", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--merge-only", action="store_true", help="기존 공식 ZIP만 검증·병합")
    parser.add_argument("--api-reference", type=Path, help="기존 API 일별 CSV와 중복 날짜 대조")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.merge_only:
        if args.start is None or args.end is None:
            parser.error("수집에는 --start와 --end가 필요합니다")
        selected = [part.strip() for part in args.regions.split(",")]
        if not selected or any(region not in REGIONS for region in selected):
            parser.error("--regions에는 등록된 심층 분석 지역코드만 지정하세요")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            launch = {"user_data_dir": str(args.profile_dir), "headless": False, "accept_downloads": True}
            if args.browser != "chromium":
                launch["channel"] = args.browser
            context = pw.chromium.launch_persistent_context(**launch)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(URL, wait_until="domcontentloaded")
                if not page.get_by_role("link", name="로그아웃").is_visible():
                    print("브라우저에서 데이터랩에 직접 로그인한 뒤 Enter를 누르세요.")
                    input()
                    page.goto(URL, wait_until="domcontentloaded")
                    if not page.get_by_role("link", name="로그아웃").is_visible():
                        raise RuntimeError("로그인 상태를 확인하지 못했습니다")
                page.locator("#area-select").wait_for(timeout=60000)
                for region in selected:
                    select_region(page, region)
                    for start, end in periods(args.start, args.end):
                        download_period(page, args.output_dir, region, start, end)
            finally:
                context.close()
    merged = merge_downloads(args.output_dir)
    if args.api_reference:
        compare_api_reference(merged, args.api_reference)


if __name__ == "__main__":
    main()
