from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
import hashlib

import pytest

import app as application
import db
from tests.auth_helpers import auth_form


class RememberStore:
    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc)
        self.remember_rows = []
        self.session_rows = []
        self.cursor_obj = None

    @contextmanager
    def connect(self):
        self.cursor_obj = RememberCursor(self)
        yield self

    @contextmanager
    def cursor(self):
        yield self.cursor_obj

    def add_remember(self, user_id, raw_token, expires_at=None, revoked_at=None):
        row = {
            "id": len(self.remember_rows) + 1,
            "user_id": user_id,
            "token_hash": hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            "created_at": self.now,
            "expires_at": expires_at or self.now + timedelta(days=30),
            "last_used_at": None,
            "device_info": "Test browser",
            "ip_address": "127.0.0.1",
            "revoked_at": revoked_at,
        }
        self.remember_rows.append(row)
        return row


class RememberCursor:
    def __init__(self, store):
        self.store = store
        self.result = None
        self.rowcount = 0

    def execute(self, query, params):
        normalized = " ".join(query.lower().split())
        self.result = None
        self.rowcount = 0

        if "with session_row as" in normalized:
            self._validate_session(params)
        elif "from revoked" in normalized:
            self._rotate_remember_token(params)
        elif normalized.startswith("insert into remember_me_tokens"):
            self._create_remember_token(params)
        elif normalized.startswith("update remember_me_tokens"):
            self._revoke_remember_tokens(normalized, params)
        elif normalized.startswith("insert into user_sessions"):
            self._create_session(params)
        elif normalized.startswith("update users"):
            self.result = {"id": params[1]}
        elif normalized.startswith("update user_sessions"):
            self.rowcount = 1

    def fetchone(self):
        return self.result

    def _create_remember_token(self, params):
        user_id, token_hash, lifetime, device_info, ip_address = params
        row = {
            "id": len(self.store.remember_rows) + 1,
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": self.store.now,
            "expires_at": self.store.now + timedelta(seconds=lifetime),
            "last_used_at": None,
            "device_info": device_info,
            "ip_address": ip_address,
            "revoked_at": None,
        }
        self.store.remember_rows.append(row)
        self.result = row

    def _rotate_remember_token(self, params):
        old_hash, new_hash, lifetime, device_info, ip_address = params
        row = next(
            (
                item
                for item in self.store.remember_rows
                if item["token_hash"] == old_hash
                and item["revoked_at"] is None
                and item["expires_at"] > self.store.now
            ),
            None,
        )
        if not row:
            return
        row["revoked_at"] = self.store.now
        row["last_used_at"] = self.store.now
        self.store.remember_rows.append(
            {
                "id": len(self.store.remember_rows) + 1,
                "user_id": row["user_id"],
                "token_hash": new_hash,
                "created_at": self.store.now,
                "expires_at": self.store.now + timedelta(seconds=lifetime),
                "last_used_at": None,
                "device_info": device_info,
                "ip_address": ip_address,
                "revoked_at": None,
            }
        )
        self.result = {"user_id": row["user_id"]}

    def _revoke_remember_tokens(self, normalized, params):
        if "token_hash = %s" in normalized:
            user_id, token_hash = params
            rows = [
                row
                for row in self.store.remember_rows
                if row["user_id"] == user_id
                and row["token_hash"] == token_hash
                and row["revoked_at"] is None
            ]
        else:
            user_id = params[0]
            rows = [
                row
                for row in self.store.remember_rows
                if row["user_id"] == user_id and row["revoked_at"] is None
            ]
        for row in rows:
            row["revoked_at"] = self.store.now
        self.rowcount = len(rows)
        self.result = (rows[0]["id"],) if rows and "returning id" in normalized else None

    def _create_session(self, params):
        user_id, token_hash, device_info, ip_address = params
        row = {
            "id": len(self.store.session_rows) + 1,
            "user_id": user_id,
            "session_token_hash": token_hash,
            "device_info": device_info,
            "ip_address": ip_address,
            "created_at": self.store.now,
            "last_active_at": self.store.now,
            "revoked_at": None,
        }
        self.store.session_rows.append(row)
        self.result = row

    def _validate_session(self, params):
        inactivity_timeout, absolute_timeout, user_id, token_hash = params
        row = next(
            (
                item
                for item in self.store.session_rows
                if item["user_id"] == user_id
                and item["session_token_hash"] == token_hash
                and item["revoked_at"] is None
            ),
            None,
        )
        if not row:
            return
        if (
            self.store.now - row["last_active_at"] >= timedelta(seconds=inactivity_timeout)
            or self.store.now - row["created_at"] >= timedelta(seconds=absolute_timeout)
        ):
            row["revoked_at"] = self.store.now
            return
        row["last_active_at"] = self.store.now
        self.result = (row["id"],)


def patch_remember_environment(monkeypatch, store, totp_enabled=False):
    monkeypatch.setattr(db, "get_connection", store.connect)
    monkeypatch.setattr(application, "is_user_session_active", db.is_user_session_active)
    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, {"id": 7, "username": "Remembered User", "email": email}),
    )
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: {"id": user_id, "username": "Remembered User", "email": "owner@example.com"},
    )
    monkeypatch.setattr(application, "get_totp_status", lambda user_id: {"is_enabled": totp_enabled})
    monkeypatch.setattr(application, "get_user_preferences", lambda user_id: {})
    monkeypatch.setattr(application, "get_notifications", lambda *args: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda user_id: 0)
    monkeypatch.setitem(application.app.config, "REMEMBER_ME_TIMEOUT_SECONDS", 30 * 24 * 60 * 60)
    monkeypatch.setitem(application.app.config, "SESSION_INACTIVITY_TIMEOUT_SECONDS", 1800)
    monkeypatch.setitem(application.app.config, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 86400)


def login_client(client, remember=False):
    data = auth_form(client, email="owner@example.com", password="password")
    if remember:
        data["remember_me"] = "1"
    return client.post("/login", data=data)


def remember_cookie_value(response):
    for header in response.headers.getlist("Set-Cookie"):
        parsed = SimpleCookie()
        parsed.load(header)
        if application.REMEMBER_ME_COOKIE_NAME in parsed:
            return parsed[application.REMEMBER_ME_COOKIE_NAME].value
    return None


def test_login_without_remember_me_creates_no_persistent_credential(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)

    response = login_client(application.app.test_client())

    assert response.status_code == 302
    assert store.remember_rows == []
    assert remember_cookie_value(response) is None


def test_login_with_remember_me_stores_only_a_random_hash_and_sets_explicit_cookie(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    client = application.app.test_client()

    response = login_client(client, remember=True)
    raw_token = remember_cookie_value(response)

    assert response.status_code == 302
    assert raw_token
    assert len(store.remember_rows) == 1
    row = store.remember_rows[0]
    assert row["user_id"] == 7
    assert row["token_hash"] == hashlib.sha256(raw_token.encode()).hexdigest()
    assert raw_token != row["token_hash"]
    remember_header = next(
        header for header in response.headers.getlist("Set-Cookie")
        if header.startswith(f"{application.REMEMBER_ME_COOKIE_NAME}=")
    )
    assert "HttpOnly" in remember_header
    assert "Max-Age=2592000" in remember_header
    assert "Expires=" in remember_header
    with client.session_transaction() as session:
        assert all(raw_token not in str(value) for value in session.values())


def test_remember_me_login_replaces_invalid_existing_cookie(monkeypatch):
    now = datetime.now(timezone.utc)
    store = RememberStore(now)
    store.add_remember(7, "expired-login-token", expires_at=now - timedelta(seconds=1))
    patch_remember_environment(monkeypatch, store)
    client = application.app.test_client()
    client.set_cookie(application.REMEMBER_ME_COOKIE_NAME, "expired-login-token")

    response = login_client(client, remember=True)

    assert response.status_code == 302
    new_raw_token = remember_cookie_value(response)
    assert new_raw_token and new_raw_token != "expired-login-token"
    assert any(
        row["token_hash"] == hashlib.sha256(new_raw_token.encode()).hexdigest()
        and row["revoked_at"] is None
        for row in store.remember_rows
    )


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_invalid_remember_me_timeout_configuration_fails_safely(monkeypatch, value):
    monkeypatch.setenv("REMEMBER_ME_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError):
        application._session_timeout_setting(
            "REMEMBER_ME_TIMEOUT_SECONDS", application.DEFAULT_REMEMBER_ME_TIMEOUT_SECONDS
        )


def test_configured_remember_me_timeout_is_used(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    monkeypatch.setitem(application.app.config, "REMEMBER_ME_TIMEOUT_SECONDS", 172800)

    response = login_client(application.app.test_client(), remember=True)
    raw_token = remember_cookie_value(response)

    remember_header = next(
        header for header in response.headers.getlist("Set-Cookie")
        if header.startswith(f"{application.REMEMBER_ME_COOKIE_NAME}=")
    )
    assert "Max-Age=172800" in remember_header
    assert store.remember_rows[0]["expires_at"] == store.now + timedelta(seconds=172800)
    assert raw_token


def test_remember_me_tokens_are_random_and_distinct(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)

    first = login_client(application.app.test_client(), remember=True)
    second = login_client(application.app.test_client(), remember=True)

    assert remember_cookie_value(first) != remember_cookie_value(second)
    assert store.remember_rows[0]["token_hash"] != store.remember_rows[1]["token_hash"]


def test_remember_me_cookie_is_secure_in_production(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    monkeypatch.setitem(application.app.config, "SESSION_COOKIE_SECURE", True)

    response = login_client(application.app.test_client(), remember=True)

    remember_header = next(
        header for header in response.headers.getlist("Set-Cookie")
        if header.startswith(f"{application.REMEMBER_ME_COOKIE_NAME}=")
    )
    assert "Secure" in remember_header


def test_valid_remember_me_cookie_restores_a_new_tracked_session_and_rotates_token(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    client = application.app.test_client()
    login_response = login_client(client, remember=True)
    old_raw_token = remember_cookie_value(login_response)

    with client.session_transaction() as session:
        session.clear()
    response = client.get("/profile")

    assert response.status_code == 200
    assert len(store.session_rows) == 2
    assert store.remember_rows[0]["revoked_at"] is not None
    new_raw_token = remember_cookie_value(response)
    assert new_raw_token and new_raw_token != old_raw_token
    assert store.remember_rows[-1]["token_hash"] == hashlib.sha256(new_raw_token.encode()).hexdigest()
    with client.session_transaction() as session:
        assert session["uid"] == 7
        assert session.permanent is False


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_invalid_expired_or_revoked_remember_me_cookie_does_not_authenticate_and_is_cleared(
    monkeypatch, state
):
    now = datetime.now(timezone.utc)
    store = RememberStore(now)
    raw_token = "invalid-state-token"
    row = store.add_remember(
        7,
        raw_token,
        expires_at=now - timedelta(seconds=1) if state == "expired" else now + timedelta(days=1),
        revoked_at=now if state == "revoked" else None,
    )
    patch_remember_environment(monkeypatch, store)
    client = application.app.test_client()
    client.set_cookie(application.REMEMBER_ME_COOKIE_NAME, raw_token)

    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert remember_cookie_value(response) == ""
    assert any(
        header.startswith(f"{application.REMEMBER_ME_COOKIE_NAME}=") and "Max-Age=0" in header
        for header in response.headers.getlist("Set-Cookie")
    )
    assert row["revoked_at"] is None if state == "expired" else row["revoked_at"] == now
    with client.session_transaction() as session:
        assert "uid" not in session


def test_token_cannot_be_revoked_or_bound_as_another_users_credential(monkeypatch):
    store = RememberStore()
    row = store.add_remember(99, "owner-99-token")
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert not db.revoke_remember_me_token(7, row["token_hash"])
    assert row["revoked_at"] is None
    assert db.rotate_remember_me_token(
        row["token_hash"], "replacement-hash", 3600, "Test browser", "127.0.0.1"
    ) == 99
    assert store.remember_rows[-1]["user_id"] == 99


def test_old_rotated_token_cannot_be_reused(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    first_client = application.app.test_client()
    login_response = login_client(first_client, remember=True)
    old_raw_token = remember_cookie_value(login_response)
    with first_client.session_transaction() as session:
        session.clear()
    assert first_client.get("/profile").status_code == 200

    second_client = application.app.test_client()
    second_client.set_cookie(application.REMEMBER_ME_COOKIE_NAME, old_raw_token)
    response = second_client.get("/profile")

    assert response.status_code == 302
    with second_client.session_transaction() as session:
        assert "uid" not in session


def test_same_persistent_token_can_only_be_rotated_once(monkeypatch):
    store = RememberStore()
    row = store.add_remember(7, "one-time-token")
    monkeypatch.setattr(db, "get_connection", store.connect)

    first = db.rotate_remember_me_token(
        row["token_hash"], "replacement-one", 3600, "Browser 1", "127.0.0.1"
    )
    second = db.rotate_remember_me_token(
        row["token_hash"], "replacement-two", 3600, "Browser 2", "127.0.0.1"
    )

    assert first == 7
    assert second is None
    assert sum(row["revoked_at"] is None for row in store.remember_rows) == 1


def test_remember_me_logout_revokes_credential_and_clears_cookie(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    client = application.app.test_client()
    login_response = login_client(client, remember=True)
    raw_token = remember_cookie_value(login_response)
    with client.session_transaction() as session:
        session["auth_csrf_token"] = "logout-csrf"

    response = client.post("/logout", data={"_auth_csrf_token": "logout-csrf"})

    assert response.status_code == 302
    assert store.remember_rows[0]["revoked_at"] is not None
    assert raw_token not in (remember_cookie_value(response) or "")
    assert any(
        header.startswith(f"{application.REMEMBER_ME_COOKIE_NAME}=") and "Max-Age=0" in header
        for header in response.headers.getlist("Set-Cookie")
    )


def test_logout_all_revokes_all_persistent_credentials(monkeypatch):
    store = RememberStore()
    patch_remember_environment(monkeypatch, store)
    store.add_remember(7, "first-device")
    store.add_remember(7, "second-device")
    token = "tracked-token"
    store.session_rows.append(
        {
            "id": 1,
            "user_id": 7,
            "session_token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "created_at": store.now,
            "last_active_at": store.now,
            "revoked_at": None,
        }
    )
    monkeypatch.setattr(application, "security_page_data", lambda user_id: ([], {"is_enabled": False}))
    client = application.app.test_client()
    with client.session_transaction() as session:
        session.update(
            uid=7,
            username="Remembered User",
            email="owner@example.com",
            auth_session_token=token,
            security_sessions_csrf_token="security-csrf",
        )

    response = client.post(
        "/profile/security/sessions/logout-all",
        data={"_security_sessions_csrf_token": "security-csrf"},
    )

    assert response.status_code == 302
    assert all(row["revoked_at"] is not None for row in store.remember_rows)


def test_password_change_revokes_persistent_credentials_in_same_database_transaction(monkeypatch):
    store = RememberStore()
    store.add_remember(7, "password-change-token")
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert db.update_user_password_and_revoke_other_sessions(7, "new-password", "current-hash")
    assert store.remember_rows[0]["revoked_at"] is not None


def test_remember_me_does_not_bypass_totp(monkeypatch):
    store = RememberStore()
    raw_token = "totp-remember-token"
    store.add_remember(7, raw_token)
    patch_remember_environment(monkeypatch, store, totp_enabled=True)
    client = application.app.test_client()
    client.set_cookie(application.REMEMBER_ME_COOKIE_NAME, raw_token)

    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login/2fa")
    assert store.session_rows == []
    with client.session_transaction() as session:
        assert session["pending_2fa_user_id"] == 7
        assert "uid" not in session
