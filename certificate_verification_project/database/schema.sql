-- Official student/certificate registry.
-- Column names stay stable so CSV/Excel/MySQL imports map directly.

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL,
    roll_no TEXT NOT NULL UNIQUE,
    certificate_id TEXT NOT NULL UNIQUE,
    course TEXT,
    branch TEXT,
    cgpa REAL,
    year TEXT,
    issue_date TEXT,
    verification_status TEXT NOT NULL DEFAULT 'issued'
);

CREATE INDEX IF NOT EXISTS idx_students_roll_no ON students (roll_no);
CREATE INDEX IF NOT EXISTS idx_students_certificate_id ON students (certificate_id);
