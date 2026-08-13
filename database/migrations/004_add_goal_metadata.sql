ALTER TABLE goals
    ADD COLUMN IF NOT EXISTS status VARCHAR(20);

UPDATE goals
SET status = CASE
    WHEN current_amount >= target_amount THEN 'Completed'
    ELSE 'Active'
END
WHERE status IS NULL;

ALTER TABLE goals
    ALTER COLUMN status SET DEFAULT 'Active',
    ALTER COLUMN status SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'goals_status_valid'
    ) THEN
        ALTER TABLE goals
            ADD CONSTRAINT goals_status_valid
            CHECK (status IN ('Active', 'Completed'));
    END IF;
END $$;

ALTER TABLE goals
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE;

UPDATE goals
SET created_at = CURRENT_TIMESTAMP
WHERE created_at IS NULL;

ALTER TABLE goals
    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE goals
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

UPDATE goals
SET updated_at = CURRENT_TIMESTAMP
WHERE updated_at IS NULL;

ALTER TABLE goals
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN updated_at SET NOT NULL;
