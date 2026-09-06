import os
import hashlib
import hmac
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config


DATABASE_SSL_MODES = {
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full",
}


def _is_production_environment():
    production_values = {"production", "prod"}
    environment_names = ("FLASK_ENV", "APP_ENV", "ENVIRONMENT", "VERCEL_ENV", "ENV")
    return any(
        os.getenv(name, "").strip().lower() in production_values
        for name in environment_names
    )


def _database_sslmode():
    configured_mode = (Config.DB_SSLMODE or "").strip().lower()
    sslmode = configured_mode or ("require" if _is_production_environment() else None)
    if sslmode and sslmode not in DATABASE_SSL_MODES:
        raise RuntimeError(
            "DB_SSLMODE must be one of disable, allow, prefer, require, verify-ca, or verify-full."
        )
    if _is_production_environment() and sslmode in {"disable", "allow", "prefer"}:
        raise RuntimeError(
            "DB_SSLMODE must require encrypted PostgreSQL connections in production."
        )
    return sslmode


def _connection_kwargs():
    kwargs = {
        "host": Config.DB_HOST,
        "database": Config.DB_NAME,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
        "port": Config.DB_PORT or 5432,
        "cursor_factory": RealDictCursor,
    }
    sslmode = _database_sslmode()
    if sslmode:
        kwargs["sslmode"] = sslmode
    if Config.DB_SSLROOTCERT:
        kwargs["sslrootcert"] = Config.DB_SSLROOTCERT
    return kwargs


@contextmanager
def get_connection():
    conn = psycopg2.connect(**_connection_kwargs())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def init_db():
    return True


def _to_float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


def _to_int(value, default=0):
    if value in (None, ""):
        return default
    return int(value)


def _to_bool(value):
    return value in (True, "true", "True", "1", 1, "on", "yes", "Yes")


def _clean_budget_data(data):
    budget_amount = _to_float(data.get("budget_amount"), 0.0)
    spent_amount = _to_float(data.get("spent_amount"), 0.0)

    return {
        "budget_name": data.get("budget_name", "").strip(),
        "description": data.get("description", "").strip(),
        "category": data.get("category", "").strip(),
        "budget_amount": budget_amount,
        "spent_amount": spent_amount,
        "remaining_amount": budget_amount - spent_amount,
        "currency": data.get("currency") or "USD",
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "status": data.get("status") or "Active",
        "priority": data.get("priority") or "Medium",
        "expected_income": _to_float(data.get("expected_income"), 0.0),
        "expected_expenses": _to_float(data.get("expected_expenses"), 0.0),
        "savings_goal": _to_float(data.get("savings_goal"), 0.0),
        "alert_percentage": _to_int(data.get("alert_percentage"), 80),
        "color_label": data.get("color_label") or "#0E5A4E",
        "budget_icon": data.get("budget_icon") or "fa-wallet",
        "is_recurring": _to_bool(data.get("is_recurring")),
        "notes": data.get("notes", "").strip(),
    }


def _json_ready(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_row(row):
    if not row:
        return None
    return {key: _json_ready(value) for key, value in dict(row).items()}


def serialize_rows(rows):
    return [serialize_row(row) for row in rows]


def registration_otp_digest(otp):
    pepper = Config.SECRET_KEY
    if not isinstance(pepper, str) or not pepper:
        raise RuntimeError("Registration OTP pepper is not configured.")
    return hmac.new(
        pepper.encode("utf-8"),
        str(otp).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _registration_username(full_name, email):
    """Return a stable, non-display username that remains unique per email."""
    digest = hashlib.sha256(
        f"{full_name}\x00{email}".encode("utf-8")
    ).hexdigest()[:32]
    return f"fs_{digest}"


def register_user(username, email, password):
    """Create a legacy registration while enforcing uniqueness by email only."""
    email = str(email or "").strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT email FROM users WHERE lower(email) = lower(%s)",
                (email,),
            )
            existing_user = cursor.fetchone()
            if existing_user:
                return False, "Email already exists."

            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, display_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id, display_name AS username, email
                """,
                (
                    _registration_username(username, email),
                    email,
                    generate_password_hash(password),
                    username,
                ),
            )
            return True, serialize_row(cursor.fetchone())


def login_user(email, password):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id,
                       COALESCE(NULLIF(to_jsonb(users)->>'display_name', ''), username)
                           AS username,
                       email, password_hash
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return False, None

    return True, serialize_row({key: user[key] for key in ("id", "username", "email")})


def create_pending_registration(full_name, email, mobile_number, password_hash, otp_hash, expires_at):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM users
                WHERE lower(email) = lower(%s)
                LIMIT 1
                """,
                (email,),
            )
            if cursor.fetchone():
                return None
            cursor.execute(
                """
                UPDATE pending_registrations
                SET consumed_at = CURRENT_TIMESTAMP
                WHERE lower(email) = lower(%s) AND consumed_at IS NULL
                """,
                (email,),
            )
            cursor.execute(
                """
                INSERT INTO pending_registrations (
                    full_name, email, mobile_number, password_hash,
                    otp_hash, otp_expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (full_name, email, mobile_number, password_hash, otp_hash, expires_at),
            )
            return serialize_row(cursor.fetchone())


def get_pending_registration(pending_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, full_name, email, mobile_number, password_hash,
                       otp_hash, otp_expires_at, otp_attempts, last_sent_at,
                       resend_count,
                       created_at, verified_at, consumed_at
                FROM pending_registrations
                WHERE id = %s AND consumed_at IS NULL
                """,
                (pending_id,),
            )
            return serialize_row(cursor.fetchone())


def get_registration_resend_status(pending_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT resend_count,
                       last_sent_at,
                       GREATEST(
                           0,
                           CEIL(EXTRACT(EPOCH FROM (
                               last_sent_at + INTERVAL '60 seconds'
                               - CURRENT_TIMESTAMP
                           )))
                       )::INTEGER AS remaining_seconds,
                       resend_count < 5
                       AND last_sent_at <= CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                       AS can_resend
                FROM pending_registrations
                WHERE id = %s AND consumed_at IS NULL
                """,
                (pending_id,),
            )
            return serialize_row(cursor.fetchone())


def replace_pending_registration_otp(pending_id, otp_hash, expires_at):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pending_registrations
                SET otp_hash = %s,
                    otp_expires_at = %s,
                    otp_attempts = 0,
                    last_sent_at = CURRENT_TIMESTAMP,
                    resend_count = resend_count + 1
                WHERE id = %s AND consumed_at IS NULL
                  AND resend_count < 5
                  AND last_sent_at <= CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                RETURNING id, email
                """,
                (otp_hash, expires_at, pending_id),
            )
            return serialize_row(cursor.fetchone())


def complete_pending_registration(pending_id, otp_hash, now=None):
    now = now or datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, full_name, email, mobile_number, password_hash, otp_hash,
                       otp_expires_at, otp_attempts
                FROM pending_registrations
                WHERE id = %s AND consumed_at IS NULL
                FOR UPDATE
                """,
                (pending_id,),
            )
            pending = cursor.fetchone()
            if not pending:
                return False, "invalid"
            if pending["otp_attempts"] >= 5:
                return False, "attempts"
            if pending["otp_expires_at"] <= now:
                return False, "expired"

            cursor.execute(
                """
                UPDATE pending_registrations
                SET otp_attempts = otp_attempts + 1
                WHERE id = %s
                """,
                (pending_id,),
            )
            if not hmac.compare_digest(pending["otp_hash"], otp_hash):
                return False, "invalid"

            cursor.execute(
                """
                INSERT INTO users (
                    username, email, mobile_number, password_hash, display_name
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id, display_name AS username, email
                """,
                (
                    _registration_username(pending["full_name"], pending["email"]),
                    pending["email"],
                    pending["mobile_number"],
                    pending["password_hash"],
                    pending["full_name"],
                ),
            )
            user = serialize_row(cursor.fetchone())
            if not user:
                return False, "already_registered"
            cursor.execute(
                """
                UPDATE pending_registrations
                SET verified_at = CURRENT_TIMESTAMP, consumed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (pending_id,),
            )
            return True, user


def get_user_for_password_reset(email):
    """Return only the account identity needed to issue a reset challenge."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email
                FROM users
                WHERE lower(email) = lower(%s)
                LIMIT 1
                """,
                (email,),
            )
            return serialize_row(cursor.fetchone())


def get_password_reset_challenge(user_id):
    """Return the latest unconsumed reset challenge for one user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, email, otp_expires_at, otp_attempts,
                       last_sent_at, resend_count, created_at, verified_at,
                       reset_token_expires_at, consumed_at
                FROM password_reset_challenges
                WHERE user_id = %s AND consumed_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return serialize_row(cursor.fetchone())


def get_password_reset_challenge_by_id(challenge_id):
    """Return an unconsumed reset challenge by id."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, email, otp_expires_at, otp_attempts,
                       last_sent_at, resend_count, created_at, verified_at,
                       reset_token_expires_at, consumed_at
                FROM password_reset_challenges
                WHERE id = %s AND consumed_at IS NULL
                """,
                (challenge_id,),
            )
            return serialize_row(cursor.fetchone())


def create_password_reset_challenge(user_id, email, otp_hash, expires_at):
    """Create one reset challenge after an OTP has been delivered."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                WITH expired AS (
                    UPDATE password_reset_challenges
                    SET consumed_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                      AND consumed_at IS NULL
                      AND (
                          otp_expires_at <= CURRENT_TIMESTAMP
                          OR (
                              reset_token_expires_at IS NOT NULL
                              AND reset_token_expires_at <= CURRENT_TIMESTAMP
                          )
                      )
                    RETURNING id
                )
                INSERT INTO password_reset_challenges (
                    user_id, email, otp_hash, otp_expires_at,
                    last_sent_at, resend_count
                )
                SELECT %s, %s, %s, %s, CURRENT_TIMESTAMP, 0
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM password_reset_challenges
                    WHERE user_id = %s AND consumed_at IS NULL
                )
                ON CONFLICT DO NOTHING
                RETURNING id, user_id, email, otp_expires_at, otp_attempts,
                          last_sent_at, resend_count, created_at,
                          verified_at, reset_token_expires_at, consumed_at
                """,
                (user_id, user_id, email, otp_hash, expires_at, user_id),
            )
            return serialize_row(cursor.fetchone())


def get_password_reset_resend_status(challenge_id):
    """Return persisted resend state without exposing challenge secrets."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT resend_count, last_sent_at,
                       GREATEST(
                           0,
                           CEIL(EXTRACT(EPOCH FROM (
                               last_sent_at + INTERVAL '60 seconds'
                               - CURRENT_TIMESTAMP
                           )))
                       )::INTEGER AS remaining_seconds,
                       otp_expires_at <= CURRENT_TIMESTAMP AS otp_expired,
                       verified_at IS NULL
                       AND consumed_at IS NULL
                       AND resend_count < 5
                       AND last_sent_at <= CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                       AS can_resend
                FROM password_reset_challenges
                WHERE id = %s AND consumed_at IS NULL
                """,
                (challenge_id,),
            )
            return serialize_row(cursor.fetchone())


def replace_password_reset_otp(challenge_id, otp_hash, expires_at):
    """Atomically replace an OTP after cooldown and resend-limit checks."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE password_reset_challenges
                SET otp_hash = %s,
                    otp_expires_at = %s,
                    otp_attempts = 0,
                    last_sent_at = CURRENT_TIMESTAMP,
                    resend_count = resend_count + 1
                WHERE id = %s
                  AND consumed_at IS NULL
                  AND verified_at IS NULL
                  AND resend_count < 5
                  AND last_sent_at <= CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                RETURNING id, user_id, email, otp_expires_at, otp_attempts,
                          last_sent_at, resend_count, created_at,
                          verified_at, reset_token_expires_at, consumed_at
                """,
                (otp_hash, expires_at, challenge_id),
            )
            return serialize_row(cursor.fetchone())


def verify_password_reset_otp(
    challenge_id, otp_hash, reset_token_hash, reset_token_expires_at, now=None
):
    """Verify an OTP under lock and create one short-lived reset authorization."""
    now = now or datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, otp_hash, otp_expires_at, otp_attempts,
                       verified_at, consumed_at
                FROM password_reset_challenges
                WHERE id = %s
                FOR UPDATE
                """,
                (challenge_id,),
            )
            challenge = cursor.fetchone()
            if not challenge or challenge["consumed_at"] is not None:
                return False, "consumed"
            if challenge["verified_at"] is not None:
                return False, "consumed"
            if challenge["otp_attempts"] >= 5:
                return False, "attempts"
            if challenge["otp_expires_at"] <= now:
                return False, "expired"

            cursor.execute(
                """
                UPDATE password_reset_challenges
                SET otp_attempts = otp_attempts + 1
                WHERE id = %s
                """,
                (challenge_id,),
            )
            if not hmac.compare_digest(challenge["otp_hash"], otp_hash):
                return False, "invalid"

            cursor.execute(
                """
                UPDATE password_reset_challenges
                SET verified_at = CURRENT_TIMESTAMP,
                    reset_token_hash = %s,
                    reset_token_expires_at = %s
                WHERE id = %s
                  AND verified_at IS NULL
                  AND consumed_at IS NULL
                RETURNING id
                """,
                (reset_token_hash, reset_token_expires_at, challenge_id),
            )
            return (cursor.fetchone() is not None), "verified"


def get_password_reset_authorization(challenge_id):
    """Check whether one challenge still has a live reset authorization."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id
                FROM password_reset_challenges
                WHERE id = %s
                  AND verified_at IS NOT NULL
                  AND reset_token_hash IS NOT NULL
                  AND reset_token_expires_at > CURRENT_TIMESTAMP
                  AND consumed_at IS NULL
                """,
                (challenge_id,),
            )
            return serialize_row(cursor.fetchone())


def reset_password_with_authorization(challenge_id, password_hash):
    """Reset a password and revoke all sessions and persistent credentials atomically."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id
                FROM password_reset_challenges
                WHERE id = %s
                  AND verified_at IS NOT NULL
                  AND reset_token_hash IS NOT NULL
                  AND reset_token_expires_at > CURRENT_TIMESTAMP
                  AND consumed_at IS NULL
                FOR UPDATE
                """,
                (challenge_id,),
            )
            authorization = cursor.fetchone()
            if not authorization:
                return False

            user_id = authorization["user_id"]
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
                RETURNING id
                """,
                (password_hash, user_id),
            )
            if cursor.fetchone() is None:
                return False

            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (user_id,),
            )
            cursor.execute(
                """
                UPDATE remember_me_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (user_id,),
            )
            cursor.execute(
                """
                UPDATE password_reset_challenges
                SET consumed_at = CURRENT_TIMESTAMP,
                    reset_token_hash = NULL,
                    reset_token_expires_at = NULL
                WHERE id = %s AND consumed_at IS NULL
                RETURNING id
                """,
                (challenge_id,),
            )
            return cursor.fetchone() is not None


def get_user_by_id(user_id):
    """Return only the user fields safe to display in a profile view."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id,
                       COALESCE(NULLIF(to_jsonb(users)->>'display_name', ''), username)
                           AS username,
                       email
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            return serialize_row(cursor.fetchone())


def create_budget(user_id, data):
    payload = _clean_budget_data(data)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO budgets (
                    user_id, budget_name, description, category, budget_amount,
                    spent_amount, remaining_amount, currency, start_date, end_date,
                    status, priority, expected_income, expected_expenses, savings_goal,
                    alert_percentage, color_label, budget_icon, is_recurring, notes
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING budget_id
                """,
                (
                    user_id,
                    payload["budget_name"],
                    payload["description"],
                    payload["category"],
                    payload["budget_amount"],
                    payload["spent_amount"],
                    payload["remaining_amount"],
                    payload["currency"],
                    payload["start_date"],
                    payload["end_date"],
                    payload["status"],
                    payload["priority"],
                    payload["expected_income"],
                    payload["expected_expenses"],
                    payload["savings_goal"],
                    payload["alert_percentage"],
                    payload["color_label"],
                    payload["budget_icon"],
                    payload["is_recurring"],
                    payload["notes"],
                ),
            )
            return serialize_row(cursor.fetchone())


def get_all_budgets(user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return serialize_rows(cursor.fetchall())


def filter_budgets(
    user_id,
    search_query="",
    category_filter="All",
    status_filter="All",
    priority_filter="All",
    sort_by="newest",
):
    clauses = ["user_id = %s"]
    params = [user_id]

    if search_query:
        clauses.append(
            "(budget_name ILIKE %s OR category ILIKE %s OR description ILIKE %s OR notes ILIKE %s)"
        )
        term = f"%{search_query}%"
        params.extend([term, term, term, term])

    if category_filter and category_filter != "All":
        clauses.append("category = %s")
        params.append(category_filter)

    if status_filter and status_filter != "All":
        clauses.append("status = %s")
        params.append(status_filter)

    if priority_filter and priority_filter != "All":
        clauses.append("priority = %s")
        params.append(priority_filter)

    order_by = {
        "oldest": "created_at ASC",
        "amount_desc": "budget_amount DESC",
        "amount_asc": "budget_amount ASC",
    }.get(sort_by, "created_at DESC")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT *
                FROM budgets
                WHERE {" AND ".join(clauses)}
                ORDER BY {order_by}
                """,
                tuple(params),
            )
            return serialize_rows(cursor.fetchall())


def get_budget(budget_id, user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM budgets
                WHERE budget_id = %s AND user_id = %s
                """,
                (budget_id, user_id),
            )
            return serialize_row(cursor.fetchone())


def update_budget(budget_id, user_id, data):
    payload = _clean_budget_data(data)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE budgets
                SET
                    budget_name = %s,
                    description = %s,
                    category = %s,
                    budget_amount = %s,
                    spent_amount = %s,
                    remaining_amount = %s,
                    currency = %s,
                    start_date = %s,
                    end_date = %s,
                    status = %s,
                    priority = %s,
                    expected_income = %s,
                    expected_expenses = %s,
                    savings_goal = %s,
                    alert_percentage = %s,
                    color_label = %s,
                    budget_icon = %s,
                    is_recurring = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE budget_id = %s AND user_id = %s
                """,
                (
                    payload["budget_name"],
                    payload["description"],
                    payload["category"],
                    payload["budget_amount"],
                    payload["spent_amount"],
                    payload["remaining_amount"],
                    payload["currency"],
                    payload["start_date"],
                    payload["end_date"],
                    payload["status"],
                    payload["priority"],
                    payload["expected_income"],
                    payload["expected_expenses"],
                    payload["savings_goal"],
                    payload["alert_percentage"],
                    payload["color_label"],
                    payload["budget_icon"],
                    payload["is_recurring"],
                    payload["notes"],
                    budget_id,
                    user_id,
                ),
            )
            return cursor.rowcount > 0


def delete_budget(budget_id, user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM budgets
                WHERE budget_id=%s
                AND user_id=%s
                """,
                (budget_id, user_id),
            )

            return cursor.rowcount > 0


def get_summary_stats(user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_budgets,
                    COUNT(*) FILTER (WHERE status = 'Active') AS active_budgets,
                    COUNT(*) FILTER (WHERE status = 'Completed') AS completed_budgets,
                    COALESCE(SUM(budget_amount), 0) AS total_allocated,
                    COALESCE(SUM(spent_amount), 0) AS total_spent,
                    COALESCE(SUM(remaining_amount), 0) AS total_remaining
                FROM budgets
                WHERE user_id = %s
                """,
                (user_id,),
            )
            stats = serialize_row(cursor.fetchone())

    return {
        "total_budgets": stats.get("total_budgets", 0),
        "active_budgets": stats.get("active_budgets", 0),
        "completed_budgets": stats.get("completed_budgets", 0),
        "total_allocated": stats.get("total_allocated", 0.0),
        "total_spent": stats.get("total_spent", 0.0),
        "total_remaining": stats.get("total_remaining", 0.0),
    }


def ensure_transactions_table():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
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
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_user_id
                ON transactions(user_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_user_type
                ON transactions(user_id, type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_user_date
                ON transactions(user_id, date DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_user_category
                ON transactions(user_id, category)
                """
            )


def _clean_transaction_data(data):
    return {
        "amount": _to_float(data.get("amount"), 0.0),
        "category": data.get("category", "").strip(),
        "date": data.get("date"),
        "description": data.get("description", "").strip(),
        "payment_mode": data.get("payment_mode", "").strip(),
    }


def create_transaction(user_id, data):
    ensure_transactions_table()
    payload = _clean_transaction_data(data)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO transactions (
                    user_id, amount, type, category, date, description, payment_mode
                )
                VALUES (%s, %s, 'Expense', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    payload["amount"],
                    payload["category"],
                    payload["date"],
                    payload["description"],
                    payload["payment_mode"],
                ),
            )
            return serialize_row(cursor.fetchone())


def get_transactions(
    user_id,
    search_query="",
    category_filter="All",
    payment_filter="All",
    sort_by="newest",
):
    ensure_transactions_table()
    clauses = ["user_id = %s", "type = 'Expense'"]
    params = [user_id]

    if search_query:
        clauses.append("(description ILIKE %s OR category ILIKE %s OR payment_mode ILIKE %s)")
        term = f"%{search_query}%"
        params.extend([term, term, term])

    if category_filter and category_filter != "All":
        clauses.append("category = %s")
        params.append(category_filter)

    if payment_filter and payment_filter != "All":
        clauses.append("payment_mode = %s")
        params.append(payment_filter)

    order_by = {
        "oldest": "date ASC, created_at ASC",
        "amount_desc": "amount DESC",
        "amount_asc": "amount ASC",
    }.get(sort_by, "date DESC, created_at DESC")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT *
                FROM transactions
                WHERE {" AND ".join(clauses)}
                ORDER BY {order_by}
                """,
                tuple(params),
            )
            return serialize_rows(cursor.fetchall())


def get_transaction(transaction_id, user_id):
    ensure_transactions_table()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM transactions
                WHERE id = %s
                AND user_id = %s
                AND type = 'Expense'
                """,
                (transaction_id, user_id),
            )
            return serialize_row(cursor.fetchone())


def update_transaction(transaction_id, user_id, data):
    ensure_transactions_table()
    payload = _clean_transaction_data(data)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE transactions
                SET
                    amount = %s,
                    category = %s,
                    date = %s,
                    description = %s,
                    payment_mode = %s,
                    updated_at = NOW()
                WHERE id = %s
                AND user_id = %s
                AND type = 'Expense'
                """,
                (
                    payload["amount"],
                    payload["category"],
                    payload["date"],
                    payload["description"],
                    payload["payment_mode"],
                    transaction_id,
                    user_id,
                ),
            )
            return cursor.rowcount > 0


def delete_transaction(transaction_id, user_id):
    ensure_transactions_table()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM transactions
                WHERE id = %s
                AND user_id = %s
                AND type = 'Expense'
                """,
                (transaction_id, user_id),
            )
            return cursor.rowcount > 0


def get_expense_summary(user_id):
    ensure_transactions_table()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_expenses,
                    COALESCE(SUM(amount), 0) AS total_spent,
                    COALESCE(AVG(amount), 0) AS average_expense,
                    COALESCE(MAX(amount), 0) AS largest_expense,
                    COUNT(*) FILTER (
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                        AND date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    ) AS month_expenses,
                    COALESCE(SUM(amount) FILTER (
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                        AND date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    ), 0) AS month_spent
                FROM transactions
                WHERE user_id = %s
                AND type = 'Expense'
                """,
                (user_id,),
            )
            summary = serialize_row(cursor.fetchone())

            cursor.execute(
                """
                SELECT category, COALESCE(SUM(amount), 0) AS total
                FROM transactions
                WHERE user_id = %s
                AND type = 'Expense'
                GROUP BY category
                ORDER BY total DESC
                LIMIT 1
                """,
                (user_id,),
            )
            top_category = serialize_row(cursor.fetchone())

    return {
        "total_expenses": summary.get("total_expenses", 0),
        "total_spent": summary.get("total_spent", 0.0),
        "average_expense": summary.get("average_expense", 0.0),
        "largest_expense": summary.get("largest_expense", 0.0),
        "month_expenses": summary.get("month_expenses", 0),
        "month_spent": summary.get("month_spent", 0.0),
        "top_category": top_category.get("category", "No data") if top_category else "No data",
    }


def get_monthly_expense_summary(user_id):
    """Return user-scoped expense totals grouped by calendar month."""
    ensure_transactions_table()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    TO_CHAR(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
                    COALESCE(SUM(amount), 0) AS amount
                FROM transactions
                WHERE user_id = %s
                AND type = 'Expense'
                GROUP BY DATE_TRUNC('month', date)
                ORDER BY DATE_TRUNC('month', date) ASC
                """,
                (user_id,),
            )
            return [
                {
                    "month": row["month"],
                    "amount": float(row["amount"] or 0),
                }
                for row in cursor.fetchall()
            ]


def create_notification(user_id, notification_type, title, message):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO notifications (user_id, type, title, message)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, type, title, message, is_read, created_at
                """,
                (user_id, notification_type, title, message),
            )
            return serialize_row(cursor.fetchone())


def get_notifications(user_id, filter_type="all", limit=None):
    filters = {
        "all": "",
        "unread": "AND is_read = FALSE",
        "alert": "AND type = 'alert'",
        "milestone": "AND type = 'milestone'",
    }
    where_filter = filters.get(filter_type, "")
    limit_clause = " LIMIT %s" if limit is not None else ""
    params = [user_id]
    if limit is not None:
        params.append(limit)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, user_id, type, title, message, is_read, created_at
                FROM notifications
                WHERE user_id = %s {where_filter}
                ORDER BY created_at DESC
                {limit_clause}
                """,
                tuple(params),
            )
            return serialize_rows(cursor.fetchall())


def get_unread_notification_count(user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS unread_count
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
            row = serialize_row(cursor.fetchone())
            return int(row.get("unread_count", 0))


def mark_notification_read(user_id, notification_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = %s AND user_id = %s
                """,
                (notification_id, user_id),
            )
            return cursor.rowcount > 0


def mark_all_notifications_read(user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE notifications
                SET is_read = TRUE
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
            return cursor.rowcount


USER_PREFERENCE_COLUMNS = (
    "user_id",
    "theme",
    "currency",
    "language",
    "budget_overspending_alerts",
    "weekly_savings_digest_enabled",
    "sip_due_date_reminders_enabled",
    "bill_due_date_reminders_enabled",
    "two_factor_enabled",
    "created_at",
    "updated_at",
)
USER_PREFERENCE_SELECT = ", ".join(USER_PREFERENCE_COLUMNS)
USER_PREFERENCE_BOOLEAN_FIELDS = (
    "budget_overspending_alerts",
    "weekly_savings_digest_enabled",
    "sip_due_date_reminders_enabled",
    "bill_due_date_reminders_enabled",
    "two_factor_enabled",
)


def list_preference_currencies():
    """Return display-safe currency metadata for the preferences form."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT code, display_name, symbol
                FROM preference_currencies
                ORDER BY sort_order, code
                """
            )
            return serialize_rows(cursor.fetchall())


def list_preference_languages():
    """Return display-safe language metadata for the preferences form."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT code, display_name
                FROM preference_languages
                ORDER BY sort_order, code
                """
            )
            return serialize_rows(cursor.fetchall())


def ensure_user_preferences(user_id):
    """Return a user's preferences, creating default settings when absent."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {USER_PREFERENCE_SELECT}
                FROM user_preferences
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    f"""
                    INSERT INTO user_preferences (user_id)
                    VALUES (%s)
                    ON CONFLICT (user_id) DO NOTHING
                    RETURNING {USER_PREFERENCE_SELECT}
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    f"""
                    SELECT {USER_PREFERENCE_SELECT}
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()

    return serialize_row(row)


def get_user_preferences(user_id):
    """Return existing preferences for a user without creating a record."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {USER_PREFERENCE_SELECT}
                FROM user_preferences
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return serialize_row(cursor.fetchone())


def _clean_user_preferences(data):
    cleaned = {}
    if "theme" in data:
        cleaned["theme"] = str(data.get("theme") or "").strip().lower()
    if "currency" in data:
        cleaned["currency"] = str(data.get("currency") or "").strip().upper()
    if "language" in data:
        cleaned["language"] = str(data.get("language") or "").strip()
    for field in USER_PREFERENCE_BOOLEAN_FIELDS:
        if field in data:
            cleaned[field] = _to_bool(data.get(field))
    return cleaned


def update_user_preferences(user_id, data):
    """Update only preference fields for the authenticated user's record."""
    payload = _clean_user_preferences(data)
    if not payload:
        return get_user_preferences(user_id)

    assignments = [f"{field} = %s" for field in payload]
    values = list(payload.values())
    values.append(user_id)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE user_preferences
                SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                RETURNING {USER_PREFERENCE_SELECT}
                """,
                tuple(values),
            )
            return serialize_row(cursor.fetchone())


USER_SESSION_SELECT = """
    id,
    device_info,
    ip_address,
    created_at,
    last_active_at
"""


def create_user_session(user_id, session_token_hash, device_info, ip_address):
    """Persist the hash of a newly authenticated browser session."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO user_sessions (
                    user_id, session_token_hash, device_info, ip_address
                )
                VALUES (%s, %s, %s, %s)
                RETURNING {USER_SESSION_SELECT}
                """,
                (user_id, session_token_hash, device_info, ip_address),
            )
            return serialize_row(cursor.fetchone())


def is_user_session_active(
    user_id,
    session_token_hash,
    inactivity_timeout_seconds,
    absolute_timeout_seconds,
):
    """Validate, expire, and record activity for one tracked session."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                WITH session_row AS (
                    SELECT id,
                           last_active_at <= CURRENT_TIMESTAMP
                               - (%s * INTERVAL '1 second') AS inactivity_expired,
                           created_at <= CURRENT_TIMESTAMP
                               - (%s * INTERVAL '1 second') AS absolute_expired
                    FROM user_sessions
                    WHERE user_id = %s
                      AND session_token_hash = %s
                      AND revoked_at IS NULL
                    FOR UPDATE
                ), expired AS (
                    UPDATE user_sessions AS sessions
                    SET revoked_at = CURRENT_TIMESTAMP
                    FROM session_row
                    WHERE sessions.id = session_row.id
                      AND (session_row.inactivity_expired OR session_row.absolute_expired)
                    RETURNING sessions.id
                )
                UPDATE user_sessions AS sessions
                SET last_active_at = CURRENT_TIMESTAMP
                FROM session_row
                WHERE sessions.id = session_row.id
                  AND NOT session_row.inactivity_expired
                  AND NOT session_row.absolute_expired
                RETURNING sessions.id
                """,
                (
                    inactivity_timeout_seconds,
                    absolute_timeout_seconds,
                    user_id,
                    session_token_hash,
                ),
            )
            return cursor.fetchone() is not None


def create_remember_me_token(
    user_id, token_hash, lifetime_seconds, device_info, ip_address
):
    """Store only a hashed, finite-lived persistent-login credential."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO remember_me_tokens (
                    user_id, token_hash, expires_at, device_info, ip_address
                )
                VALUES (
                    %s,
                    %s,
                    CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    %s,
                    %s
                )
                RETURNING id, user_id, created_at, expires_at
                """,
                (user_id, token_hash, lifetime_seconds, device_info, ip_address),
            )
            return serialize_row(cursor.fetchone())


def rotate_remember_me_token(
    token_hash, new_token_hash, lifetime_seconds, device_info, ip_address
):
    """Atomically consume one persistent credential and issue its replacement."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                WITH existing AS (
                    SELECT id, user_id
                    FROM remember_me_tokens
                    WHERE token_hash = %s
                      AND revoked_at IS NULL
                      AND expires_at > CURRENT_TIMESTAMP
                    FOR UPDATE
                ), revoked AS (
                    UPDATE remember_me_tokens AS tokens
                    SET revoked_at = CURRENT_TIMESTAMP,
                        last_used_at = CURRENT_TIMESTAMP
                    FROM existing
                    WHERE tokens.id = existing.id
                    RETURNING tokens.user_id
                )
                INSERT INTO remember_me_tokens (
                    user_id, token_hash, expires_at, device_info, ip_address
                )
                SELECT user_id,
                       %s,
                       CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                       %s,
                       %s
                FROM revoked
                RETURNING user_id
                """,
                (token_hash, new_token_hash, lifetime_seconds, device_info, ip_address),
            )
            row = cursor.fetchone()
            return row["user_id"] if row else None


def revoke_remember_me_token(user_id, token_hash):
    """Revoke one persistent credential for its owning user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE remember_me_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND token_hash = %s
                  AND revoked_at IS NULL
                RETURNING id
                """,
                (user_id, token_hash),
            )
            return cursor.fetchone() is not None


def revoke_all_remember_me_tokens(user_id):
    """Revoke every active persistent credential for one user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE remember_me_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )
            return cursor.rowcount


def list_active_user_sessions(user_id, current_session_token_hash):
    """Return display-safe active session details for one user only."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {USER_SESSION_SELECT},
                       session_token_hash = %s AS is_current
                FROM user_sessions
                WHERE user_id = %s
                  AND revoked_at IS NULL
                ORDER BY last_active_at DESC, id DESC
                """,
                (current_session_token_hash, user_id),
            )
            return serialize_rows(cursor.fetchall())


def revoke_user_session(session_id, user_id, current_session_token_hash):
    """Revoke one other active session owned by the authenticated user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND user_id = %s
                  AND session_token_hash <> %s
                  AND revoked_at IS NULL
                RETURNING id
                """,
                (session_id, user_id, current_session_token_hash),
            )
            return cursor.fetchone() is not None


def revoke_current_user_session(user_id, session_token_hash):
    """Revoke the active session associated with a normal logout."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND session_token_hash = %s
                  AND revoked_at IS NULL
                RETURNING id
                """,
                (user_id, session_token_hash),
            )
            return cursor.fetchone() is not None


def revoke_all_user_sessions(user_id):
    """Revoke every active session owned by one authenticated user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )
            return cursor.rowcount


def update_user_password_and_revoke_other_sessions(
    user_id, new_password, current_session_token_hash
):
    """Replace one user's password hash and revoke their other tracked sessions."""
    new_password_hash = generate_password_hash(new_password)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
                RETURNING id
                """,
                (new_password_hash, user_id),
            )
            if cursor.fetchone() is None:
                return False

            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND session_token_hash <> %s
                  AND revoked_at IS NULL
                """,
                (user_id, current_session_token_hash),
            )
            cursor.execute(
                """
                UPDATE remember_me_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )
    return True


def verify_user_password(user_id, password):
    """Verify a current password without returning the stored hash."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
    return bool(row and check_password_hash(row["password_hash"], password))


def save_pending_totp_secret(user_id, secret_encrypted):
    """Store an encrypted, not-yet-enabled TOTP secret for one user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_totp_credentials (user_id, secret_encrypted)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET secret_encrypted = EXCLUDED.secret_encrypted,
                    enabled_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING user_id
                """,
                (user_id, secret_encrypted),
            )
            return cursor.fetchone() is not None


def get_totp_credential(user_id):
    """Return the encrypted credential only for the owning authenticated user."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT secret_encrypted, enabled_at
                FROM user_totp_credentials
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return serialize_row(cursor.fetchone())


def get_totp_status(user_id):
    """Return display-safe TOTP state without exposing an encrypted secret."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT enabled_at IS NOT NULL AS is_enabled
                FROM user_totp_credentials
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    return {
        "is_enabled": bool(row and row["is_enabled"]),
        "setup_pending": bool(row and not row["is_enabled"]),
    }


def enable_totp_for_user(user_id):
    """Enable a verified credential and the existing preference flag together."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_preferences (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cursor.execute(
                """
                UPDATE user_totp_credentials
                SET enabled_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND enabled_at IS NULL
                RETURNING user_id
                """,
                (user_id,),
            )
            enabled = cursor.fetchone() is not None
            if enabled:
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET two_factor_enabled = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
            return enabled


def disable_totp_for_user(user_id):
    """Remove a user's credential and clear the existing preference flag."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_preferences (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM user_totp_credentials WHERE user_id = %s RETURNING user_id",
                (user_id,),
            )
            disabled = cursor.fetchone() is not None
            cursor.execute(
                """
                UPDATE user_preferences
                SET two_factor_enabled = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return disabled
