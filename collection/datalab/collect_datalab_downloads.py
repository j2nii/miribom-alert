#!/usr/bin/env python3
"""한국관광 데이터랩 공식 '전체 다운로드' 버튼 자동화 수집기.

브라우저 프로필에 저장된 자동완성 정보가 있으면 세션 만료 후 자동으로 다시
로그인한다. 내부 JSON API를 직접 호출하지 않고, 사이트가 제공하는
지역 선택/조회/전체 다운로드 UI만 조작한다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


URL = "https://datalab.visitkorea.or.kr/datalab/portal/loc/getAreaDataForm.do"
LOGIN_URL = "https://datalab.visitkorea.or.kr/datalab/portal/mbr/getMbrLoginForm.do"
# 사이트 화면의 sessionTimeout은 3,600초다. 긴 다운로드 중 경계에 걸리지
# 않도록 30분마다 페이지를 다시 열어 세션을 확인하고 필요하면 재로그인한다.
SESSION_REFRESH_SEC = 30 * 60
SESSION_REFRESH_AT: dict[int, float] = {}
TAB_NAMES = {
    1: "종합분석",
    2: "방문자",
    3: "숙박_체류시간",
    4: "관광소비",
    5: "소셜미디어",
    6: "인기관광지",
    7: "유입_유출지역",
    8: "유사지역",
    9: "지역집중률",
}
SIDO_NAMES = {
    "11": "서울특별시",
    "12": "전남광주통합특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "43": "충청북도",
    "44": "충청남도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
    "51": "강원특별자치도",
    "52": "전북특별자치도",
}


@dataclass(frozen=True)
class Region:
    region_code: str
    region_name: str
    sido_code: str
    sido_name: str


@dataclass
class Result:
    timestamp: str
    region_code: str
    region_name: str
    sido_code: str
    tab: int
    tab_name: str
    period: str
    status: str
    attempt: int
    file_path: str = ""
    file_size: int = 0
    elapsed_sec: float = 0.0
    error: str = ""


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="한국관광 데이터랩 지역별 공식 다운로드 자동화",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start", default="202401", help="시작월 YYYYMM")
    p.add_argument("--end", default="202506", help="종료월 YYYYMM")
    p.add_argument(
        "--tabs",
        default="2,3,4,5",
        help="수집 탭 번호. 32개 월별 지표 갱신은 2,3,4,5",
    )
    p.add_argument(
        "--regions",
        default="auto",
        help="지역 목록 CSV. auto이면 로그인 후 데이터랩의 최신 지역 목록을 자동 탐색",
    )
    p.add_argument("--output-dir", default="datalab_downloads", help="다운로드 폴더")
    p.add_argument("--profile-dir", default=".datalab_browser", help="로그인 유지용 브라우저 프로필")
    p.add_argument("--limit", type=int, default=0, help="앞 N개 지역만 시험. 0은 전체")
    p.add_argument("--start-at", default="", help="이 지역코드부터 시작")
    p.add_argument("--only-failed", action="store_true", help="이전 실패 항목만 재시도")
    p.add_argument("--retries", type=int, default=2, help="항목별 추가 재시도 횟수")
    p.add_argument("--timeout", type=int, default=120, help="조회/다운로드 제한시간(초)")
    p.add_argument("--delay", type=float, default=2.0, help="다운로드 사이 대기시간(초)")
    p.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
        help="이 횟수만큼 연속 실패하면 사이트 차단/장애로 보고 안전 중단",
    )
    p.add_argument("--browser", choices=["chrome", "msedge", "chromium"], default="chrome")
    return p.parse_args()


def validate_yyyymm(value: str, label: str) -> None:
    if not re.fullmatch(r"\d{6}", value):
        raise SystemExit(f"{label}은 YYYYMM 6자리여야 합니다: {value!r}")
    year, month = int(value[:4]), int(value[4:])
    if not (2020 <= year <= 2100 and 1 <= month <= 12):
        raise SystemExit(f"{label} 값이 올바르지 않습니다: {value!r}")


def month_count(start: str, end: str) -> int:
    sy, sm = int(start[:4]), int(start[4:])
    ey, em = int(end[:4]), int(end[4:])
    return (ey - sy) * 12 + em - sm + 1


def parse_tabs(raw: str) -> list[int]:
    try:
        tabs = list(dict.fromkeys(int(x.strip()) for x in raw.split(",") if x.strip()))
    except ValueError as exc:
        raise SystemExit("--tabs는 2,3,4,5처럼 쉼표로 입력하세요.") from exc
    invalid = [x for x in tabs if x not in TAB_NAMES]
    if not tabs or invalid:
        raise SystemExit(f"지원하지 않는 탭 번호: {invalid or raw}")
    return tabs


def read_regions(path: Path) -> list[Region]:
    if not path.exists():
        raise SystemExit(
            f"지역 목록을 찾을 수 없습니다: {path}\n"
            "datalab_collector 폴더에서 실행했는지 확인하세요."
        )
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path}에 지역 데이터가 없습니다.")
    result = []
    if {"region", "name", "시도코드"}.issubset(rows[0]):
        # 기존 프로젝트의 region_master.csv 형식. 합산용 비표준 코드는 원천
        # 다운로드 대상이 아니므로 숫자 5자리 코드만 수집한다.
        for row in rows:
            code = row["region"].strip()
            sido = row["시도코드"].strip()
            if code.isdigit() and len(code) == 5 and sido in SIDO_NAMES:
                result.append(Region(code, row["name"].strip(), sido, SIDO_NAMES[sido]))
    elif {"region_code", "region_name", "sido_code", "sido_name", "enabled"}.issubset(rows[0]):
        for row in rows:
            if row["enabled"].strip().lower() not in {"1", "true", "y", "yes"}:
                continue
            code = row["region_code"].strip()
            sido = row["sido_code"].strip()
            if code.isdigit() and len(code) == 5 and sido.isdigit() and len(sido) == 2:
                result.append(Region(code, row["region_name"].strip(), sido, row["sido_name"].strip()))
    else:
        raise SystemExit(
            f"{path}의 열이 올바르지 않습니다. region_master.csv 또는 "
            "region_code/region_name/sido_code/sido_name/enabled 형식이 필요합니다."
        )
    if not result:
        raise SystemExit("수집 대상으로 활성화된 숫자 지역코드가 없습니다.")
    return result


def discover_regions(page: Page, timeout_ms: int, start: str, end: str) -> list[Region]:
    """로그인된 지역 선택 팝업에서 현재 제공되는 전체 지역을 읽는다."""
    page.locator("#area-select").click()
    modal = page.locator("#popup1")
    modal.wait_for(state="visible", timeout=timeout_ms)

    sido_rows: list[tuple[str, str]] = []
    for anchor in page.locator("#srchNatCdList1 a").all():
        onclick = anchor.get_attribute("onclick") or ""
        match = re.search(r"funChangeSido\(['\"](\d{2})['\"]", onclick)
        if match:
            sido_rows.append((match.group(1), (anchor.text_content() or "").strip()))
    if not sido_rows:
        raise RuntimeError("지역 선택 창에서 시도 목록을 읽지 못했습니다.")

    regions: list[Region] = []
    seen: set[str] = set()
    for sido_code, sido_name in sido_rows:
        # 2026-07 개편 이전 구간은 구 광주(29)·전남(46)을, 개편 이후
        # 구간은 통합 시도(12)를 쓴다. 개편일을 가로지르면 셋 모두 받아
        # 병합 단계에서 12xxx 정본 코드로 연결한다.
        if end < "202607" and sido_code == "12":
            continue
        if start >= "202607" and sido_code in {"29", "46"}:
            continue
        selector = (
            "#srchNatCdList1 a[onclick*="
            + '"'
            + f"funChangeSido('{sido_code}'"
            + '"'
            + "]"
        )
        page.locator(selector).click()
        # 세종은 사이트가 시도 자체(코드 36)를 분석 단위로 사용하며
        # 시군구 목록 API가 빈 배열을 반환한다.
        if sido_code == "36":
            page.wait_for_timeout(500)
            regions.append(Region("36", "세종특별자치시", "36", sido_name or "세종특별자치시"))
            seen.add("36")
            continue
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            onclicks = page.locator("#srchSidoCdList1 a").evaluate_all(
                "els => els.map(el => el.getAttribute('onclick') || '')"
            )
            if any(re.search(r"getSrchFrm\(['\"]" + re.escape(sido_code), x) for x in onclicks):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"{sido_name or sido_code} 지역 목록 갱신을 기다리다 시간 초과했습니다.")
        for anchor in page.locator("#srchSidoCdList1 a").all():
            onclick = anchor.get_attribute("onclick") or ""
            match = re.search(r"getSrchFrm\(['\"](\d{5})['\"]", onclick)
            if not match:
                continue
            intg_match = re.search(r",\s*['\"]([YN])['\"]\s*\)\s*;?", onclick)
            # 수원시·화성시 같은 통합 상위 시(Y)와 하위 일반구를 함께
            # 받으면 이중 계상된다. 기존 259개 패널과 동일하게 상위 시는 제외한다.
            if intg_match and intg_match.group(1) == "Y":
                continue
            code = match.group(1)
            if code in seen:
                continue
            name = re.sub(r"\s+", " ", (anchor.text_content() or "").strip())
            if name:
                regions.append(Region(code, name, sido_code, sido_name or SIDO_NAMES.get(sido_code, sido_code)))
                seen.add(code)

    if not regions:
        raise RuntimeError("지역 선택 창에서 기초지자체 목록을 읽지 못했습니다.")

    # 팝업을 정상적으로 닫기 위해 첫 지역을 임시 선택한다. 실제 수집 직전에는
    # choose_region()이 각 대상 지역을 다시 선택한다.
    first = regions[0]
    sido_selector = (
        "#srchNatCdList1 a[onclick*=" + '"' + f"funChangeSido('{first.sido_code}'" + '"' + "]"
    )
    page.locator(sido_selector).click()
    page.locator("#srchSidoCdList1 a").first.wait_for(state="visible", timeout=timeout_ms)
    region_selector = (
        "#srchSidoCdList1 a[onclick*=" + '"' + f"getSrchFrm('{first.region_code}'" + '"' + "]"
    )
    page.locator(region_selector).click()
    modal.locator(".modal-foot a.btn-primary").click()
    modal.wait_for(state="hidden", timeout=timeout_ms)
    return regions


def sanitize_filename(text: str) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", text)
    return re.sub(r"\s+", "_", text).strip("._") or "download"


def progress_key(region_code: str, tab: int, period: str) -> str:
    return f"{region_code}|{tab}|{period}"


class Progress:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.latest: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    key = progress_key(row["region_code"], int(row["tab"]), row["period"])
                    self.latest[key] = row
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

    def append(self, result: Result) -> None:
        row = asdict(result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.latest[progress_key(result.region_code, result.tab, result.period)] = row

    def successful(self, region_code: str, tab: int, period: str) -> bool:
        row = self.latest.get(progress_key(region_code, tab, period))
        if not row or row.get("status") != "success":
            return False
        path = Path(row.get("file_path", ""))
        if not path.exists():
            return False
        if row.get("error") == "official_no_data":
            return True
        return path.stat().st_size >= 100

    def failed(self, region_code: str, tab: int, period: str) -> bool:
        row = self.latest.get(progress_key(region_code, tab, period))
        return bool(row and row.get("status") == "failed")


def wait_loading(page: Page, timeout_ms: int) -> None:
    # 조회 직후 로딩 레이어가 표시되기 전에 hidden 판정이 끝나는 경쟁조건을 피한다.
    page.wait_for_timeout(500)
    for selector in ("#loading", "#loadingSpin"):
        try:
            page.locator(selector).wait_for(state="hidden", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            # 사이트에서 숨김 처리가 누락되는 경우가 있어 핵심 컨트롤 활성 여부로 재확인한다.
            if not page.locator("#download").is_enabled():
                raise


def ensure_page_ready(page: Page, timeout_ms: int) -> None:
    page.locator("#area-select").wait_for(state="visible", timeout=timeout_ms)
    page.locator("#monthStart").wait_for(state="visible", timeout=timeout_ms)
    page.locator("#download").wait_for(state="attached", timeout=timeout_ms)
    wait_loading(page, timeout_ms)


def login_link_visible(page: Page) -> bool:
    links = page.get_by_text("로그인", exact=True)
    return links.count() > 0 and links.first.is_visible()


def login_required(page: Page) -> bool:
    """로그인 페이지 리디렉션·로그인 폼·상단 로그인 링크를 함께 확인한다."""
    try:
        if "getMbrLoginForm.do" in page.url:
            return True
        login_form = page.locator("#mbrId, #mbrPw")
        if login_form.count() > 0 and login_form.first.is_visible():
            return True
        return login_link_visible(page)
    except Exception:
        return True


def mark_session_refresh(page: Page) -> None:
    SESSION_REFRESH_AT[id(page)] = time.monotonic()


def session_refresh_due(page: Page) -> bool:
    refreshed_at = SESSION_REFRESH_AT.get(id(page), 0.0)
    return time.monotonic() - refreshed_at >= SESSION_REFRESH_SEC


def try_saved_password_login(page: Page, timeout_ms: int) -> bool:
    """브라우저 프로필이 자동완성한 값만 이용해 로그인한다.

    아이디나 비밀번호를 코드·로그·설정 파일에서 읽지 않는다. 자동완성 값이
    없거나 로그인이 실패하면 False를 반환해 기존 수동 로그인으로 전환한다.
    """
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        user_input = page.locator("#mbrId")
        password_input = page.locator("#mbrPw")
        user_input.wait_for(state="visible", timeout=timeout_ms)
        password_input.wait_for(state="visible", timeout=timeout_ms)

        # Chrome 비밀번호 관리자가 포커스를 받은 뒤 값을 채우는 경우도 있어
        # 두 입력칸을 한 번씩 포커스하고 최대 20초간 값이 나타나기를 기다린다.
        user_input.click()
        password_input.click()
        deadline = time.time() + 20
        while time.time() < deadline:
            if user_input.input_value() and password_input.input_value():
                break
            page.wait_for_timeout(500)
        else:
            print("[자동 로그인] 브라우저 자동완성 값을 확인하지 못했습니다.")
            return False

        print("[자동 로그인] 브라우저에 저장된 자동완성 정보로 로그인을 시도합니다.")
        submit = page.locator('input[type="submit"][value="로그인"], button:has-text("로그인")')
        if submit.count() > 0:
            submit.first.click()
        else:
            password_input.press("Enter")

        # 로그인 폼이 사라지거나 다른 화면으로 이동할 때까지 기다린다.
        deadline = time.time() + min(timeout_ms / 1000, 30)
        while time.time() < deadline:
            form_visible = (
                page.locator("#mbrId").count() > 0
                and page.locator("#mbrId").first.is_visible()
            )
            if not form_visible and "getMbrLoginForm.do" not in page.url:
                break
            page.wait_for_timeout(500)
        else:
            return False

        page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
        if login_required(page):
            return False
        ensure_page_ready(page, timeout_ms)
        mark_session_refresh(page)
        print("[자동 로그인] 완료했습니다. 수집을 계속합니다.")
        return True
    except Exception as exc:
        print(f"[자동 로그인 실패] {exc}")
        return False


def ensure_logged_in(page: Page, timeout_ms: int) -> None:
    """세션이 만료됐으면 대량 실패를 쌓지 않고 사용자의 재로그인을 기다린다."""
    if not login_required(page):
        return
    if try_saved_password_login(page, timeout_ms):
        return
    print("\n[일시정지] 데이터랩 로그인 세션이 만료됐습니다.")
    print("브라우저에서 다시 로그인하고 지역별 관광현황 화면으로 돌아오세요.")
    print("브라우저 창은 닫지 마세요. 최소화는 괜찮습니다.")
    input("준비가 끝났으면 브라우저를 열어 둔 채 이 창에서 Enter를 누르세요: ")
    page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
    if login_required(page):
        raise RuntimeError("로그인 상태를 확인하지 못했습니다.")
    ensure_page_ready(page, timeout_ms)
    mark_session_refresh(page)


def recovery_wait(attempt: int) -> int:
    """짧은 장애나 요청 제한에 연속 재요청하지 않도록 점진적으로 기다린다."""
    return min(60, 5 * (2 ** max(0, attempt - 1)))


def choose_region(page: Page, region: Region, timeout_ms: int) -> None:
    page.locator("#area-select").click()
    modal = page.locator("#popup1")
    modal.wait_for(state="visible", timeout=timeout_ms)

    sido_selector = f"#srchNatCdList1 a[onclick*=" + '"' + f"funChangeSido('{region.sido_code}'" + '"' + "]"
    page.locator(sido_selector).click()

    if region.region_code == "36" and region.sido_code == "36":
        # 세종은 오른쪽 시군구 목록 없이 시도 버튼 선택만으로 tmpSggCd가
        # 36으로 설정되고, 확인(popSet1)에서 실제 검색 코드가 반영된다.
        modal.locator(".modal-foot a.btn-primary").click()
        modal.wait_for(state="hidden", timeout=timeout_ms)
        selected = page.locator("#sggCd").input_value()
        if selected != "36":
            raise RuntimeError(f"세종 지역 선택 불일치: 화면={selected}")
        return

    region_selector = f"#srchSidoCdList1 a[onclick*=" + '"' + f"getSrchFrm('{region.region_code}'" + '"' + "]"
    page.locator(region_selector).wait_for(state="visible", timeout=timeout_ms)
    page.locator(region_selector).click()
    modal.locator(".modal-foot a.btn-primary").click()
    modal.wait_for(state="hidden", timeout=timeout_ms)

    selected = page.locator("#sggCd").input_value()
    if selected != region.region_code:
        raise RuntimeError(f"지역 선택 불일치: 요청={region.region_code}, 화면={selected}")


def set_period_and_query(page: Page, start: str, end: str, timeout_ms: int) -> None:
    page.locator("#lookupDate").select_option("1")
    page.locator("#monthStart").fill(start)
    page.locator("#monthStart").press("Tab")
    page.locator("#monthEnd").fill(end)
    page.locator("#monthEnd").press("Tab")
    page.locator('#searchWrap input[type="submit"][value="조회"]').click()
    wait_loading(page, timeout_ms)


def select_tab(page: Page, tab: int, timeout_ms: int) -> None:
    if page.locator("#tabDiv").input_value() == str(tab):
        return
    anchor = page.locator(f"#tab{tab} > a")
    anchor.click()
    page.locator("#tabDiv").wait_for(state="attached", timeout=timeout_ms)
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if page.locator("#tabDiv").input_value() == str(tab):
            break
        time.sleep(0.2)
    else:
        raise TimeoutError(f"탭 전환 실패: {tab}")
    wait_loading(page, timeout_ms)


def download_tab(
    page: Page,
    region: Region,
    tab: int,
    start: str,
    end: str,
    output_dir: Path,
    timeout_ms: int,
) -> Path:
    target_dir = output_dir / f"{start}_{end}" / f"{region.region_code}_{sanitize_filename(region.region_name)}"
    target_dir.mkdir(parents=True, exist_ok=True)
    with page.expect_download(timeout=timeout_ms) as event:
        page.locator("#download").click()
    download = event.value
    original = sanitize_filename(download.suggested_filename)
    suffix = Path(original).suffix or ".bin"
    target = target_dir / f"{region.region_code}_tab{tab}_{TAB_NAMES[tab]}_{start}_{end}{suffix}"
    download.save_as(str(target))
    if not target.exists() or target.stat().st_size < 100:
        # 일부 지역·과거기간의 SNS 탭은 사이트가 정상 다운로드 이벤트 후
        # 빈 ZIP(또는 0바이트 파일)을 반환한다. 같은 요청을 반복해도 값이
        # 생기지 않으므로 공식 미제공으로 기록하고 병합에서는 NULL로 둔다.
        if tab == 5 and target.exists():
            return target.resolve()
        raise RuntimeError(f"다운로드 파일이 비어 있습니다: {target}")
    return target.resolve()


def dialog_handler(dialog) -> None:
    print(f"\n[사이트 알림] {dialog.message}")
    dialog.accept()


def close_context_quietly(context) -> None:
    """이미 종료된 브라우저 컨텍스트도 안전하게 정리한다."""
    if context is None:
        return
    try:
        context.close()
    except Exception:
        pass


def launch_ready_session(pw, args, profile_dir: Path, timeout_ms: int, reason: str = ""):
    """브라우저를 시작하고 로그인된 데이터랩 화면까지 준비한다.

    사용자가 창을 닫았거나 Chrome 자체가 종료된 경우에도 같은 영구 프로필로
    다시 열 수 있도록 시작 과정을 한곳에 모은다.
    """
    last_error = None
    for launch_attempt in range(1, 4):
        context = None
        try:
            if reason:
                suffix = f" ({launch_attempt}/3)" if launch_attempt > 1 else ""
                print(f"  [브라우저 다시 열기] {reason}{suffix}")
            launch_args = {
                "user_data_dir": str(profile_dir),
                "headless": False,
                "accept_downloads": True,
            }
            if args.browser == "chromium":
                context = pw.chromium.launch_persistent_context(**launch_args)
            else:
                context = pw.chromium.launch_persistent_context(channel=args.browser, **launch_args)
            page = context.pages[0] if context.pages else context.new_page()
            page.on("dialog", dialog_handler)
            page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
            ensure_logged_in(page, timeout_ms)
            ensure_page_ready(page, timeout_ms)
            mark_session_refresh(page)
            return context, page
        except KeyboardInterrupt:
            close_context_quietly(context)
            raise
        except Exception as exc:
            last_error = exc
            close_context_quietly(context)
            if launch_attempt >= 3:
                break
            wait_sec = 3 * launch_attempt
            print(f"  [브라우저 시작 재시도] {exc} · {wait_sec}초 후 다시 시도")
            time.sleep(wait_sec)
    raise RuntimeError(f"브라우저를 다시 준비하지 못했습니다: {last_error}")


def recover_ready_page(pw, args, profile_dir: Path, context, page, timeout_ms: int):
    """현재 페이지를 복구하고, 닫혀 있으면 브라우저 자체를 재실행한다."""
    try:
        if not page.is_closed():
            page.goto(URL, wait_until="domcontentloaded", timeout=timeout_ms)
            ensure_logged_in(page, timeout_ms)
            ensure_page_ready(page, timeout_ms)
            mark_session_refresh(page)
            return context, page
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"  [현재 브라우저 복구 불가] {exc}")

    close_context_quietly(context)
    # Chrome 프로세스와 프로필 잠금 파일이 완전히 정리될 짧은 시간을 준다.
    time.sleep(2)
    return launch_ready_session(
        pw, args, profile_dir, timeout_ms,
        reason="창이 닫혔거나 연결이 끊겨 자동 복구합니다.",
    )


def iter_targets(
    regions: Iterable[Region],
    tabs: list[int],
    progress: Progress,
    period: str,
    only_failed: bool,
) -> Iterable[tuple[Region, list[int]]]:
    for region in regions:
        needed = []
        for tab in tabs:
            if progress.successful(region.region_code, tab, period):
                continue
            if only_failed and not progress.failed(region.region_code, tab, period):
                continue
            needed.append(tab)
        if needed:
            yield region, needed


def write_summary(progress: Progress, path: Path) -> None:
    rows = sorted(progress.latest.values(), key=lambda r: (r.get("region_code", ""), int(r.get("tab", 0))))
    fields = [f.name for f in Result.__dataclass_fields__.values()]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    args = parse_args()
    validate_yyyymm(args.start, "--start")
    validate_yyyymm(args.end, "--end")
    months = month_count(args.start, args.end)
    if months < 1 or months > 18:
        raise SystemExit(f"월간 조회 범위는 1~18개월이어야 합니다. 현재 {months}개월")

    base = Path(__file__).resolve().parent
    output_dir = (base / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    profile_dir = (base / args.profile_dir).resolve() if not Path(args.profile_dir).is_absolute() else Path(args.profile_dir)
    tabs = parse_tabs(args.tabs)
    period = f"{args.start}_{args.end}"
    progress = Progress(output_dir / "progress.jsonl")
    print(f"[기간] {args.start}~{args.end} ({months}개월)")
    print(f"[저장] {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timeout_ms = args.timeout * 1000
    completed = 0
    failed = 0

    with sync_playwright() as pw:
        try:
            context, page = launch_ready_session(pw, args, profile_dir, timeout_ms)
        except RuntimeError:
            raise SystemExit("로그인 상태를 확인하지 못했습니다. 로그인 후 다시 실행하세요.")

        if args.regions.strip().lower() == "auto":
            # 지역 목록 경고와 제공 범위가 조회기간에 따라 달라지므로,
            # 개편 영향이 없는 종로구로 기간을 먼저 적용한 뒤 목록을 읽는다.
            seed = Region("11110", "종로구", "11", "서울특별시")
            choose_region(page, seed, timeout_ms)
            set_period_and_query(page, args.start, args.end, timeout_ms)
            print("[지역] 데이터랩의 최신 지역 목록을 확인합니다.")
            regions = discover_regions(page, timeout_ms, args.start, args.end)
        else:
            regions_path = Path(args.regions)
            if not regions_path.is_absolute():
                regions_path = (base / regions_path).resolve()
            regions = read_regions(regions_path)

        if args.start_at:
            codes = [r.region_code for r in regions]
            if args.start_at not in codes:
                close_context_quietly(context)
                raise SystemExit(f"--start-at 지역코드가 목록에 없습니다: {args.start_at}")
            regions = regions[codes.index(args.start_at):]
        if args.limit > 0:
            regions = regions[: args.limit]

        targets = list(iter_targets(regions, tabs, progress, period, args.only_failed))
        total_items = sum(len(t) for _, t in targets)
        print(f"[대상] 전체 지역 {len(regions):,}개 · 미완료 지역 {len(targets):,}개 · 다운로드 {total_items:,}건 · 탭 {tabs}")
        if not targets:
            print("수집할 미완료 항목이 없습니다.")
            close_context_quietly(context)
            return 0

        consecutive_failures = 0
        stop_requested = False
        for region_index, (region, needed_tabs) in enumerate(targets, start=1):
            print(f"\n[{region_index}/{len(targets)}] {region.sido_name} {region.region_name} ({region.region_code})")
            setup_error = None
            for setup_attempt in range(1, args.retries + 2):
                try:
                    if session_refresh_due(page):
                        print("  [세션 확인] 30분이 지나 페이지를 다시 열고 로그인 상태를 확인합니다.")
                        context, page = recover_ready_page(
                            pw, args, profile_dir, context, page, timeout_ms
                        )
                    choose_region(page, region, timeout_ms)
                    set_period_and_query(page, args.start, args.end, timeout_ms)
                    setup_error = None
                    break
                except Exception as exc:
                    setup_error = exc
                    print(f"  [지역 설정 재시도 {setup_attempt}/{args.retries + 1}] {exc}")
                    if setup_attempt <= args.retries:
                        wait_sec = recovery_wait(setup_attempt)
                        print(f"  [복구 대기] {wait_sec}초")
                        time.sleep(wait_sec)
                        try:
                            context, page = recover_ready_page(
                                pw, args, profile_dir, context, page, timeout_ms
                            )
                        except Exception as recovery_exc:
                            print(f"  [복구 준비 실패] {recovery_exc}")
            if setup_error is not None:
                for tab in needed_tabs:
                    result = Result(
                        now_text(), region.region_code, region.region_name, region.sido_code,
                        tab, TAB_NAMES[tab], period, "failed", args.retries + 1,
                        error=f"지역/기간 설정 실패: {setup_error}",
                    )
                    progress.append(result)
                    failed += 1
                consecutive_failures += len(needed_tabs)
                print(f"  [실패] 지역/기간 설정: {setup_error}")
                write_summary(progress, output_dir / "progress_summary.csv")
                if consecutive_failures >= args.max_consecutive_failures:
                    print(f"\n[안전 중단] 연속 실패 {consecutive_failures}건. 사이트 상태와 로그인을 확인하세요.")
                    stop_requested = True
                    break
                continue

            for tab in needed_tabs:
                success = False
                last_error = "알 수 없는 오류"
                for attempt in range(1, args.retries + 2):
                    started = time.time()
                    try:
                        if session_refresh_due(page):
                            print("  [세션 확인] 30분이 지나 로그인 상태를 확인하고 현재 지역을 복원합니다.")
                            context, page = recover_ready_page(
                                pw, args, profile_dir, context, page, timeout_ms
                            )
                            choose_region(page, region, timeout_ms)
                            set_period_and_query(page, args.start, args.end, timeout_ms)
                        select_tab(page, tab, timeout_ms)
                        path = download_tab(page, region, tab, args.start, args.end, output_dir, timeout_ms)
                        elapsed = round(time.time() - started, 2)
                        official_no_data = path.stat().st_size < 100
                        result = Result(
                            now_text(), region.region_code, region.region_name, region.sido_code,
                            tab, TAB_NAMES[tab], period, "success", attempt,
                            str(path), path.stat().st_size, elapsed,
                            error="official_no_data" if official_no_data else "",
                        )
                        progress.append(result)
                        completed += 1
                        consecutive_failures = 0
                        success = True
                        if official_no_data:
                            print(f"  [자료 없음] 탭 {tab} {TAB_NAMES[tab]} · 데이터랩 빈 다운로드 · {elapsed}s")
                        else:
                            print(f"  [성공] 탭 {tab} {TAB_NAMES[tab]} · {path.stat().st_size:,} bytes · {elapsed}s")
                        time.sleep(max(0.0, args.delay))
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        elapsed = round(time.time() - started, 2)
                        print(f"  [재시도 {attempt}/{args.retries + 1}] 탭 {tab}: {exc}")
                        if attempt <= args.retries:
                            wait_sec = recovery_wait(attempt)
                            print(f"  [복구 대기] {wait_sec}초")
                            time.sleep(wait_sec)
                            try:
                                context, page = recover_ready_page(
                                    pw, args, profile_dir, context, page, timeout_ms
                                )
                                choose_region(page, region, timeout_ms)
                                set_period_and_query(page, args.start, args.end, timeout_ms)
                            except Exception as recovery_exc:
                                print(f"  [복구 실패] {recovery_exc}")
                if not success:
                    progress.append(Result(
                        now_text(), region.region_code, region.region_name, region.sido_code,
                        tab, TAB_NAMES[tab], period, "failed", args.retries + 1,
                        elapsed_sec=elapsed, error=last_error,
                    ))
                    failed += 1
                    consecutive_failures += 1
                    if consecutive_failures >= args.max_consecutive_failures:
                        print(f"\n[안전 중단] 연속 실패 {consecutive_failures}건. 사이트 상태와 로그인을 확인하세요.")
                        stop_requested = True
                        break

            write_summary(progress, output_dir / "progress_summary.csv")
            if stop_requested:
                break

        close_context_quietly(context)

    write_summary(progress, output_dir / "progress_summary.csv")
    print(f"\n완료: 성공 {completed:,}건 · 실패 {failed:,}건")
    print(f"진행표: {output_dir / 'progress_summary.csv'}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다. 완료 기록은 보존되며 같은 명령으로 이어받을 수 있습니다.")
        raise SystemExit(130)
