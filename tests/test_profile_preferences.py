from pathlib import Path

import db


class FakeCursor:
    def __init__(self, rows=None, insert_row=None, update_row=None):
        self.rows = rows or {}
        self.insert_row = insert_row
        self.update_row = update_row
        self.executions = []
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=()):
        self.executions.append((query, params))
        normalized_query = " ".join(query.split()).upper()
        if normalized_query.startswith("SELECT"):
            self._result = self.rows.get(params[0])
        elif normalized_query.startswith("INSERT"):
            self._result = self.insert_row
        elif normalized_query.startswith("UPDATE"):
            self._result = self.update_row
        else:
            raise AssertionError(f"Unexpected SQL: {query}")

    def fetchone(self):
        result, self._result = self._result, None
        return result


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance


def preference_row(user_id=7, **overrides):
    row = {
        "user_id": user_id,
        "theme": "default",
        "currency": "USD",
        "language": "en",
        "budget_overspending_alerts": False,
        "weekly_savings_digest_enabled": False,
        "sip_due_date_reminders_enabled": False,
        "bill_due_date_reminders_enabled": False,
        "two_factor_enabled": False,
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


def patch_connection(monkeypatch, cursor):
    monkeypatch.setattr(db, "get_connection", lambda: FakeConnection(cursor))


def test_preference_record_can_be_created_for_a_user(monkeypatch):
    cursor = FakeCursor(insert_row=preference_row())
    patch_connection(monkeypatch, cursor)

    result = db.ensure_user_preferences(7)

    assert result["user_id"] == 7
    assert cursor.executions[0][1] == (7,)
    assert "INSERT INTO user_preferences" in cursor.executions[1][0]


def test_default_preference_values_are_correct(monkeypatch):
    cursor = FakeCursor(insert_row=preference_row())
    patch_connection(monkeypatch, cursor)

    result = db.ensure_user_preferences(7)

    assert result["theme"] == "default"
    assert result["currency"] == "USD"
    assert result["language"] == "en"
    assert not result["budget_overspending_alerts"]
    assert not result["weekly_savings_digest_enabled"]
    assert not result["sip_due_date_reminders_enabled"]
    assert not result["bill_due_date_reminders_enabled"]
    assert not result["two_factor_enabled"]


def test_existing_user_remains_valid_without_preference_row(monkeypatch):
    cursor = FakeCursor(rows={})
    patch_connection(monkeypatch, cursor)

    assert db.get_user_preferences(7) is None
    assert len(cursor.executions) == 1
    assert "FROM user_preferences" in cursor.executions[0][0]


def test_user_a_cannot_read_user_b_preferences(monkeypatch):
    cursor = FakeCursor(rows={8: preference_row(8, currency="EUR")})
    patch_connection(monkeypatch, cursor)

    result = db.get_user_preferences(7)

    assert result is None
    assert cursor.executions[0][1] == (7,)


def test_user_a_cannot_modify_user_b_preferences(monkeypatch):
    cursor = FakeCursor(update_row=None)
    patch_connection(monkeypatch, cursor)

    result = db.update_user_preferences(7, {"user_id": 8, "currency": "EUR"})

    assert result is None
    query, params = cursor.executions[0]
    assert "WHERE user_id = %s" in query
    assert params[-1] == 7
    assert 8 not in params


def test_client_user_id_cannot_override_authenticated_scope(monkeypatch):
    cursor = FakeCursor(update_row=preference_row(7, currency="EUR"))
    patch_connection(monkeypatch, cursor)

    result = db.update_user_preferences(
        7,
        {"user_id": 99, "currency": "EUR", "two_factor_enabled": True},
    )

    assert result["user_id"] == 7
    assert cursor.executions[0][1][-1] == 7
    assert 99 not in cursor.executions[0][1]


def test_preference_data_persists_through_update(monkeypatch):
    updated = preference_row(
        7,
        theme="dark",
        currency="EUR",
        weekly_savings_digest_enabled=True,
    )
    cursor = FakeCursor(update_row=updated)
    patch_connection(monkeypatch, cursor)

    result = db.update_user_preferences(
        7,
        {
            "theme": "DARK",
            "currency": "eur",
            "weekly_savings_digest_enabled": "on",
        },
    )

    assert result == updated
    assert cursor.executions[0][1] == ("dark", "EUR", True, 7)
    assert "updated_at = CURRENT_TIMESTAMP" in cursor.executions[0][0]


def test_empty_update_does_not_issue_unscoped_write(monkeypatch):
    cursor = FakeCursor(rows={7: preference_row()})
    patch_connection(monkeypatch, cursor)

    result = db.update_user_preferences(7, {"user_id": 99})

    assert result["user_id"] == 7
    assert len(cursor.executions) == 1
    assert cursor.executions[0][0].lstrip().upper().startswith("SELECT")


def test_migration_is_additive_and_idempotent():
    migration = Path("database/migrations/005_create_user_preferences.sql").read_text()
    upper_migration = migration.upper()

    assert "CREATE TABLE IF NOT EXISTS USER_PREFERENCES" in upper_migration
    assert "ON DELETE CASCADE" in upper_migration
    assert "DROP TABLE" not in upper_migration
    assert "DELETE FROM" not in upper_migration
    assert "ALTER TABLE USERS" not in upper_migration


def test_migration_contains_future_2fa_state_without_secret_storage():
    migration = Path("database/migrations/005_create_user_preferences.sql").read_text()
    upper_migration = migration.upper()

    assert "TWO_FACTOR_ENABLED BOOLEAN" in upper_migration
    assert "SECRET" not in upper_migration
    assert "DEVICE" not in upper_migration


def test_reference_data_migration_is_additive_and_seeds_currency_and_language_codes():
    migration = Path("database/migrations/008_create_preference_reference_data.sql").read_text()
    upper_migration = migration.upper()

    assert "CREATE TABLE IF NOT EXISTS PREFERENCE_CURRENCIES" in upper_migration
    assert "CREATE TABLE IF NOT EXISTS PREFERENCE_LANGUAGES" in upper_migration
    assert "ON CONFLICT (CODE) DO NOTHING" in upper_migration
    assert "'USD'" in migration
    assert "'INR'" in migration
    assert "'EUR'" in migration
    assert "'JPY'" in migration
    assert "'en'" in migration
    assert "DROP TABLE" not in upper_migration
    assert "DELETE FROM" not in upper_migration
