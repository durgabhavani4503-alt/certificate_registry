"""
Basic fraud checks for legacy certificates (no embedded QR).

Works with verification results from verify_module — no hardcoded student data.
"""

BLOCKED_REGISTRY_STATUSES = {"revoked", "cancelled", "invalid", "suspended"}


def run_fraud_checks(extracted_text: str | None, verification: dict) -> dict:
    """
    Return fraud assessment: PASS, REVIEW, or FAIL.

    Used only on the legacy path (certificate had no QR).
    """
    flags: list[str] = []
    text = (extracted_text or "").strip()
    db_record = verification.get("database_record") or {}

    if len(text) < 40:
        flags.append("Very little text extracted from certificate (possible blank or poor scan).")

    if not text:
        flags.append("No readable certificate content.")

    if verification.get("status") == "INVALID":
        flags.append("Database verification failed (details do not match).")

    if verification.get("status") == "SUSPICIOUS":
        flags.append("Verification inconclusive (partial or missing fields).")

    if verification.get("mismatched_fields"):
        flags.append("One or more fields conflict with the official record.")

    registry_status = str(db_record.get("verification_status", "")).lower()
    if registry_status in BLOCKED_REGISTRY_STATUSES:
        flags.append(f"Registry status is '{registry_status}' (not eligible for verification).")

    if not db_record:
        flags.append("No matching official record found in database.")

    status = _decide_status(verification.get("status"), flags)
    return {
        "status": status,
        "flags": flags,
        "message": _message_for_status(status),
    }


def _decide_status(verification_status: str | None, flags: list[str]) -> str:
    if verification_status == "INVALID":
        return "FAIL"
    if verification_status != "VALID":
        return "FAIL" if flags else "REVIEW"
    if not flags:
        return "PASS"
    return "REVIEW"


def _message_for_status(status: str) -> str:
    messages = {
        "PASS": "No fraud indicators detected.",
        "REVIEW": "Some concerns detected — manual review recommended.",
        "FAIL": "Fraud checks failed — verified digital copy will not be created.",
    }
    return messages.get(status, "Fraud check completed.")
