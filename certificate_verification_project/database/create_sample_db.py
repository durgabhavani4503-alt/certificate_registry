"""
Create database/students.db with dummy TEST records only.

Run once for local testing:
    python database/create_sample_db.py

Real production data should be loaded with import_from_csv.py instead.
"""

from pathlib import Path

from db_utils import DEFAULT_DB_PATH, get_connection, init_database

# Dummy rows for testing only — not used by verification logic.
SAMPLE_ROWS = [
    {
        "student_name": "YATAKUNTA DURGA BHAVANI",
        "roll_no": "NPTEL25MA99S272101101",
        "certificate_id": "CERT-NPTEL-2025-001",
        "course": "Foundations of R Software",
        "branch": "Computer Science",
        "cgpa": 7.3,
        "year": "2025",
        "issue_date": "2025-10-15",
        "verification_status": "issued",
    },
    {
        "student_name": "ARUN KUMAR SHARMA",
        "roll_no": "NPTEL24CS88S123456789",
        "certificate_id": "CERT-NPTEL-2024-002",
        "course": "Programming in Python",
        "branch": "Information Technology",
        "cgpa": 8.1,
        "year": "2024",
        "issue_date": "2024-08-20",
        "verification_status": "issued",
    },
    {
        "student_name": "PRIYA NAIR",
        "roll_no": "NPTEL23EE77S987654321",
        "certificate_id": "CERT-NPTEL-2023-003",
        "course": "Basic Electrical Circuits",
        "branch": "Electrical Engineering",
        "cgpa": 6.9,
        "year": "2023",
        "issue_date": "2023-12-01",
        "verification_status": "revoked",
    },
]


def main() -> None:
    init_database(DEFAULT_DB_PATH)
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        conn.execute("DELETE FROM students")
        conn.executemany(
            """
            INSERT INTO students (
                student_name, roll_no, certificate_id, course, branch,
                cgpa, year, issue_date, verification_status
            ) VALUES (
                :student_name, :roll_no, :certificate_id, :course, :branch,
                :cgpa, :year, :issue_date, :verification_status
            )
            """,
            SAMPLE_ROWS,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        print(f"Sample database ready: {DEFAULT_DB_PATH} ({count} rows)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
