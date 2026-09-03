CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) NOT NULL DEFAULT 'default'
        CHECK (theme IN ('default', 'light', 'dark')),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD'
        CHECK (currency ~ '^[A-Z]{3}$'),
    language VARCHAR(10) NOT NULL DEFAULT 'en'
        CHECK (length(trim(language)) BETWEEN 2 AND 10),
    budget_overspending_alerts BOOLEAN NOT NULL DEFAULT FALSE,
    weekly_savings_digest_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    sip_due_date_reminders_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    bill_due_date_reminders_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
