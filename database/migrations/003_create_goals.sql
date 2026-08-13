CREATE TABLE IF NOT EXISTS goals (
    goal_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_name VARCHAR(150) NOT NULL,
    goal_category VARCHAR(50) NOT NULL,
    target_amount NUMERIC(14, 2) NOT NULL CHECK (target_amount > 0),
    current_amount NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (current_amount >= 0),
    target_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Active', 'Completed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_goals_user_id
    ON goals(user_id);

CREATE INDEX IF NOT EXISTS idx_goals_user_target_date
    ON goals(user_id, target_date ASC);
