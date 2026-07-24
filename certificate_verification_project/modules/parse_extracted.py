"""
Parse student/certificate fields from OCR text or QR payload.

Uses generic patterns only — no hardcoded student values.
"""

import json
import re
from urllib.parse import parse_qs, urlparse

# Fields we try to detect from any certificate text.
PARSED_FIELDS = (
    "student_name",
    "roll_no",
    "certificate_id",
    "serial_no",
    "course",
    "branch",
    "cgpa",
    "year",
    "issue_date",
)


def parse_extracted_content(text: str | None) -> dict[str, str]:
    """Build a dict of detected fields from raw OCR/QR text."""
    if not text or not text.strip():
        return {}

    cleaned = text.strip()
    parsed: dict[str, str] = {}

    # QR payloads are sometimes JSON or URL query parameters.
    parsed.update(_parse_structured_payload(cleaned))
    parsed.update(_parse_with_regex(cleaned))

    return parsed


def parse_barcode_content(barcode_text: str | None) -> dict[str, str]:
    """Map raw barcode data to certificate_id and/or serial_no (roll_no)."""
    if not barcode_text or not barcode_text.strip():
        return {}

    value = barcode_text.strip()

    # JSON / URL payloads can use the full parser.
    if value.startswith("{") or "://" in value:
        return parse_extracted_content(value)

    upper = value.upper()
    if upper.startswith("CERT"):
        return {"certificate_id": value}
    if upper.startswith("NPTEL"):
        return {"roll_no": value}

    return {"serial_no": value, "certificate_id": value}


def _parse_structured_payload(text: str) -> dict[str, str]:
    found: dict[str, str] = {}

    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in PARSED_FIELDS:
                    value = data.get(key) or data.get(key.upper())
                    if value is not None and str(value).strip():
                        found[key] = str(value).strip()
                for extra in ("verification_id", "hash_value"):
                    value = data.get(extra) or data.get(extra.upper())
                    if value is not None and str(value).strip():
                        found[extra] = str(value).strip()
        except json.JSONDecodeError:
            pass

    if "://" in text:
        query = parse_qs(urlparse(text).query)
        for key in PARSED_FIELDS:
            if key in query and query[key][0].strip():
                found[key] = query[key][0].strip()
        for extra in ("verification_id", "hash_value"):
            if extra in query and query[extra][0].strip():
                found[extra] = query[extra][0].strip()

    return found


def _parse_with_regex(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    single_line = " ".join(text.split())

    patterns = {
        "roll_no": [
            r"roll\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
            r"regd\.?\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
            r"registration\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
            r"\b(NPTEL[0-9A-Z]{10,})\b",
            r"hall\s*ticket\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
            r"hallticket\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
        ],
        "certificate_id": [
            r"pc\.?\s*no\.?[,:\s]*([A-Z0-9 ]{8,})",
            r"certificate\s*id\s*[:\-]?\s*([A-Z0-9\-]+)",
            r"memo\s*no\.?\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "serial_no": [
            r"pc\s*sl\.?\s*no\.?\s*[:\-]?\s*([A-Z0-9]+)",
            r"serial\s*no\.?\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "student_name": [
            r"this\s+is\s+to\s+certify\s+that\s+mr\.?/ms[.,]?\s*([A-Z ]+?)\s+son\s*/?\s*daughter",
            r"this\s+is\s+to\s+certify\s+that\s+mr\.?/ms[.,]?\s*([A-Z ]+?)\s+son",
            r"this\s+is\s+to\s+certify\s+that\s+mr\.?/ms[.,]?\s*([A-Z ]+?)\s+passed",
            r"mr\.?/ms[.,]?\s*([A-Z ]+?)\s+son",
            r"name\s*of\s*the\s*candidate\s*[:\-]?\s*([A-Za-z ]+)",
        ],
        "course": [
            r"completing\s+the\s+course\s+(.+?)(?:\s+with|\s*$)",
            r"course\s*[:\-]?\s*([^,\n]+)",
            r"passed\s+(b\.?tech|m\.?tech|mba|mca)",
        ],
        "branch": [
            r"branch\s*[:\-]?\s*([A-Za-z &]+)",
            r"passed\s+b\.?tech\s*\((.*?)\)",
        ],
        "cgpa": [
            r"cgpa\s*[:\-]?\s*([0-9.]+)",
            r"consolidated\s+score\s*(?:of\s*)?([0-9.]+)\s*%",
        ],
        "year": [
            r"\b(20[0-9]{2})\b",
        ],
        "issue_date": [
            r"issue\s*date\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            r"date\s*[:\-]?\s*([0-9]{2}-[0-9]{2}-[0-9]{4})",
            r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
            r"\b([0-9]{2}-[0-9]{2}-[0-9]{4})\b",
            r"date\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
        ],
    }

    for field, field_patterns in patterns.items():
        if field in found:
            continue
        for pattern in field_patterns:
            match = re.search(pattern, single_line, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    found[field] = value
                    break
    if "certificate_id" in found:
        found["certificate_id"] = (
            found["certificate_id"]
            .replace(" ", "")
            .replace(",", "")
            .upper()
        )
    print("\n===== PARSER OUTPUT =====")
    print(found)
    print("=========================\n")
    return found
