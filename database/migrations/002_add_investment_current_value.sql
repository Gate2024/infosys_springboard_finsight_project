ALTER TABLE investments
    ADD COLUMN IF NOT EXISTS current_value NUMERIC(14, 2);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'investments_current_value_nonnegative'
    ) THEN
        ALTER TABLE investments
            ADD CONSTRAINT investments_current_value_nonnegative
            CHECK (current_value IS NULL OR current_value >= 0);
    END IF;
END $$;
