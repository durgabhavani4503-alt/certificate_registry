"""
Certificate verification decisions.

Statuses:
  - Verified
  - Fraudulent
  - Needs Manual Review

Methods: qr, barcode, ocr
"""

import sqlite3
from pathlib import Path

from modules.parse_extracted import PARSED_FIELDS, parse_extracted_content
from modules.verification_records import find_stored_record, init_verification_tables

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "database" / "students.db"

STATUS_VERIFIED = "Verified"
STATUS_FRAUDULENT = "Fraudulent"
STATUS_MANUAL_REVIEW = "Needs Manual Review"

BLOCKED_REGISTRY_STATUSES = {"revoked", "cancelled", "invalid", "suspended"}
CRITICAL_FIELDS = ("certificate_id", "roll_no", "student_name")
OCR_STRONG_MATCH_MIN_FIELDS = 3


def verify_from_qr(qr_text: str |None, db_path: Path |None = None):
    parsed = parse_extracted_content(qr_text)

    # If QR only contains certificate ID
    if not parsed and qr_text:
        parsed = {"certificate_id": qr_text.strip()}

    return _verify_with_method(parsed, method="qr", db_path=db_path, raw_text=qr_text)
    """Decode QR payload, check stored verification record, then student database."""
    parsed = parse_extracted_content(qr_text)
    return _verify_with_method(parsed, method="qr", db_path=db_path, raw_text=qr_text)


def verify_from_barcode(parsed: dict[str, str], db_path: Path | None = None) -> dict:
    """Search barcode value in certificate database."""
    return _verify_with_method(parsed, method="barcode", db_path=db_path)


def verify_from_ocr(extracted_text: str | None, db_path: Path | None = None) -> dict:
    """OCR text: extract fields and compare with database."""
    parsed = parse_extracted_content(extracted_text)
    print("\n========== OCR PARSED ==========")
    print(parsed)
    print("\n========== RAW OCR ==========")
    print(extracted_text)
    print("================================")
    return _verify_with_method(parsed, method="ocr", db_path=db_path, raw_text=extracted_text)


# Backward-compatible aliases used elsewhere
def verify_extracted_certificate(extracted_text: str | None, db_path: Path | None = None) -> dict:
    return verify_from_ocr(extracted_text, db_path=db_path)


def verify_parsed_certificate(parsed: dict[str, str], db_path: Path | None = None) -> dict:
    return verify_from_barcode(parsed, db_path=db_path)


def _verify_with_method(
    parsed: dict[str, str],
    method: str,
    db_path: Path | None = None,
    raw_text: str | None = None,
) -> dict:
    init_verification_tables(db_path)
    conn = _open_database(db_path)

    try:
        stored_record = find_stored_record(parsed, conn) if method == "qr" else None
        student_record = _find_student_record(conn, parsed)

        print("\n========== DATABASE RECORD ==========")
        if student_record:
            print(dict(student_record))
        else:
            print("No student found")
        print("=====================================")

        if method == "qr":
            outcome = _decide_qr(parsed, stored_record, student_record, raw_text)
        elif method == "barcode":
            outcome = _decide_barcode(parsed, student_record)
        else:
            outcome = _decide_ocr(parsed, student_record)
        outcome["method"] = method
        return outcome
    finally:
        conn.close()


def _decide_qr(
    parsed: dict[str, str],
    stored_record: sqlite3.Row | None,
    student_record: sqlite3.Row | None,
    raw_text: str | None,
) -> dict:
    if not parsed and not raw_text:
        return _result(
            STATUS_MANUAL_REVIEW,
            "QR decoded but contained no usable verification data.",
            parsed,
            student_record,
            {},
            {},
            0.35,
        )

    if stored_record is not None:
        confidence = 0.97
        return _result(
            STATUS_VERIFIED,
            "QR matches an active stored verification record.",
            parsed,
            student_record,
            {"stored_verification_record": "matched"},
            {},
            confidence,
        )

    if student_record is None:
        return _result(
            STATUS_FRAUDULENT,
            "QR data does not match any stored verification record or student entry.",
            parsed,
            None,
            {},
            {},
            0.2,
        )

    matched, mismatched, missing = _compare_fields(parsed, student_record)

    if _registry_blocked(student_record):
        return _result(
            STATUS_FRAUDULENT,
            "Student record exists but registry status is not valid.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.15,
        )

    if mismatched:
        return _result(
            STATUS_FRAUDULENT,
            "QR details conflict with the database record.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.25,
        )

    if _identifier_fields_match(parsed, matched) or _is_strong_match(matched, mismatched, missing):
        confidence = _confidence_score(matched, mismatched, missing, "qr")
        return _result(
            STATUS_VERIFIED,
            "QR certificate data matches the database.",
            parsed,
            student_record,
            matched,
            mismatched,
            confidence,
        )

    if missing:
        return _result(
            STATUS_MANUAL_REVIEW,
            "QR partially matches the database; manual review recommended.",
            parsed,
            student_record,
            matched,
            mismatched,
            _confidence_score(matched, mismatched, missing, "qr"),
        )

    return _result(
        STATUS_VERIFIED,
        "QR linked to a valid database record.",
        parsed,
        student_record,
        matched,
        mismatched,
        0.88,
    )


def _decide_barcode(parsed: dict[str, str], student_record: sqlite3.Row | None) -> dict:
    if not parsed:
        return _result(
            STATUS_MANUAL_REVIEW,
            "Barcode decoded but could not map to certificate identifiers.",
            parsed,
            None,
            {},
            {},
            0.4,
        )

    if student_record is None:
        return _result(
            STATUS_FRAUDULENT,
            "Barcode value not found in the certificate database.",
            parsed,
            None,
            {},
            {},
            0.18,
        )

    matched, mismatched, missing = _compare_fields(parsed, student_record)

    if _registry_blocked(student_record):
        return _result(
            STATUS_FRAUDULENT,
            "Barcode matches a revoked or invalid registry entry.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.12,
        )

    if mismatched:
        critical_conflict = any(field in mismatched for field in CRITICAL_FIELDS)
        if critical_conflict:
            return _result(
                STATUS_FRAUDULENT,
                "Barcode conflicts with database details.",
                parsed,
                student_record,
                matched,
                mismatched,
                0.2,
            )
        return _result(
            STATUS_MANUAL_REVIEW,
            "Barcode matches partially; some fields disagree.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.55,
        )

    if _identifier_fields_match(parsed, matched):
        return _result(
            STATUS_VERIFIED,
            "Barcode matches the certificate database.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.9,
        )

    return _result(
        STATUS_MANUAL_REVIEW,
        "Barcode found a record but match is incomplete.",
        parsed,
        student_record,
        matched,
        mismatched,
        _confidence_score(matched, mismatched, missing, "barcode"),
    )


def _decide_ocr(parsed: dict[str, str], student_record: sqlite3.Row | None) -> dict:
    if not parsed:
        return _result(
            STATUS_FRAUDULENT,
            "OCR could not extract enough certificate details.",
            parsed,
            None,
            {},
            {},
            0.15,
        )

    if student_record is None:
        return _result(
            STATUS_FRAUDULENT,
            "No matching student record found in the database.",
            parsed,
            None,
            {},
            {},
            0.2,
        )

    matched, mismatched, missing = _compare_fields(parsed, student_record)
    print("\n===== MATCH RESULT =====")
    print("Matched :", matched)
    print("Mismatched :", mismatched)
    print("Missing :", missing)
    print("========================")
    if _registry_blocked(student_record):
        return _result(
            STATUS_FRAUDULENT,
            "Record exists but official registry status is not valid.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.1,
        )

    if mismatched:
        critical_conflict = any(field in mismatched for field in CRITICAL_FIELDS)
        if critical_conflict:
            return _result(
                STATUS_FRAUDULENT,
                "OCR details conflict with the database.",
                parsed,
                student_record,
                matched,
                mismatched,
                0.22,
            )
        return _result(
            STATUS_MANUAL_REVIEW,
            "Some OCR fields disagree with the database.",
            parsed,
            student_record,
            matched,
            mismatched,
            0.5,
        )

    if _is_strong_match(matched, mismatched, missing):
        return _result(
            STATUS_VERIFIED,
            "OCR data strongly matches the database record.",
            parsed,
            student_record,
            matched,
            mismatched,
            _confidence_score(matched, mismatched, missing, "ocr"),
        )

    if missing:
        return _result(
            STATUS_MANUAL_REVIEW,
            "Partial or unclear OCR match; manual review required.",
            parsed,
            student_record,
            matched,
            mismatched,
            _confidence_score(matched, mismatched, missing, "ocr"),
        )

    return _result(
        STATUS_VERIFIED,
        "OCR data matches the database record.",
        parsed,
        student_record,
        matched,
        mismatched,
        0.85,
    )


def _open_database(db_path: Path | None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. "
            "Run: python database/create_sample_db.py "
            "or import CSV with: python database/import_from_csv.py your_file.csv"
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _find_student_record(conn: sqlite3.Connection, parsed: dict[str, str]) -> sqlite3.Row | None:
    roll_no = parsed.get("roll_no")
    if roll_no:
        row = conn.execute(
            "SELECT * FROM students WHERE roll_no = ? COLLATE NOCASE",
            (roll_no.strip(),),
        ).fetchone()
        if row:
            return row

    certificate_id = parsed.get("certificate_id")
    if certificate_id:
        row = conn.execute(
            "SELECT * FROM students WHERE certificate_id = ? COLLATE NOCASE",
            (certificate_id.strip(),),
        ).fetchone()
        if row:
            return row

    serial_no = parsed.get("serial_no")
    if serial_no:
        value = serial_no.strip()
        row = conn.execute(
            """
            SELECT * FROM students
            WHERE certificate_id = ? OR roll_no = ? COLLATE NOCASE
            """,
            (value, value),
        ).fetchone()
        if row:
            return row

    student_name = parsed.get("student_name")
    if student_name:
        rows = conn.execute(
            "SELECT * FROM students WHERE student_name LIKE ? COLLATE NOCASE",
            (f"%{student_name.strip()}%",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]

    return None

def _normalize_ocr_text(value: str) -> str:
    """
    Advanced normalization that standardizes common OCR typos 
    (like reading 8 as B, or 0 as O) specifically for serial codes and roll numbers.
    """
    if value is None:
        return ""
    # Convert to uppercase, remove spaces, dashes, and extra punctuation
    clean = " ".join(str(value).upper().split()).replace(" ", "").replace("-", "")
    # Normalize character patterns frequently swapped by local Tesseract
    clean = clean.replace("O", "0").replace("B", "8").replace("I", "1")
    return clean


def _compare_fields(
    parsed: dict[str, str],
    record: sqlite3.Row,
) -> tuple[dict[str, str], dict[str, str], list[str]]:

    matched = {}
    mismatched = {}
    missing = []

    for field in PARSED_FIELDS:

        if field in ("verification_status", "serial_no"):
            continue

        if field not in record.keys():
            continue

        extracted_value = parsed.get(field)
        db_value = record[field]

        # ✅ Skip comparison if database value is empty or not provided
        if db_value is None or str(db_value).strip() == "":
            continue

        if extracted_value is None or str(extracted_value).strip() == "":
            missing.append(field)
            continue

        if _values_match(field, extracted_value, db_value):
            matched[field] = str(db_value)
        else:
            mismatched[field] = (
                f"extracted={extracted_value} | db={db_value}"
            )

    return matched, mismatched, missing


def _values_match(field: str, extracted: str, db_value) -> bool:
    if db_value is None:
        return False
        
    if field == "cgpa":
        try:
            return abs(float(extracted) - float(db_value)) <= 0.15
        except ValueError:
            return False
            
    # ✅ FIX: Use OCR character typo normalization for critical identifier strings
    if field in {"roll_no", "certificate_id"}:
        return _normalize_ocr_text(extracted) == _normalize_ocr_text(db_value)
            
    left = _normalize(str(extracted))
    right = _normalize(str(db_value))
    if left == right:
        return True
        
    if field in {"student_name", "course", "branch"}:
        return left in right or right in left
    return False


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _registry_blocked(record: sqlite3.Row) -> bool:
    return _normalize(record["verification_status"]) in BLOCKED_REGISTRY_STATUSES


def _identifier_fields_match(parsed: dict[str, str], matched: dict[str, str]) -> bool:
    id_fields = ("certificate_id", "roll_no", "serial_no")
    provided = [field for field in id_fields if parsed.get(field)]
    return bool(provided) and all(field in matched for field in provided)


def _is_strong_match(
    matched: dict[str, str],
    mismatched: dict[str, str],
    missing: list[str],
) -> bool:
    if mismatched:
        return False
    has_id = "certificate_id" in matched or "roll_no" in matched
    if not has_id:
        return False
    if len(matched) >= OCR_STRONG_MATCH_MIN_FIELDS:
        return True
    return "student_name" in matched and has_id


def _confidence_score(
    matched: dict[str, str],
    mismatched_fields: dict[str, str],
    missing: list[str],
    method: str,
) -> float:
    if mismatched_fields:
        return 0.2
    base = {"qr": 0.92, "barcode": 0.88, "ocr": 0.8}[method]
    checked = len(matched) + len(missing)
    if checked == 0:
        return round(base * 0.5, 2)
    ratio = len(matched) / checked
    score = base * ratio + 0.08 * len(matched)
    return round(min(0.99, max(0.1, score)), 2)


def _result(
    status: str,
    message: str,
    parsed: dict[str, str],
    record: sqlite3.Row | None,
    matched_fields: dict[str, str],
    mismatched_fields: dict[str, str],
    confidence_score: float,
) -> dict:
    return {
        "status": status,
        "message": message,
        "parsed": parsed,
        "database_record": dict(record) if record else None,
        "matched_fields": matched_fields,
        "mismatched_fields": mismatched_fields,
        "confidence_score": confidence_score,
    }
