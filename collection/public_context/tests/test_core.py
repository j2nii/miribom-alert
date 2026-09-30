from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import (
    assert_collection_open,
    day_chunks,
    month_chunks,
    normalize_items,
    parse_date,
    parse_datetime,
)
from db_admin import sql_statements


class CoreTests(unittest.TestCase):
    def test_normalize_list_and_dict(self):
        rows, total = normalize_items(
            {"response": {"header": {"resultCode": "00"}, "body": {
                "totalCount": 2, "items": {"item": [{"a": 1}, {"a": 2}]}
            }}}
        )
        self.assertEqual(total, 2)
        self.assertEqual([row["a"] for row in rows], [1, 2])
        rows, total = normalize_items(
            {"response": {"header": {"resultCode": "0000"}, "body": {
                "totalCount": "1", "items": {"item": {"a": 3}}
            }}}
        )
        self.assertEqual(rows, [{"a": 3}])

    def test_month_chunks(self):
        chunks = list(month_chunks(date(2026, 1, 15), date(2026, 3, 2)))
        self.assertEqual(chunks, [
            (date(2026, 1, 15), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
            (date(2026, 3, 1), date(2026, 3, 2)),
        ])

    def test_seven_day_chunks(self):
        chunks = list(day_chunks(date(2026, 1, 1), date(2026, 1, 17), 7))
        self.assertEqual(chunks, [
            (date(2026, 1, 1), date(2026, 1, 7)),
            (date(2026, 1, 8), date(2026, 1, 14)),
            (date(2026, 1, 15), date(2026, 1, 17)),
        ])

    def test_date_parsing(self):
        self.assertEqual(parse_date("20260831", "%Y%m%d"), date(2026, 8, 31))
        self.assertEqual(
            parse_datetime("202608311230", "%Y%m%d%H%M"),
            datetime(2026, 8, 31, 12, 30),
        )

    def test_deadline(self):
        kst = ZoneInfo("Asia/Seoul")
        assert_collection_open(datetime(2026, 9, 22, 23, 59, 59, tzinfo=kst))
        with self.assertRaises(RuntimeError):
            assert_collection_open(datetime(2026, 9, 23, 0, 0, 0, tzinfo=kst))

    def test_schema_statements(self):
        text = (ROOT / "01_create_tables.sql").read_text(encoding="utf-8")
        statements = sql_statements(text)
        self.assertEqual(len(statements), 5)
        self.assertTrue(all(item.upper().startswith("CREATE TABLE") for item in statements))


if __name__ == "__main__":
    unittest.main()
