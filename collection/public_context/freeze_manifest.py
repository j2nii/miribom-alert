from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from common import COLLECTION_DEADLINE, KST, OUTPUT_DIR, connect_db, json_text, load_environment


TABLE_QUERIES = {
    "visitors_external_daily": "SELECT COUNT(*) rows_actual, MIN(observed_date) date_min, MAX(observed_date) date_max FROM fact_signal WHERE metric='realization_visitors'",
    "naver_search_daily": "SELECT COUNT(*) rows_actual, MIN(observed_date) date_min, MAX(observed_date) date_max FROM fact_signal WHERE metric='interest_naver'",
    "datalab_monthly_panel": "SELECT COUNT(*) rows_actual, MIN(period_start) date_min, MAX(period_start) date_max FROM datalab_monthly_panel",
    "datalab_detail_row": "SELECT COUNT(*) rows_actual, MIN(COALESCE(observed_month,query_start_month)) date_min, MAX(COALESCE(observed_month,query_end_month)) date_max FROM datalab_detail_row",
    "major_attraction_visitors_monthly": "SELECT COUNT(*) rows_actual, MIN(observed_month) date_min, MAX(observed_month) date_max FROM major_attraction_visitors_monthly",
    "event_evidence_candidate": "SELECT COUNT(*) rows_actual, COUNT(DISTINCT region_id,episode_no) episodes, MIN(collected_at) date_min, MAX(collected_at) date_max FROM event_evidence_candidate",
    "raw_tourapi_festival": "SELECT COUNT(*) rows_actual, MIN(event_start_date) date_min, MAX(event_end_date) date_max FROM raw_tourapi_festival",
    "raw_kma_asos_daily": "SELECT COUNT(*) rows_actual, MIN(observed_date) date_min, MAX(observed_date) date_max FROM raw_kma_asos_daily",
    "raw_kma_warning": "SELECT COUNT(*) rows_actual, MIN(announcement_at) date_min, MAX(announcement_at) date_max FROM raw_kma_warning",
    "vw_anomaly_analysis_ready": "SELECT COUNT(*) rows_actual, MIN(episode_start) date_min, MAX(episode_end) date_max FROM vw_anomaly_analysis_ready",
    "vw_anomaly_analysis_enriched": "SELECT COUNT(*) rows_actual, MIN(episode_start) date_min, MAX(episode_end) date_max FROM vw_anomaly_analysis_enriched",
    "vw_additional_collection_priority": "SELECT COUNT(*) rows_actual, MIN(visitor_peak_date) date_min, MAX(visitor_peak_date) date_max FROM vw_additional_collection_priority",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(row: dict) -> dict:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in row.items()}


def main() -> int:
    load_environment()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()
    tables: dict[str, dict] = {}
    try:
        for name, sql in TABLE_QUERIES.items():
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    tables[name] = json_safe(cur.fetchone() or {})
            except Exception as exc:
                tables[name] = {"error": str(exc)}

        files = []
        for path in sorted(OUTPUT_DIR.iterdir()):
            if path.is_file() and not path.name.startswith("collection_freeze_manifest"):
                files.append(
                    {
                        "file": path.name,
                        "size_bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                    }
                )

        payload = {
            "project": "tourism-early-warning",
            "freeze_policy": "No new data collection after the cutoff; validation and analysis remain allowed.",
            "cutoff_at_kst": COLLECTION_DEADLINE.isoformat(),
            "snapshot_at_kst": datetime.now(KST).isoformat(),
            "database": tables,
            "files": files,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["manifest_payload_sha256"] = manifest_hash
        path = OUTPUT_DIR / "collection_freeze_manifest_20260922.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO collection_freeze_snapshot(
                       frozen_at_kst,cutoff_at_kst,manifest_sha256,note)
                   VALUES(%s,%s,%s,%s)""",
                (
                    datetime.now(KST).replace(tzinfo=None),
                    COLLECTION_DEADLINE.replace(tzinfo=None),
                    manifest_hash,
                    "2026-09-22 final collection freeze",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"[OK] {path}")
    print(f"[SHA256] {manifest_hash}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
