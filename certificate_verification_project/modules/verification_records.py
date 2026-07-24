"""Save and look up stored QR verification records."""

import json
import sqlite3
from pathlib import Path

from database.db_utils import DEFAULT_DB_PATH, get_connection, init_database

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "verification_schema.sql"


def init_verification_tables(db_path: Path | None = None) -> None:
    init_database(db_path)
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def save_stored_record(record: dict, db_path: Path | None = None) -> None:
    """Persist a verification record so future QR scans can validate against it."""
    init_verification_tables(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO verification_records (
                certificate_id, verification_id, hash_value,
                verification_timestamp, record_status
            ) VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT(certificate_id) DO UPDATE SET
                verification_id = excluded.verification_id,
                hash_value = excluded.hash_value,
                verification_timestamp = excluded.verification_timestamp,
                record_status = 'active'
            """,
            (
                record["certificate_id"],
                record["verification_id"],
                record["hash_value"],
                record["verification_timestamp"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def find_stored_record(
    parsed: dict,
    conn: sqlite3.Connection,
) -> sqlite3.Row | None:
    certificate_id = parsed.get("certificate_id")
    if not certificate_id:
        return None

    row = conn.execute(
        """
        SELECT * FROM verification_records
        WHERE certificate_id = ? COLLATE NOCASE AND record_status = 'active'
        """,
        (certificate_id.strip(),),
    ).fetchone()

    if row is None:
        return None

    expected_hash = parsed.get("hash_value")
    if expected_hash and row["hash_value"] != expected_hash.strip():
        return None

    expected_vid = parsed.get("verification_id")
    if expected_vid and row["verification_id"] != expected_vid.strip():
        return None

    return row
