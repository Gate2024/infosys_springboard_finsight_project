CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (lower(email));

CREATE TABLE IF NOT EXISTS budgets (
    budget_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_name VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(80) NOT NULL,
    budget_amount NUMERIC(14, 2) NOT NULL CHECK (budget_amount >= 0),
    spent_amount NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (spent_amount >= 0),
    remaining_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
    expected_income NUMERIC(14, 2) NOT NULL DEFAULT 0,
    expected_expenses NUMERIC(14, 2) NOT NULL DEFAULT 0,
    savings_goal NUMERIC(14, 2) NOT NULL DEFAULT 0,
    alert_percentage INTEGER NOT NULL DEFAULT 80,
    color_label VARCHAR(20) NOT NULL DEFAULT '#0E5A4E',
    budget_icon VARCHAR(80) NOT NULL DEFAULT 'fa-wallet',
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_budgets_user_id
    ON budgets (user_id);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    type VARCHAR(20) NOT NULL DEFAULT 'Expense',
    category VARCHAR(80) NOT NULL,
    date DATE NOT NULL,
    description TEXT,
    payment_mode VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id
    ON transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_type
    ON transactions (user_id, type);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON transactions (user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_user_category
    ON transactions (user_id, category);
