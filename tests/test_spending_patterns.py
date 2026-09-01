from contextlib import contextmanager
from decimal import Decimal

import db


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = ""
        self.params = None

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_result = cursor

    def cursor(self):
        return self.cursor_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def run_monthly_summary(monkeypatch, rows, user_id=7):
    cursor = FakeCursor(rows)
    connection = FakeConnection(cursor)

    monkeypatch.setattr(db, "ensure_transactions_table", lambda: None)

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(db, "get_connection", fake_connection)
    return db.get_monthly_expense_summary(user_id), cursor


def test_monthly_expense_aggregation_groups_multiple_months(monkeypatch):
    result, cursor = run_monthly_summary(
        monkeypatch,
        [
            {"month": "2026-01", "amount": Decimal("125.50")},
            {"month": "2026-02", "amount": Decimal("300.25")},
        ],
    )

    assert result == [
        {"month": "2026-01", "amount": 125.5},
        {"month": "2026-02", "amount": 300.25},
    ]
    assert cursor.params == (7,)
    assert "TYPE = 'EXPENSE'" in cursor.query.upper()
    assert "SUM(AMOUNT)" in cursor.query.upper()
    assert "TO_CHAR(DATE_TRUNC('MONTH', DATE), 'YYYY-MM')" in cursor.query.upper()
    assert "GROUP BY DATE_TRUNC('MONTH', DATE)" in cursor.query.upper()
    assert "ORDER BY DATE_TRUNC('MONTH', DATE) ASC" in cursor.query.upper()


def test_monthly_expense_aggregation_handles_empty_data(monkeypatch):
    result, _ = run_monthly_summary(monkeypatch, [])

    assert result == []


def test_monthly_expense_aggregation_is_user_scoped(monkeypatch):
    _, cursor = run_monthly_summary(monkeypatch, [], user_id=42)

    assert "USER_ID = %S" in cursor.query.upper()
    assert cursor.params == (42,)
