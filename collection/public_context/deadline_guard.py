from __future__ import annotations

import sys

from common import COLLECTION_DEADLINE, KST, assert_collection_open


if __name__ == "__main__":
    try:
        assert_collection_open()
        print(f"[OPEN] Collection allowed until {COLLECTION_DEADLINE:%Y-%m-%d %H:%M:%S} KST")
    except Exception as exc:
        print(f"[CLOSED] {exc}", file=sys.stderr)
        raise SystemExit(2)

