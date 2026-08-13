CREATE TABLE IF NOT EXISTS investments (
    investment_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_name VARCHAR(150) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL CHECK (quantity > 0),
    purchase_price NUMERIC(14, 2) NOT NULL CHECK (purchase_price >= 0),
    purchase_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investments_user_id
    ON investments(user_id);

CREATE INDEX IF NOT EXISTS idx_investments_user_purchase_date
    ON investments(user_id, purchase_date DESC);
