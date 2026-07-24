"""
Import student records from a CSV file using static fallback dictionary mapping
or dynamic dashboard runtime mapping configurations.
"""

import argparse
import csv
import sys
from pathlib import Path

from database.db_utils import DEFAULT_DB_PATH, get_connection, init_database

REQUIRED_COLUMNS = {
    "student_name",
    "roll_no",
    "certificate_id",
    "course",
    "branch",
    "cgpa",
    "year",
    "issue_date",
    "verification_status",
}

COLUMN_MAPPING = {
    "ROLL NO": "roll_no",
    "ROLLNO": "roll_no",
    "ROLL_NUMBER": "roll_no",
    "HALL TICKET": "roll_no",
    "HALL TICKET NO": "roll_no",
    "HTNO": "roll_no",
    "REGISTER NUMBER": "roll_no",
    "NAME": "student_name",
    "STUDENT NAME": "student_name",
    "CANDIDATE NAME": "student_name",
    "FULL NAME": "student_name",
    "PC NO": "certificate_id",
    "PC.NO": "certificate_id",
    "CERTIFICATE NO": "certificate_id",
    "CERTIFICATE NUMBER": "certificate_id",
    "PC SL.NO": "serial_no",
    "PC SL NO": "serial_no",
    "SL.NO": "serial_no",
    "SERIAL NO": "serial_no",
    "COURSE": "course",
    "BRANCH": "branch",
    "CGPA": "cgpa",
    "YEAR": "year",
    "ISSUE DATE": "issue_date",
    "DATE": "issue_date",
    "STATUS": "verification_status",
    "VERIFICATION STATUS": "verification_status",
    "DIVISION": "division",
}

def import_csv(csv_path: Path, db_path: Path, replace: bool = False, runtime_mapping: dict = None) -> int:
    """
    Import student CSV rows. If runtime_mapping is passed from the dashboard dropdowns,
    it overrides the static dictionary layout checks.
    """
    init_database(db_path)

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        rows = list(csv.reader(csv_file))

        header_row = None
        
        # Look down the rows to find where the true data columns start
        for i, row in enumerate(rows):
            normalized = [cell.strip().upper() for cell in row]
            if "ROLL NO" in normalized or "NAME" in normalized or "HTNO" in normalized or "S.NO" in normalized:
                header_row = i
                break

        if header_row is None:
            header_row = 0

        header = [cell.strip() for cell in rows[header_row]]
        data_rows = rows[header_row + 1:]

        reader = []
        for row in data_rows:
            record = dict(zip(header, row))
            reader.append(record)

        mapped_headers = {}

        # ✅ FIXED: Completely case-normalize the keys and values to stop character mismatches
        if runtime_mapping:
            # Revert mapping config to form a clean lookup dictionary: { 'USER_HEADER_UPPER': 'system_key' }
            clean_runtime = {}
            for sys_key, user_col in runtime_mapping.items():
                if user_col:
                    clean_runtime[str(user_col).strip().upper()] = sys_key

            for original in header:
                key_upper = original.upper()
                mapped_headers[original] = clean_runtime.get(key_upper, original)
        else:
            for original in header:
                key = original.strip().upper()
                mapped_headers[original] = COLUMN_MAPPING.get(key, original)

        headers_set = set(mapped_headers.values())
        mandatory = {"roll_no", "student_name", "certificate_id"}
        missing = mandatory - headers_set
        
        if missing:
            raise ValueError(f"CSV missing required fields after mapping: {', '.join(sorted(missing))}")

        processed_rows = []
        for line_no, row in enumerate(reader, start=header_row + 2):
            cleaned = {}

            for csv_column, db_column in mapped_headers.items():
                cleaned[db_column] = (row.get(csv_column) or "").strip()

            cleaned.setdefault("course", "")
            cleaned.setdefault("branch", "")
            cleaned.setdefault("cgpa", "")
            cleaned.setdefault("year", "")
            cleaned.setdefault("issue_date", "")
            cleaned.setdefault("verification_status", "valid")

            # Ignore empty strings or footer summaries
            if not cleaned.get("student_name") and not cleaned.get("roll_no") and not cleaned.get("certificate_id"):
                continue

            # Skip messy descriptive note blocks at the bottom of the data table cleanly
            if not cleaned.get("student_name") or not cleaned.get("roll_no") or not cleaned.get("certificate_id"):
                continue

            try:
                cleaned["cgpa"] = float(cleaned["cgpa"]) if cleaned["cgpa"] else None
            except ValueError:
                cleaned["cgpa"] = None

            processed_rows.append(cleaned)

    conn = get_connection(db_path)
    try:
        if replace:
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
            ON CONFLICT(roll_no) DO UPDATE SET
                student_name = excluded.student_name,
                certificate_id = excluded.certificate_id,
                course = excluded.course,
                branch = excluded.branch,
                cgpa = excluded.cgpa,
                year = excluded.year,
                issue_date = excluded.issue_date,
                verification_status = excluded.verification_status
            """,
            processed_rows,
        )
        conn.commit()
        return len(processed_rows)
    finally:
        conn.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="Import student records from CSV.")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="Replace all records")
    mode.add_argument("--append", action="store_true", help="Append records")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    import_csv(csv_path, Path(args.db), replace=args.replace)

if __name__ == "__main__":
    main()
