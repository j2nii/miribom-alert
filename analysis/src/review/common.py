from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "review_output"

def connect():
    import pymysql
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    password = os.getenv("MYSQL_PASSWORD", "")
    if not password or password == "CHANGE_ME":
        raise SystemExit(".env의 MYSQL_PASSWORD를 실제 비밀번호로 변경하세요.")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "yaho_loader"),
        password=password,
        database=os.getenv("MYSQL_DATABASE", "tour_earlywarning"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )

