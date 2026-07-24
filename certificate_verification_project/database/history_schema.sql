-- Upload and verification audit log for the dashboard.

CREATE TABLE IF NOT EXISTS verification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    uploaded_filename TEXT,
    certificate_file TEXT,
    student_name TEXT,
    roll_no TEXT,
    certificate_id TEXT,
    qr_status TEXT,
    verification_result TEXT,
    fraud_risk TEXT,
    blockchain_hash_status TEXT,
    hash_value TEXT,
    verification_timestamp TEXT NOT NULL,
    verified_copy_filename TEXT,
    workflow TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_batch_id ON verification_history (batch_id);
CREATE INDEX IF NOT EXISTS idx_history_verified_at ON verification_history (verification_timestamp DESC);
