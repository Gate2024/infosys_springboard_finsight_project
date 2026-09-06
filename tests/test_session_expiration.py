from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

import app as application
import db
from tests.auth_helpers import auth_form


class SessionCursor:
    def __init__(self, store):
        self.store = store
        self.result = None
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params
        inactivity_timeout, absolute_timeout, user_id, token_hash = params
        session_row = next(
            (
                row
                for row in self.store.rows
                if row["user_id"] == user_id
                and row["session_token_hash"] == token_hash
                and row["revoked_at"] is None
            ),
            None,
        )
        if not session_row:
            self.result = None
            return

        inactivity_expired = self.store.now - session_row["last_active_at"] >= timedelta(
            seconds=inactivity_timeout
        )
        absolute_expired = self.store.now - session_row["created_at"] >= timedelta(
            seconds=absolute_timeout
        )
        if inactivity_expired or absolute_expired:
            session_row["revoked_at"] = self.store.now
            self.result = None
            return

        session_row["last_active_at"] = self.store.now
        self.result = (session_row["id"],)

    def fetchone(self):
        return self.result


class SessionStore:
    def __init__(self, rows, now):
        self.rows = rows
        self.now = now
        self.cursor_obj = None

    @contextmanager
    def connect(self):
        self.cursor_obj = SessionCursor(self)
        yield self

    @contextmanager
    def cursor(self):
        yield self.cursor_obj


def session_row(session_id, user_id, token, now, **overrides):
    row = {
        "id": session_id,
        "user_id": user_id,
        "session_token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "created_at": now,
        "last_active_at": now,
        "revoked_at": None,
    }
    row.update(overrides)
    return row


def authenticated_client(token="current-session-token"):
    client = application.app.test_client()
    with client.session_transaction() as session:
        session.update(
            uid=7,
            username="Session Owner",
            email="owner@example.com",
            auth_session_token=token,
        )
    return client


def configure_profile_route(monkeypatch):
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: {"id": user_id, "username": "Session Owner", "email": "owner@example.com"},
    )
    monkeypatch.setattr(application, "get_user_preferences", lambda user_id: {})
    monkeypatch.setattr(application, "get_notifications", lambda *args: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda user_id: 0)


def test_timeout_defaults_are_positive_and_environment_values_are_used(monkeypatch):
    assert application.app.config["SESSION_INACTIVITY_TIMEOUT_SECONDS"] > 0
    assert application.app.config["SESSION_ABSOLUTE_TIMEOUT_SECONDS"] > 0

    monkeypatch.setenv("SESSION_INACTIVITY_TIMEOUT_SECONDS", "120")
    assert application._session_timeout_setting("SESSION_INACTIVITY_TIMEOUT_SECONDS", 30) == 120


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_invalid_timeout_configuration_is_rejected(monkeypatch, value):
    monkeypatch.setenv("SESSION_INACTIVITY_TIMEOUT_SECONDS", value)
    with pytest.raises(RuntimeError, match="positive integer"):
        application._session_timeout_setting("SESSION_INACTIVITY_TIMEOUT_SECONDS", 30)


def test_fresh_session_is_valid_and_activity_updates_last_active_at(monkeypatch):
    now = datetime.now(timezone.utc)
    store = SessionStore([session_row(1, 7, "current", now)], now)
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert db.is_user_session_active(7, store.rows[0]["session_token_hash"], 60, 3600)
    assert store.rows[0]["last_active_at"] == now
    assert "FOR UPDATE" in store.cursor_obj.query
    assert "revoked_at IS NULL" in store.cursor_obj.query


def test_active_session_does_not_expire_when_activity_continues(monkeypatch):
    created = datetime.now(timezone.utc) - timedelta(minutes=5)
    first_now = created + timedelta(seconds=30)
    second_now = first_now + timedelta(seconds=30)
    store = SessionStore([session_row(1, 7, "current", first_now, created_at=created)], first_now)
    monkeypatch.setattr(db, "get_connection", store.connect)
    token_hash = store.rows[0]["session_token_hash"]

    assert db.is_user_session_active(7, token_hash, 60, 3600)
    store.now = second_now
    assert db.is_user_session_active(7, token_hash, 60, 3600)
    assert store.rows[0]["revoked_at"] is None
    assert store.rows[0]["last_active_at"] == second_now


def test_inactivity_expiration_revokes_current_session(monkeypatch):
    now = datetime.now(timezone.utc)
    store = SessionStore(
        [session_row(1, 7, "current", now, last_active_at=now - timedelta(seconds=61))],
        now,
    )
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.is_user_session_active(7, store.rows[0]["session_token_hash"], 60, 3600)
    assert store.rows[0]["revoked_at"] == now


def test_expired_inactivity_session_redirects_to_login(monkeypatch):
    now = datetime.now(timezone.utc)
    token = "expired-session"
    row = session_row(1, 7, token, now, last_active_at=now - timedelta(seconds=61))
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)
    configure_profile_route(monkeypatch)
    monkeypatch.setitem(application.app.config, "SESSION_INACTIVITY_TIMEOUT_SECONDS", 60)
    monkeypatch.setitem(application.app.config, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 3600)

    client = authenticated_client(token)
    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert row["revoked_at"] == now
    with client.session_transaction() as session:
        assert "uid" not in session
        assert "auth_session_token" not in session


def test_absolute_expiration_wins_even_when_session_is_active(monkeypatch):
    now = datetime.now(timezone.utc)
    token = "absolute-expired-session"
    row = session_row(
        1,
        7,
        token,
        now,
        created_at=now - timedelta(seconds=101),
        last_active_at=now - timedelta(seconds=1),
    )
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.is_user_session_active(7, row["session_token_hash"], 60, 100)
    assert row["revoked_at"] == now


def test_absolute_expiration_redirects_to_login(monkeypatch):
    now = datetime.now(timezone.utc)
    token = "absolute-expired-route-session"
    row = session_row(
        1,
        7,
        token,
        now,
        created_at=now - timedelta(seconds=101),
        last_active_at=now - timedelta(seconds=1),
    )
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)
    configure_profile_route(monkeypatch)
    monkeypatch.setitem(application.app.config, "SESSION_INACTIVITY_TIMEOUT_SECONDS", 60)
    monkeypatch.setitem(application.app.config, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 100)

    client = authenticated_client(token)
    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert row["revoked_at"] == now


def test_absolute_expiration_is_not_reset_by_activity(monkeypatch):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=95)
    row = session_row(1, 7, "absolute-session", now, created_at=created, last_active_at=now)
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)
    token_hash = row["session_token_hash"]

    assert db.is_user_session_active(7, token_hash, 60, 120)
    store.now = now + timedelta(seconds=40)
    assert not db.is_user_session_active(7, token_hash, 60, 120)
    assert row["revoked_at"] == store.now


def test_expiring_one_session_does_not_revoke_another(monkeypatch):
    now = datetime.now(timezone.utc)
    expired = session_row(1, 7, "expired", now, last_active_at=now - timedelta(seconds=61))
    valid = session_row(2, 7, "valid", now)
    store = SessionStore([expired, valid], now)
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.is_user_session_active(7, expired["session_token_hash"], 60, 3600)
    assert db.is_user_session_active(7, valid["session_token_hash"], 60, 3600)
    assert expired["revoked_at"] == now
    assert valid["revoked_at"] is None


@pytest.mark.parametrize(
    "user_id, token_hash",
    [
        (7, hashlib.sha256(b"missing-token").hexdigest()),
        (8, hashlib.sha256(b"current").hexdigest()),
    ],
)
def test_invalid_or_other_user_session_is_rejected(monkeypatch, user_id, token_hash):
    now = datetime.now(timezone.utc)
    row = session_row(1, 7, "current", now)
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.is_user_session_active(user_id, token_hash, 60, 3600)
    assert row["revoked_at"] is None


def test_revoked_session_remains_invalid(monkeypatch):
    now = datetime.now(timezone.utc)
    row = session_row(1, 7, "revoked", now, revoked_at=now - timedelta(seconds=1))
    store = SessionStore([row], now)
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.is_user_session_active(7, row["session_token_hash"], 60, 3600)


def test_login_without_totp_creates_a_valid_tracked_session(monkeypatch):
    now = datetime.now(timezone.utc)
    store = SessionStore([], now)
    monkeypatch.setattr(db, "get_connection", store.connect)
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, {"id": 7, "username": "Session Owner", "email": email}),
    )
    monkeypatch.setattr(application, "get_totp_status", lambda user_id: {"is_enabled": False})
    monkeypatch.setattr(application, "get_user_preferences", lambda user_id: {})
    monkeypatch.setattr(
        application,
        "create_user_session",
        lambda user_id, token_hash, device, ip: store.rows.append(
            session_row(1, user_id, "unused", now, session_token_hash=token_hash)
        ),
    )
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: {"id": user_id, "username": "Session Owner", "email": "owner@example.com"},
    )
    monkeypatch.setattr(application, "get_notifications", lambda *args: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda user_id: 0)
    monkeypatch.setitem(application.app.config, "SESSION_INACTIVITY_TIMEOUT_SECONDS", 60)
    monkeypatch.setitem(application.app.config, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 3600)

    client = application.app.test_client()
    response = client.post(
        "/login",
        data=auth_form(client, email="owner@example.com", password="password"),
    )

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert db.is_user_session_active(
            session["uid"],
            hashlib.sha256(session["auth_session_token"].encode()).hexdigest(),
            60,
            3600,
        )


def test_pending_totp_state_is_not_accepted_by_protected_routes():
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["pending_2fa_user_id"] = 7

    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
