CREATE TABLE IF NOT EXISTS password_reset_challenges (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    otp_hash CHAR(64) NOT NULL,
    otp_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    otp_attempts INTEGER NOT NULL DEFAULT 0 CHECK (otp_attempts >= 0),
    last_sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resend_count INTEGER NOT NULL DEFAULT 0 CHECK (resend_count >= 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP WITH TIME ZONE,
    reset_token_hash CHAR(64) UNIQUE,
    reset_token_expires_at TIMESTAMP WITH TIME ZONE,
    consumed_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_password_reset_active_user
    ON password_reset_challenges (user_id)
    WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_password_reset_email_recent
    ON password_reset_challenges (lower(email), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_password_reset_active_expiry
    ON password_reset_challenges (id, otp_expires_at)
    WHERE consumed_at IS NULL;
