CREATE TABLE IF NOT EXISTS remember_me_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    device_info VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_remember_me_tokens_active_user
    ON remember_me_tokens (user_id, expires_at DESC)
    WHERE revoked_at IS NULL;
