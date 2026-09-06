ALTER TABLE users
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(30);

CREATE TABLE IF NOT EXISTS pending_registrations (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(320) NOT NULL,
    mobile_number VARCHAR(30) NOT NULL,
    password_hash TEXT NOT NULL,
    otp_hash CHAR(64) NOT NULL,
    otp_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    otp_attempts INTEGER NOT NULL DEFAULT 0 CHECK (otp_attempts >= 0),
    last_sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP WITH TIME ZONE,
    consumed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_pending_registrations_email
    ON pending_registrations (lower(email), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pending_registrations_active
    ON pending_registrations (id, otp_expires_at)
    WHERE consumed_at IS NULL;
