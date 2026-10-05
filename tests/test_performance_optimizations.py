from contextlib import contextmanager

import app as application
import db
import pytest


class FakeConnection:
    def __init__(self):
        self.closed = 0
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


def test_flask_request_reuses_one_database_connection(monkeypatch):
    connections = []

    def connect(**_kwargs):
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(db.psycopg2, "connect", connect)

    with application.app.test_request_context("/dashboard"):
        with db.get_connection() as first:
            pass
        with db.get_connection() as second:
            pass

        assert first is second
        assert len(connections) == 1
        assert connections[0].commits == 2
        assert connections[0].closed == 0
        db.close_request_connection()
        assert connections[0].closed == 1


def test_closed_database_connection_does_not_mask_original_error(monkeypatch):
    class ClosedConnection:
        closed = 1

        def commit(self):
            pass

        def rollback(self):
            raise db.psycopg2.InterfaceError("connection already closed")

        def close(self):
            pass

    monkeypatch.setattr(db.psycopg2, "connect", lambda **_kwargs: ClosedConnection())

    with application.app.test_request_context("/reports"):
        with pytest.raises(RuntimeError, match="original database failure"):
            with db.get_connection():
                raise RuntimeError("original database failure")


def test_transaction_creation_no_longer_runs_runtime_schema_ddl(monkeypatch):
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params=None):
            executed.append((" ".join(query.split()), params))

        def fetchone(self):
            return {"id": 21}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(db, "get_connection", connection)
    monkeypatch.setattr(
        db,
        "ensure_transactions_table",
        lambda: (_ for _ in ()).throw(AssertionError("runtime DDL called")),
    )

    result = db.create_transaction(
        7,
        {
            "amount": "25.00",
            "category": "Food & Dining",
            "date": "2026-10-05",
            "description": "Lunch",
            "payment_mode": "UPI",
        },
    )

    assert result == {"id": 21}
    assert len(executed) == 1
    assert executed[0][0].startswith("INSERT INTO transactions")


def test_recent_expenses_are_limited_in_sql(monkeypatch):
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params=None):
            executed.append((" ".join(query.split()), params))

        def fetchall(self):
            return []

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(db, "get_connection", connection)

    assert db.get_transactions(7, limit=5) == []
    assert "LIMIT %s" in executed[0][0]
    assert executed[0][1] == (7, 5)


def test_notification_duplicate_check_is_targeted_and_user_scoped(monkeypatch):
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params=None):
            executed.append((" ".join(query.split()), params))

        def fetchone(self):
            return {"exists": 1}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(db, "get_connection", connection)

    assert db.notification_exists(7, "alert", "Budget limit reached", "Message")
    query, params = executed[0]
    assert "WHERE user_id = %s" in query
    assert "AND type = %s" in query
    assert "AND title = %s" in query
    assert "AND message = %s" in query
    assert "LIMIT 1" in query
    assert params == (7, "alert", "Budget limit reached", "Message")


def test_performance_logging_is_opt_in_and_contains_safe_metadata(
    monkeypatch, caplog
):
    monkeypatch.setenv("PERFORMANCE_TIMING", "true")

    with caplog.at_level("INFO", logger=application.app.logger.name):
        response = application.app.test_client().get("/health")

    assert response.status_code == 200
    message = next(
        record.message for record in caplog.records if "performance route=" in record.message
    )
    assert "route=/health" in message
    assert "connections=0" in message
    assert "queries=0" in message
    assert "password" not in message.lower()
    assert "token" not in message.lower()
