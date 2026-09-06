from contextlib import contextmanager
import hashlib
from unittest.mock import Mock

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import app as application
import db
from tests.auth_helpers import auth_form


class TrackedSessionDatabase:
    def __init__(self, active=True):
        self.active = active
        self.cursor_obj = Mock()
        self.cursor_obj.fetchone.return_value = (1,) if active else None

    @contextmanager
    def cursor_context(self):
        yield self.cursor_obj

    def cursor(self):
        return self.cursor_context()

    @contextmanager
    def connect(self):
        yield self


@pytest.fixture
def real_tracked_session(monkeypatch):
    """Exercise db.is_user_session_active without requiring test DB writes."""
    database = TrackedSessionDatabase()
    monkeypatch.setattr(db, "get_connection", database.connect)
    return database


@pytest.fixture
def auth_store(monkeypatch):
    user = {"id": 7, "username": "Auth Owner", "email": "owner@example.com"}
    calls = {
        "login": Mock(return_value=(True, user)),
        "register": Mock(return_value=(True, user)),
        "pending": Mock(return_value={"id": 1}),
        "pending_record": Mock(return_value={"id": 1, "email": "owner@example.com"}),
        "resend_status": Mock(return_value={"resend_count": 0, "can_resend": False, "remaining_seconds": 60}),
        "email": Mock(),
        "create": Mock(return_value={"id": 1}),
        "revoke": Mock(return_value=True),
    }
    monkeypatch.setattr(application, "login_user", calls["login"])
    monkeypatch.setattr(application, "register_user", calls["register"])
    monkeypatch.setattr(application, "create_pending_registration", calls["pending"])
    monkeypatch.setattr(application, "get_pending_registration", calls["pending_record"])
    monkeypatch.setattr(application, "get_registration_resend_status", calls["resend_status"])
    monkeypatch.setattr(application.email_service, "send_registration_otp", calls["email"])
    monkeypatch.setattr(application, "create_user_session", calls["create"])
    monkeypatch.setattr(application, "revoke_current_user_session", calls["revoke"])
    monkeypatch.setattr(application, "get_totp_status", lambda uid: {"is_enabled": False})
    monkeypatch.setattr(application, "get_user_by_id", lambda uid: user)
    monkeypatch.setattr(application, "get_user_preferences", lambda uid: None)
    monkeypatch.setattr(application, "get_notifications", lambda *args: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda uid: 0)
    application._login_failures.clear()
    yield calls
    application._login_failures.clear()


def tracked_client():
    client = application.app.test_client()
    with client.session_transaction() as session:
        session.update(uid=7, username="Auth Owner", auth_session_token="fixture-session-7")
    return client


@pytest.mark.parametrize("route", ["/dashboard", "/profile", "/profile/preferences", "/profile/security"])
@pytest.mark.parametrize("user_id, token", [
    (7, None), (7, ""), (7, 42), (7, "unknown-token"),
    (7, "fixture-session-99"), (None, "fixture-session-7"),
    ("7", "fixture-session-7"), (True, "fixture-session-True"),
    (0, "fixture-session-0"), (-1, "fixture-session--1"),
])
def test_protected_routes_reject_invalid_sessions(route, user_id, token):
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = user_id
        if token is not None:
            session["auth_session_token"] = token
    response = client.get(route)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as session:
        assert "uid" not in session
        assert "auth_session_token" not in session


def test_valid_tracked_session_reaches_profile(auth_store, real_tracked_session, monkeypatch):
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    assert tracked_client().get("/profile").status_code == 200


def test_revoked_session_rejected(auth_store, real_tracked_session, monkeypatch):
    real_tracked_session.cursor_obj.fetchone.return_value = None
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    response = tracked_client().get("/profile")
    assert response.status_code == 302
    assert real_tracked_session.cursor_obj.execute.call_args.args[1] == (
        application.app.config["SESSION_INACTIVITY_TIMEOUT_SECONDS"],
        application.app.config["SESSION_ABSOLUTE_TIMEOUT_SECONDS"],
        7,
        hashlib.sha256(b"fixture-session-7").hexdigest(),
    )


@pytest.mark.parametrize("route", ["/login", "/register"])
@pytest.mark.parametrize("token", [None, "invalid"])
def test_auth_forms_reject_missing_or_invalid_csrf(auth_store, route, token):
    client = application.app.test_client()
    data = auth_form(client, username="Owner", email="owner@example.com", password="password")
    if token is None:
        data.pop("_auth_csrf_token")
    else:
        data["_auth_csrf_token"] = token
    assert client.post(route, data=data).status_code == 400
    auth_store["login"].assert_not_called()
    auth_store["register"].assert_not_called()
    auth_store["create"].assert_not_called()


def test_csrf_from_another_browser_is_rejected(auth_store):
    first = application.app.test_client()
    second = application.app.test_client()
    data = auth_form(first, email="owner@example.com", password="password")
    second.get("/login")
    assert second.post("/login", data=data).status_code == 400
    auth_store["login"].assert_not_called()


def test_login_rotates_session_and_returns_no_hash(auth_store):
    client = application.app.test_client()
    data = auth_form(client, email="owner@example.com", password="password")
    with client.session_transaction() as session:
        session["stale"] = "old-session-value"
    response = client.post("/login", data=data)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    with client.session_transaction() as session:
        assert session["uid"] == 7
        assert session["auth_session_token"]
        assert "stale" not in session
        assert "auth_csrf_token" not in session
        assert "password_hash" not in session
        assert auth_store["create"].call_args.args[1] == hashlib.sha256(
            session["auth_session_token"].encode()
        ).hexdigest()


def test_invalid_credentials_keep_generic_error(auth_store):
    auth_store["login"].return_value = (False, None)
    client = application.app.test_client()
    response = client.post("/login", data=auth_form(client, email="absent@example.com", password="wrong"))
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data
    auth_store["create"].assert_not_called()


@pytest.mark.parametrize("password", ["123456", "1234567", "12345678"])
def test_registration_eight_character_boundary(auth_store, password):
    client = application.app.test_client()
    response = client.post("/register", data=auth_form(
        client, username="Owner", email="OWNER@example.com", mobile_number="9876543210",
        password=password, confirm_password=password
    ))
    if len(password) < 8:
        assert response.status_code == 200
        assert b"Password must contain at least 8 characters." in response.data
        auth_store["register"].assert_not_called()
    else:
        assert response.status_code == 200
        assert b"verification code" in response.data
        auth_store["pending"].assert_called_once()
        auth_store["register"].assert_not_called()
        auth_store["email"].assert_called_once()


@pytest.mark.parametrize("token", [None, "invalid"])
def test_logout_rejects_missing_or_invalid_csrf(auth_store, token, real_tracked_session, monkeypatch):
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    client = tracked_client()
    assert client.get("/profile").status_code == 200
    data = {} if token is None else {"_auth_csrf_token": token}
    assert client.post("/logout", data=data).status_code == 400
    auth_store["revoke"].assert_not_called()
    with client.session_transaction() as session:
        assert session["uid"] == 7


def test_logout_requires_post_and_revokes_current_session(auth_store, real_tracked_session, monkeypatch):
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    client = tracked_client()
    response = client.get("/profile")
    assert b'action="/logout" method="post"' in response.data
    assert b'href="/logout"' not in response.data
    assert client.get("/logout").status_code == 405
    auth_store["revoke"].assert_not_called()
    with client.session_transaction() as session:
        token = session["auth_csrf_token"]
    response = client.post("/logout", data={"_auth_csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    auth_store["revoke"].assert_called_once_with(7, hashlib.sha256(b"fixture-session-7").hexdigest())
    with client.session_transaction() as session:
        assert not session


@pytest.mark.parametrize("password, found", [("correct-password", True), ("wrong", True), ("correct-password", False)])
def test_database_login_verifies_hash_but_only_returns_public_fields(monkeypatch, password, found):
    row = {"id": 7, "username": "Owner", "email": "owner@example.com",
           "password_hash": generate_password_hash("correct-password")}
    cursor = Mock()
    cursor.fetchone.return_value = row if found else None

    @contextmanager
    def cursor_context():
        yield cursor

    connection = Mock()
    connection.cursor = cursor_context

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(db, "get_connection", connect)
    success, user = db.login_user("owner@example.com", password)
    assert check_password_hash(row["password_hash"], "correct-password")
    assert cursor.execute.call_args.args[1] == ("owner@example.com",)
    assert "SELECT *" not in cursor.execute.call_args.args[0]
    if found and password == "correct-password":
        assert success
        assert user == {key: row[key] for key in ("id", "username", "email")}
    else:
        assert (success, user) == (False, None)
