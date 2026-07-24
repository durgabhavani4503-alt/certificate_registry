"""Shared database helpers (used by verify module and import script)."""

import sqlite3
from pathlib import Path

DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = DATABASE_DIR / "students.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Path | None = None) -> None:
    """Create tables from schema.sql if they do not exist."""
    conn = get_connection(db_path)
    try:
        # 1. Initialize original tables from schema.sql
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
        
        # 2. Add our new Dynamic Mapping Config Table explicitly if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS upload_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                format_name TEXT UNIQUE,
                map_roll_no TEXT,
                map_student_name TEXT,
                map_certificate_id TEXT,
                map_course TEXT,
                map_branch TEXT,
                map_cgpa TEXT
            )
        ''')
        conn.commit()
    finally:
        conn.close()


def save_mapping_config(format_name: str, config: dict, db_path: Path | None = None) -> None:
    """
    Saves a college's custom spreadsheet layout column names into the system configuration.
    config keys: roll_no, student_name, certificate_id, course, branch, cgpa
    """
    conn = get_connection(db_path)
    try:
        conn.execute('''
            INSERT OR REPLACE INTO upload_mappings 
            (format_name, map_roll_no, map_student_name, map_certificate_id, map_course, map_branch, map_cgpa)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            format_name,
            config.get('roll_no'),
            config.get('student_name'),
            config.get('certificate_id'),
            config.get('course'),
            config.get('branch'),
            config.get('cgpa')
        ))
        conn.commit()
    finally:
        conn.close()


def get_mapping_config(format_name: str, db_path: Path | None = None) -> sqlite3.Row | None:
    """Retrieves a saved formatting map structure for automated ingestion processing."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM upload_mappings WHERE format_name = ?", (format_name,)
        ).fetchone()
        return row
    finally:
        conn.close()
