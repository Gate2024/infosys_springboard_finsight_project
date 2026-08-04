from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config


def _connection_kwargs():
    return {
        "host": Config.DB_HOST,
        "database": Config.DB_NAME,
        "user": Config.DB_USER,
        "password": Config.DB_PASSWORD,
        "port": Config.DB_PORT or 5432,
        "cursor_factory": RealDictCursor,
    }


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


def register_user(username, email, password):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username, email FROM users WHERE email = %s OR username = %s",
                (email, username),
            )
            existing_user = cursor.fetchone()
            if existing_user:
                if existing_user["email"] == email:
                    return False, "Email already exists."
                return False, "Username already exists."

            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email
                """,
                (username, email, generate_password_hash(password)),
            )
            return True, serialize_row(cursor.fetchone())


def login_user(email, password):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return False, None

    return True, serialize_row(user)


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
