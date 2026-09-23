from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
APPLY_FILES = (
    "40_create_detail_mappings.sql",
    "41_build_canonical_detail_features.sql",
    "42_create_enriched_analysis_views.sql",
    "43_validate_integration.sql",
)


def load_environment():
    local_env = BASE_DIR / ".env"
    sibling_env = BASE_DIR.parent / "all_received_loader" / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    elif sibling_env.exists():
        load_dotenv(sibling_env)


def connect():
    password = os.environ.get("MYSQL_PASSWORD", "")
    if not password or password.startswith("CHANGE_"):
        raise RuntimeError(
            ".env의 MYSQL_PASSWORD를 실제 yaho_loader 비밀번호로 바꾸세요."
        )
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "yaho_loader"),
        password=password,
        database=os.environ.get("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=30,
        read_timeout=7200,
        write_timeout=7200,
        cursorclass=pymysql.cursors.DictCursor,
    )


def split_sql(text: str):
    statements = []
    current = []
    quote = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                if next_char == quote:
                    current.append(next_char)
                    index += 1
                else:
                    quote = None
        else:
            if char in ("'", '"', "`"):
                quote = char
                current.append(char)
            elif char == ";":
                statement = "".join(current).strip()
                if statement:
                    statements.append(statement)
                current = []
            else:
                current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def print_result(cursor):
    if not cursor.description:
        return
    rows = cursor.fetchall()
    if not rows:
        return
    columns = [column[0] for column in cursor.description]
    print("\t".join(columns))
    for row in rows:
        print("\t".join("NULL" if row.get(column) is None else str(row.get(column)) for column in columns))


def run_file(conn, path: Path, show_progress=True):
    statements = split_sql(path.read_text(encoding="utf-8-sig"))
    if show_progress:
        print(f"[{path.name}] {len(statements)}개 SQL 실행")
    with conn.cursor() as cursor:
        for number, statement in enumerate(statements, start=1):
            try:
                cursor.execute(statement)
                print_result(cursor)
            except Exception as exc:
                conn.rollback()
                first_line = next(
                    (line.strip() for line in statement.splitlines() if line.strip()),
                    "SQL",
                )
                raise RuntimeError(
                    f"{path.name}의 {number}번째 SQL 실패 ({first_line[:100]}): {exc}"
                ) from exc
    conn.commit()


def main():
    load_environment()
    parser = argparse.ArgumentParser(description="세부 관광 데이터 분석 결합")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--enriched-only",
        action="store_true",
        help="월별 상세 스냅샷과 통합 분석 뷰만 다시 만들고 검증합니다.",
    )
    parser.add_argument(
        "--mapping-fix",
        action="store_true",
        help="확정된 미매핑 지역을 적용하고 파생 데이터 전체를 다시 계산합니다.",
    )
    args = parser.parse_args()

    selected_modes = sum((args.validate_only, args.enriched_only, args.mapping_fix))
    if selected_modes > 1:
        parser.error("실행 모드 옵션은 하나만 선택할 수 있습니다.")
    if args.validate_only:
        targets = ("43_validate_integration.sql",)
    elif args.enriched_only:
        targets = (
            "42_create_enriched_analysis_views.sql",
            "43_validate_integration.sql",
        )
    elif args.mapping_fix:
        targets = (
            "44_apply_missing_region_mappings.sql",
            "41_build_canonical_detail_features.sql",
            "42_create_enriched_analysis_views.sql",
            "43_validate_integration.sql",
        )
    else:
        targets = APPLY_FILES
    conn = connect()
    try:
        for index, name in enumerate(targets, start=1):
            print("\n" + "=" * 68)
            print(f"[{index}/{len(targets)}] {name}")
            print("=" * 68)
            run_file(conn, BASE_DIR / name)
    finally:
        conn.close()
    if args.validate_only:
        print("\n[OK] 검증 완료")
    elif args.enriched_only:
        print("\n[OK] 통합 분석 뷰 재생성 및 검증 완료")
    elif args.mapping_fix:
        print("\n[OK] 미매핑 지역 보정 및 전체 파생 데이터 재계산 완료")
    else:
        print("\n[OK] 세부 데이터 결합 완료")
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[중단] 사용자가 작업을 중단했습니다.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n[오류] {exc}", file=sys.stderr)
        raise SystemExit(2)
