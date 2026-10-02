ALTER TABLE users
    ADD COLUMN IF NOT EXISTS date_of_birth DATE,
    ADD COLUMN IF NOT EXISTS address TEXT,
    ADD COLUMN IF NOT EXISTS profile_image_data BYTEA,
    ADD COLUMN IF NOT EXISTS profile_image_mime VARCHAR(50);
