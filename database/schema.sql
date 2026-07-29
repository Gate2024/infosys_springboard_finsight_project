-- PostgreSQL Database Initialization Script for Budget Creation & Monitoring Module

-- Drop existing tables if re-initializing schema
DROP TABLE IF EXISTS budgets CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. Users Table (Pre-existing authentication compatibility)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert Default Demo User (ID = 1) for seamless testing
INSERT INTO users (id, username, email, password_hash)
VALUES (1, 'alex_fintech', 'alex@luxurybudget.com', '$2b$12$eImiTXuWVxfM37uY4JANjOL.gZq.8W.x3wz99d.5d5g1x3h4y5z6')
ON CONFLICT (id) DO NOTHING;

-- Reset sequence for users table
SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));

-- 2. Budgets Table (Core Budget Module Table)
CREATE TABLE budgets (
    budget_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_name VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    budget_amount NUMERIC(12, 2) NOT NULL CHECK (budget_amount >= 0),
    spent_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (spent_amount >= 0),
    remaining_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Completed', 'Archived')),
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Low', 'Medium', 'High', 'Urgent')),
    expected_income NUMERIC(12, 2) DEFAULT 0.00 CHECK (expected_income >= 0),
    expected_expenses NUMERIC(12, 2) DEFAULT 0.00 CHECK (expected_expenses >= 0),
    savings_goal NUMERIC(12, 2) DEFAULT 0.00 CHECK (savings_goal >= 0),
    alert_percentage INT DEFAULT 80 CHECK (alert_percentage BETWEEN 1 AND 100),
    color_label VARCHAR(20) DEFAULT '#0E5A4E',
    budget_icon VARCHAR(50) DEFAULT 'fa-wallet',
    is_recurring BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for optimized querying, filtering, and sorting
CREATE INDEX idx_budgets_user_id ON budgets(user_id);
CREATE INDEX idx_budgets_status ON budgets(status);
CREATE INDEX idx_budgets_category ON budgets(category);
CREATE INDEX idx_budgets_priority ON budgets(priority);
CREATE INDEX idx_budgets_dates ON budgets(start_date, end_date);

-- Trigger Function to automatically update the updated_at timestamp on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_budgets_modtime
BEFORE UPDATE ON budgets
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
