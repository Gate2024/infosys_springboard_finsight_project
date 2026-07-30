"""
db.py - PostgreSQL Database Abstraction & Business Logic Layer
Supports Neon PostgreSQL Cloud Connection via DATABASE_URL URI string,
parameterized CRUD operations, fallback management, and metric calculations.
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "budget_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Global flag to track connection mode
USE_SQLITE_FALLBACK = False
SQLITE_DB_PATH = "budget_fallback.db"

def calculate_remaining(budget_amount, spent_amount):
    """Calculates remaining budget amount safely: remaining = budget_amount - spent_amount"""
    try:
        b_amt = float(budget_amount) if budget_amount is not None else 0.0
        s_amt = float(spent_amount) if spent_amount is not None else 0.0
        return round(b_amt - s_amt, 2)
    except (ValueError, TypeError):
        return 0.0

def get_db_connection():
    """
    Establishes and returns a database connection.
    Connects to Neon Cloud PostgreSQL via DATABASE_URL if provided, or host parameters.
    Falls back to SQLite if PostgreSQL fails.
    """
    global USE_SQLITE_FALLBACK
    
    if not USE_SQLITE_FALLBACK:
        try:
            if DATABASE_URL:
                conn = psycopg2.connect(
                    DATABASE_URL,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )
                return conn, "postgresql"
            else:
                conn = psycopg2.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    sslmode="require" if "neon.tech" in DB_HOST else "prefer",
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )
                return conn, "postgresql"
        except Exception as e:
            print(f"[DB Notice] PostgreSQL connection failed ({e}). Switching to local SQLite fallback.")
            USE_SQLITE_FALLBACK = True

    # SQLite Fallback Connection
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    """
    Initializes database schema. Reads schema.sql and creates PostgreSQL/SQLite tables.
    """
    conn, mode = get_db_connection()
    try:
        cur = conn.cursor()
        if mode == "postgresql":
            schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
            if os.path.exists(schema_file):
                with open(schema_file, "r") as f:
                    cur.execute(f.read())
                conn.commit()
                print("[DB Info] PostgreSQL (Neon Cloud) database schema initialized successfully!")
        else:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                INSERT OR IGNORE INTO users (id, username, email, password_hash)
                VALUES (1, 'alex_fintech', 'alex@luxurybudget.com', 'hashed_pass_placeholder');

                CREATE TABLE IF NOT EXISTS budgets (
                    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    budget_name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    budget_amount REAL NOT NULL CHECK(budget_amount >= 0),
                    spent_amount REAL NOT NULL DEFAULT 0.00 CHECK(spent_amount >= 0),
                    remaining_amount REAL NOT NULL DEFAULT 0.00,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Active',
                    priority TEXT NOT NULL DEFAULT 'Medium',
                    expected_income REAL DEFAULT 0.00,
                    expected_expenses REAL DEFAULT 0.00,
                    savings_goal REAL DEFAULT 0.00,
                    alert_percentage INTEGER DEFAULT 80,
                    color_label TEXT DEFAULT '#0E5A4E',
                    budget_icon TEXT DEFAULT 'fa-wallet',
                    is_recurring INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            conn.commit()
            print("[DB Info] SQLite fallback database initialized successfully.")
    except Exception as err:
        print(f"[DB Error] Schema initialization warning: {err}")
    finally:
        conn.close()

def dict_from_row(row):
    """Utility to convert a database row into a standard Python dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)

def create_budget(user_id, data):
    """Inserts a new budget record using parameterized queries with strict PostgreSQL boolean typing."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    
    budget_amt = float(data.get("budget_amount", 0.0))
    spent_amt = float(data.get("spent_amount", 0.0))
    rem_amt = calculate_remaining(budget_amt, spent_amt)

    # Convert is_recurring to Python bool for PostgreSQL compatibility
    is_recurring_val = True if data.get("is_recurring") in [True, "true", "1", 1, "on"] else False
    if mode == "sqlite":
        is_recurring_val = 1 if is_recurring_val else 0

    param_placeholder = "%s" if mode == "postgresql" else "?"

    query = f"""
        INSERT INTO budgets (
            user_id, budget_name, description, category, budget_amount,
            spent_amount, remaining_amount, currency, start_date, end_date,
            status, priority, expected_income, expected_expenses, savings_goal,
            alert_percentage, color_label, budget_icon, is_recurring, notes
        ) VALUES (
            {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
            {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
            {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder},
            {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder}, {param_placeholder}
        )
    """

    params = (
        int(user_id),
        data.get("budget_name"),
        data.get("description", ""),
        data.get("category"),
        budget_amt,
        spent_amt,
        rem_amt,
        data.get("currency", "USD"),
        data.get("start_date"),
        data.get("end_date"),
        data.get("status", "Active"),
        data.get("priority", "Medium"),
        float(data.get("expected_income", 0.0) or 0.0),
        float(data.get("expected_expenses", 0.0) or 0.0),
        float(data.get("savings_goal", 0.0) or 0.0),
        int(data.get("alert_percentage", 80) or 80),
        data.get("color_label", "#0E5A4E"),
        data.get("budget_icon", "fa-wallet"),
        is_recurring_val,
        data.get("notes", "")
    )

    try:
        cur.execute(query, params)
        conn.commit()
        if mode == "postgresql":
            cur.execute("SELECT LASTVAL() AS new_id;")
            res = cur.fetchone()
            new_id = res['new_id'] if isinstance(res, dict) else res[0]
        else:
            new_id = cur.lastrowid
        return new_id
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] Failed to create budget: {e}")
        raise e
    finally:
        conn.close()

def get_all_budgets(user_id):
    """Fetches all budgets for a user ordered by created_at DESC."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"
    
    query = f"SELECT * FROM budgets WHERE user_id = {param_placeholder} ORDER BY created_at DESC"
    cur.execute(query, (int(user_id),))
    rows = cur.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

def get_budget(budget_id, user_id):
    """Fetches a single budget record by budget_id and user_id."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"

    query = f"SELECT * FROM budgets WHERE budget_id = {param_placeholder} AND user_id = {param_placeholder}"
    cur.execute(query, (int(budget_id), int(user_id)))
    row = cur.fetchone()
    conn.close()
    return dict_from_row(row)

def update_budget(budget_id, user_id, data):
    """Updates an existing budget record in PostgreSQL."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"

    budget_amt = float(data.get("budget_amount", 0.0))
    spent_amt = float(data.get("spent_amount", 0.0))
    rem_amt = calculate_remaining(budget_amt, spent_amt)

    is_recurring_val = True if data.get("is_recurring") in [True, "true", "1", 1, "on"] else False
    if mode == "sqlite":
        is_recurring_val = 1 if is_recurring_val else 0

    query = f"""
        UPDATE budgets SET
            budget_name = {param_placeholder},
            description = {param_placeholder},
            category = {param_placeholder},
            budget_amount = {param_placeholder},
            spent_amount = {param_placeholder},
            remaining_amount = {param_placeholder},
            currency = {param_placeholder},
            start_date = {param_placeholder},
            end_date = {param_placeholder},
            status = {param_placeholder},
            priority = {param_placeholder},
            expected_income = {param_placeholder},
            expected_expenses = {param_placeholder},
            savings_goal = {param_placeholder},
            alert_percentage = {param_placeholder},
            color_label = {param_placeholder},
            budget_icon = {param_placeholder},
            is_recurring = {param_placeholder},
            notes = {param_placeholder},
            updated_at = CURRENT_TIMESTAMP
        WHERE budget_id = {param_placeholder} AND user_id = {param_placeholder}
    """

    params = (
        data.get("budget_name"),
        data.get("description", ""),
        data.get("category"),
        budget_amt,
        spent_amt,
        rem_amt,
        data.get("currency", "USD"),
        data.get("start_date"),
        data.get("end_date"),
        data.get("status", "Active"),
        data.get("priority", "Medium"),
        float(data.get("expected_income", 0.0) or 0.0),
        float(data.get("expected_expenses", 0.0) or 0.0),
        float(data.get("savings_goal", 0.0) or 0.0),
        int(data.get("alert_percentage", 80) or 80),
        data.get("color_label", "#0E5A4E"),
        data.get("budget_icon", "fa-wallet"),
        is_recurring_val,
        data.get("notes", ""),
        int(budget_id),
        int(user_id)
    )

    try:
        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] Failed to update budget {budget_id}: {e}")
        return False
    finally:
        conn.close()

def delete_budget(budget_id, user_id):
    """Deletes a budget permanently by budget_id."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"

    query = f"DELETE FROM budgets WHERE budget_id = {param_placeholder} AND user_id = {param_placeholder}"
    try:
        cur.execute(query, (int(budget_id), int(user_id)))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] Failed to delete budget {budget_id}: {e}")
        return False
    finally:
        conn.close()

def duplicate_budget(budget_id, user_id):
    """Duplicates an existing budget, appending '(Copy)' to its name."""
    original = get_budget(budget_id, user_id)
    if not original:
        return None

    new_data = dict(original)
    new_data['budget_name'] = f"{original['budget_name']} (Copy)"
    new_data.pop('budget_id', None)
    new_data.pop('created_at', None)
    new_data.pop('updated_at', None)

    return create_budget(user_id, new_data)

def archive_budget(budget_id, user_id):
    """Sets the status of a budget to 'Archived'."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"

    query = f"UPDATE budgets SET status = 'Archived', updated_at = CURRENT_TIMESTAMP WHERE budget_id = {param_placeholder} AND user_id = {param_placeholder}"
    try:
        cur.execute(query, (int(budget_id), int(user_id)))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] Failed to archive budget {budget_id}: {e}")
        return False
    finally:
        conn.close()

def get_summary_stats(user_id):
    """Calculates summary metrics for Dashboard cards."""
    budgets = get_all_budgets(user_id)
    total_budgets = len(budgets)
    active_budgets = sum(1 for b in budgets if b.get('status') == 'Active')
    completed_budgets = sum(1 for b in budgets if b.get('status') == 'Completed')
    
    total_allocated = sum(float(b.get('budget_amount', 0)) for b in budgets)
    total_remaining = sum(float(b.get('remaining_amount', 0)) for b in budgets)

    return {
        "total_budgets": total_budgets,
        "active_budgets": active_budgets,
        "completed_budgets": completed_budgets,
        "total_allocated": round(total_allocated, 2),
        "total_remaining": round(total_remaining, 2)
    }

def filter_budget(user_id, category=None, status=None, priority=None, search_term=None, sort_by=None):
    """Dynamic filtering and sorting of budgets on backend."""
    conn, mode = get_db_connection()
    cur = conn.cursor()
    param_placeholder = "%s" if mode == "postgresql" else "?"

    query = f"SELECT * FROM budgets WHERE user_id = {param_placeholder}"
    params = [int(user_id)]

    if category and category != 'All':
        query += f" AND category = {param_placeholder}"
        params.append(category)

    if status and status != 'All':
        query += f" AND status = {param_placeholder}"
        params.append(status)

    if priority and priority != 'All':
        query += f" AND priority = {param_placeholder}"
        params.append(priority)

    if search_term:
        term = f"%{search_term.strip()}%"
        query += f" AND (budget_name ILIKE {param_placeholder} OR description ILIKE {param_placeholder} OR category ILIKE {param_placeholder})" if mode == "postgresql" else f" AND (budget_name LIKE {param_placeholder} OR description LIKE {param_placeholder} OR category LIKE {param_placeholder})"
        params.extend([term, term, term])

    if sort_by == 'amount_asc':
        query += " ORDER BY budget_amount ASC"
    elif sort_by == 'amount_desc':
        query += " ORDER BY budget_amount DESC"
    elif sort_by == 'oldest':
        query += " ORDER BY created_at ASC"
    else:
        query += " ORDER BY created_at DESC"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]
