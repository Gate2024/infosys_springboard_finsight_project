ALTER TABLE pending_registrations
    ADD COLUMN IF NOT EXISTS resend_count INTEGER NOT NULL DEFAULT 0;

WITH ranked_pending AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY lower(email)
               ORDER BY created_at DESC, id DESC
           ) AS row_number
    FROM pending_registrations
    WHERE consumed_at IS NULL
)
UPDATE pending_registrations
SET consumed_at = CURRENT_TIMESTAMP
WHERE id IN (
    SELECT id FROM ranked_pending WHERE row_number > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_registrations_active_email
    ON pending_registrations (lower(email))
    WHERE consumed_at IS NULL;
