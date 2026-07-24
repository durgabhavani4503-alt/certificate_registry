"""
Post-verification QR payload and standalone report generation.

Uploaded certificate files (images/PDFs) are read-only evidence. This module
never edits or re-exports the student's original certificate. After a successful
database match it only creates:

  1. A verification record (IDs, timestamp, tamper-evident hash, QR payload)
  2. An optional standalone verification report PDF (metadata + QR for re-checks)

Use the QR on the report or in the record for future lookups — not for stamping
onto issued certificates.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz
import qrcode
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M

REPORT_QR_SIZE = 140


def create_verification_artifacts(
    certificate_stem: str,
    verification: dict,
    output_dir: Path,
    evidence_text: str | None = None,
) -> dict | None:
    """
    Build verification record and save a separate report PDF under output_dir.

    Returns metadata dict, or None if verification has no database match.
    """
    record = build_verification_record(verification, evidence_text=evidence_text)
    if record is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    report_filename = write_verification_report_pdf(
        record,
        output_dir / f"{certificate_stem}_verification_report.pdf",
    )

    record["report_filename"] = report_filename
    record["report_path"] = str(output_dir / report_filename)
    return record


def build_verification_record(
    verification: dict,
    evidence_text: str | None = None,
) -> dict | None:
    """Create QR-linked verification metadata (no certificate image changes)."""
    db_record = verification.get("database_record")
    if not db_record:
        return None

    certificate_id = db_record.get("certificate_id") or db_record.get("roll_no")
    if not certificate_id:
        return None

    verification_id = str(uuid.uuid4())
    verification_timestamp = datetime.now(timezone.utc).isoformat()
    hash_value = compute_hash_value(evidence_text, db_record)
    qr_payload = build_qr_payload(
        certificate_id=certificate_id,
        verification_id=verification_id,
        verification_timestamp=verification_timestamp,
        hash_value=hash_value,
    )

    return {
        "certificate_id": certificate_id,
        "verification_id": verification_id,
        "verification_timestamp": verification_timestamp,
        "hash_value": hash_value,
        "qr_payload": qr_payload,
        "student_name": db_record.get("student_name"),
        "roll_no": db_record.get("roll_no"),
        "course": db_record.get("course"),
        "year": db_record.get("year"),
    }


def build_qr_payload(
    certificate_id: str,
    verification_id: str,
    verification_timestamp: str,
    hash_value: str,
) -> str:
    """JSON string encoded in the post-verification QR (report / record only)."""
    data = {
        "certificate_id": certificate_id,
        "verification_id": verification_id,
        "verification_timestamp": verification_timestamp,
        "hash_value": hash_value,
        "purpose": "verification_record",
    }
    return json.dumps(data, separators=(",", ":"))


def compute_hash_value(evidence_text: str | None, db_record: dict) -> str:
    """Tamper-evident hash from scan evidence + official record identifiers."""
    parts = [
        evidence_text or "",
        str(db_record.get("certificate_id", "")),
        str(db_record.get("roll_no", "")),
        str(db_record.get("student_name", "")),
    ]
    digest_input = "|".join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def generate_qr_image(payload: str) -> Image.Image:
    """Create a QR image from the verification payload."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def write_verification_report_pdf(record: dict, output_path: Path) -> str:
    """
    Write a standalone verification report PDF (not a modified certificate).

    Returns the report filename (basename).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text(
        (50, 48),
        "Certificate verification report",
        fontsize=18,
        fontname="helv",
    )
    page.insert_text(
        (50, 72),
        "This document is separate from the issued certificate. "
        "The original upload was not modified.",
        fontsize=9,
        fontname="helv",
        color=(0.35, 0.35, 0.35),
    )

    lines = [
        ("Certificate ID", record.get("certificate_id", "—")),
        ("Verification ID", record.get("verification_id", "—")),
        ("Verified at (UTC)", _format_ts(record.get("verification_timestamp"))),
        ("Student name", record.get("student_name") or "—"),
        ("Roll number", record.get("roll_no") or "—"),
        ("Course", record.get("course") or "—"),
        ("Year", record.get("year") or "—"),
        ("Evidence hash", record.get("hash_value", "—")),
    ]

    y = 110
    for label, value in lines:
        page.insert_text((50, y), f"{label}:", fontsize=10, fontname="helv")
        page.insert_text((180, y), str(value), fontsize=10, fontname="helv")
        y += 22

    qr_image = generate_qr_image(record["qr_payload"])
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)

    qr_rect = fitz.Rect(380, 620, 380 + REPORT_QR_SIZE, 620 + REPORT_QR_SIZE)
    page.insert_image(qr_rect, stream=buffer.read())
    page.insert_text(
        (380, 605),
        "QR for future verification lookups",
        fontsize=9,
        fontname="helv",
    )

    doc.save(output_path)
    doc.close()
    return output_path.name


def _format_ts(value: str | None) -> str:
    if not value:
        return "—"
    return value[:19].replace("T", " ") + " UTC"
