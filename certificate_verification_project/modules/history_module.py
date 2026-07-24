"""Save and load verification results for the dashboard."""

import json
from datetime import datetime, timezone
from pathlib import Path

from database.db_utils import DEFAULT_DB_PATH, get_connection, init_database
from modules.verification_records import init_verification_tables

VERIFICATION_SCHEMA = (
    Path(__file__).resolve().parent.parent / "database" / "verification_schema.sql"
)


def init_history_table(db_path: Path | None = None) -> None:
    init_database(db_path)
    init_verification_tables(db_path)


def save_verification_results(
    batch_id: str,
    uploaded_filename: str,
    certificate_entries: list[dict],
    db_path: Path | None = None,
) -> None:
    """Store one row per certificate with full verification outcome."""
    init_history_table(db_path)
    conn = get_connection(db_path)
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        for entry in certificate_entries:
            verification = entry.get("verification") or {}
            parsed = verification.get("parsed") or {}
            db_record = verification.get("database_record") or {}
            artifacts = entry.get("verification_artifacts") or {}

            extracted_payload = {
                "parsed": parsed,
                "raw": entry.get("qr_data") or entry.get("barcode_data") or entry.get("text"),
            }

            conn.execute(
                """
                INSERT INTO verification_results (
                    batch_id, uploaded_filename, certificate_file,
                    verification_method, extracted_data, status,
                    confidence_score, verification_timestamp, message,
                    student_name, roll_no, certificate_id, report_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    uploaded_filename,
                    entry.get("file"),
                    entry.get("source") or verification.get("method") or "unknown",
                    json.dumps(extracted_payload, ensure_ascii=False),
                    verification.get("status") or "Needs Manual Review",
                    float(verification.get("confidence_score") or 0.0),
                    timestamp,
                    verification.get("message"),
                    db_record.get("student_name") or parsed.get("student_name"),
                    db_record.get("roll_no") or parsed.get("roll_no"),
                    db_record.get("certificate_id") or parsed.get("certificate_id"),
                    artifacts.get("report_filename"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


# Backward-compatible name used in app.py
save_upload_history = save_verification_results


def list_verification_history(limit: int = 100, db_path: Path | None = None) -> list[dict]:
    init_history_table(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM verification_results
            ORDER BY verification_timestamp DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_dashboard_item(dict(row)) for row in rows]
    finally:
        conn.close()


def get_dashboard_stats(db_path: Path | None = None) -> dict:
    init_history_table(db_path)
    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM verification_results").fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM verification_results WHERE status = ?",
            ("Verified",),
        ).fetchone()[0]
        fraudulent = conn.execute(
            "SELECT COUNT(*) FROM verification_results WHERE status = ?",
            ("Fraudulent",),
        ).fetchone()[0]
        manual = conn.execute(
            "SELECT COUNT(*) FROM verification_results WHERE status = ?",
            ("Needs Manual Review",),
        ).fetchone()[0]
        reports = conn.execute(
            """
            SELECT COUNT(*) FROM verification_results
            WHERE report_filename IS NOT NULL AND report_filename != ''
            """
        ).fetchone()[0]
        return {
            "total_checks": total,
            "verified_count": verified,
            "fraudulent_count": fraudulent,
            "manual_review_count": manual,
            "report_count": reports,
        }
    finally:
        conn.close()


def _row_to_dashboard_item(row: dict) -> dict:
    row["verification_timestamp_display"] = _format_timestamp(
        row.get("verification_timestamp")
    )
    row["confidence_display"] = f"{(row.get('confidence_score') or 0) * 100:.0f}%"
    row["download_url"] = None
    if row.get("report_filename") and row.get("batch_id"):
        row["download_url"] = f"/verified/{row['batch_id']}/{row['report_filename']}"
    try:
        row["extracted_preview"] = json.loads(row.get("extracted_data") or "{}")
    except json.JSONDecodeError:
        row["extracted_preview"] = {}
    return row


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ").replace("+00:00", " UTC")[:19] + " UTC"
