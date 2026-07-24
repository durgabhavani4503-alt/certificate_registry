-- Stored QR verification records (from successful verifications / reports).
CREATE TABLE IF NOT EXISTS verification_records (
    certificate_id TEXT PRIMARY KEY,
    verification_id TEXT NOT NULL,
    hash_value TEXT NOT NULL,
    verification_timestamp TEXT NOT NULL,
    record_status TEXT NOT NULL DEFAULT 'active'
);

-- Every upload check (dashboard + audit log).
CREATE TABLE IF NOT EXISTS verification_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    uploaded_filename TEXT NOT NULL,
    certificate_file TEXT,
    verification_method TEXT NOT NULL,
    extracted_data TEXT,
    status TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    verification_timestamp TEXT NOT NULL,
    message TEXT,
    student_name TEXT,
    roll_no TEXT,
    certificate_id TEXT,
    report_filename TEXT
);

CREATE INDEX IF NOT EXISTS idx_results_timestamp ON verification_results (verification_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_results_status ON verification_results (status);
