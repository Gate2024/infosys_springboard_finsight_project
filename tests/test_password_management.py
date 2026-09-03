from contextlib import contextmanager
import hashlib

import pyotp
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import app as application
import db as database


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def set_authenticated_session(client, user_id=7, token="current-device-token"):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Password Owner"
        session["email"] = f"user{user_id}@example.com"
        session["auth_session_token"] = token


def session_row(session_id, user_id, token, **overrides):
    row = {
        "id": session_id,
        "user_id": user_id,
        "session_token_hash": token_hash(token),
        "device_info": "Browser",
        "ip_address": "127.0.0.1",
        "created_at": "2026-09-03 10:00:00+00:00",
        "last_active_at": "2026-09-03 10:00:00+00:00",
        "revoked_at": None,
    }
    row.update(overrides)
    return row


def install_password_store(monkeypatch, two_factor_enabled=False):
    secret = pyotp.random_base32() if two_factor_enabled else None
    state = {
        "users": {
            7: {
                "id": 7,
                "username": "Password Owner",
                "email": "owner@example.com",
                "password_hash": generate_password_hash("current-password"),
            },
            99: {
                "id": 99,
                "username": "Other User",
                "email": "other@example.com",
                "password_hash": generate_password_hash("other-password"),
            },
        },
        "sessions": [
            session_row(1, 7, "current-device-token"),
            session_row(2, 7, "other-device-token"),
            session_row(3, 99, "other-user-token"),
        ],
        "preferences": {7: {"two_factor_enabled": two_factor_enabled}},
        "credentials": (
            {
                7: {
                    "secret_encrypted": application.encrypt_totp_secret(secret),
                    "enabled_at": "2026-09-03 12:00:00+00:00",
                }
            }
            if two_factor_enabled
            else {}
        ),
        "totp_secret": secret,
    }
    calls = {"change": [], "create_session": []}

    def is_active(user_id, session_token_hash):
        return any(
            row["user_id"] == user_id
            and row["session_token_hash"] == session_token_hash
            and row["revoked_at"] is None
            for row in state["sessions"]
        )

    def list_sessions(user_id, current_session_token_hash):
        return [
            {
                "id": row["id"],
                "device_info": row["device_info"],
                "ip_address": row["ip_address"],
                "created_at": row["created_at"],
                "last_active_at": row["last_active_at"],
                "is_current": row["session_token_hash"] == current_session_token_hash,
            }
            for row in state["sessions"]
            if row["user_id"] == user_id and row["revoked_at"] is None
        ]

    def verify_password(user_id, password):
        user = state["users"].get(user_id)
        return bool(user and check_password_hash(user["password_hash"], password))

    def change_password(user_id, new_password, current_session_token_hash):
        calls["change"].append((user_id, new_password, current_session_token_hash))
        user = state["users"].get(user_id)
        if not user:
            return False
        user["password_hash"] = generate_password_hash(new_password)
        for row in state["sessions"]:
            if (
                row["user_id"] == user_id
                and row["session_token_hash"] != current_session_token_hash
                and row["revoked_at"] is None
            ):
                row["revoked_at"] = "2026-09-03 13:00:00+00:00"
        return True

    def get_totp_status(user_id):
        credential = state["credentials"].get(user_id)
        return {
            "is_enabled": bool(credential and credential["enabled_at"] is not None),
            "setup_pending": bool(credential and credential["enabled_at"] is None),
        }

    def create_session(user_id, session_token_hash, device_info, ip_address):
        calls["create_session"].append((user_id, session_token_hash))
        state["sessions"].append(
            {
                "id": len(state["sessions"]) + 1,
                "user_id": user_id,
                "session_token_hash": session_token_hash,
                "device_info": device_info,
                "ip_address": ip_address,
                "created_at": "2026-09-03 14:00:00+00:00",
                "last_active_at": "2026-09-03 14:00:00+00:00",
                "revoked_at": None,
            }
        )
        return {"id": len(state["sessions"])}

    def login(email, password):
        for user in state["users"].values():
            if user["email"] == email and check_password_hash(user["password_hash"], password):
                return True, {key: value for key, value in user.items() if key != "password_hash"}
        return False, None

    monkeypatch.setattr(application, "is_user_session_active", is_active)
    monkeypatch.setattr(application, "list_active_user_sessions", list_sessions)
    monkeypatch.setattr(application, "verify_user_password", verify_password)
    monkeypatch.setattr(application, "update_user_password_and_revoke_other_sessions", change_password)
    monkeypatch.setattr(application, "get_totp_status", get_totp_status)
    monkeypatch.setattr(application, "get_totp_credential", lambda user_id: state["credentials"].get(user_id))
    monkeypatch.setattr(application, "get_user_by_id", lambda user_id: state["users"].get(user_id))
    monkeypatch.setattr(application, "create_user_session", create_session)
    monkeypatch.setattr(application, "login_user", login)
    return state, calls


def security_csrf_token(client):
    client.get("/profile/security")
    with client.session_transaction() as session:
        return session["security_sessions_csrf_token"]


def password_form(client, token, **overrides):
    data = {
        "_security_sessions_csrf_token": token,
        "current_password": "current-password",
        "new_password": "new-password",
        "confirm_password": "new-password",
    }
    data.update(overrides)
    return data


def test_password_change_requires_authentication():
    response = application.app.test_client().post("/profile/security/password", data={})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_password_change_is_post_only():
    assert application.app.test_client().get("/profile/security/password").status_code == 405


def test_successful_password_change_hashes_password_revokes_other_devices_and_keeps_current_session(monkeypatch):
    state, calls = install_password_store(monkeypatch)
    original_hash = state["users"][7]["password_hash"]
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/password",
        data=password_form(client, security_csrf_token(client)),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile/security")
    assert state["users"][7]["password_hash"] != original_hash
    assert state["users"][7]["password_hash"] != "new-password"
    assert check_password_hash(state["users"][7]["password_hash"], "new-password")
    assert not check_password_hash(state["users"][7]["password_hash"], "current-password")
    assert calls["change"] == [(7, "new-password", token_hash("current-device-token"))]
    assert state["sessions"][0]["revoked_at"] is None
    assert state["sessions"][1]["revoked_at"] is not None
    assert state["sessions"][2]["revoked_at"] is None
    assert client.get("/profile").status_code == 200


def test_old_password_fails_and_new_password_authenticates(monkeypatch):
    _, _ = install_password_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)
    client.post(
        "/profile/security/password",
        data=password_form(client, security_csrf_token(client)),
    )
    with client.session_transaction() as session:
        session.clear()

    old_password = client.post("/login", data={"email": "owner@example.com", "password": "current-password"})
    new_password = client.post("/login", data={"email": "owner@example.com", "password": "new-password"})

    assert old_password.status_code == 200
    assert b"Invalid email or password." in old_password.data
    assert new_password.status_code == 302
    assert new_password.headers["Location"].endswith("/dashboard")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"current_password": ""}, b"All password fields are required."),
        ({"new_password": ""}, b"All password fields are required."),
        ({"confirm_password": ""}, b"All password fields are required."),
        ({"current_password": "wrong-password"}, b"Current password is incorrect."),
        ({"confirm_password": "different-password"}, b"New password and confirmation do not match."),
        ({"new_password": "current-password", "confirm_password": "current-password"}, b"New password must be different from the current password."),
        ({"new_password": "short", "confirm_password": "short"}, b"Password must contain at least 6 characters."),
    ],
)
def test_invalid_password_changes_do_not_update_or_revoke_sessions(monkeypatch, overrides, message):
    state, calls = install_password_store(monkeypatch)
    original_hash = state["users"][7]["password_hash"]
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/password",
        data=password_form(client, security_csrf_token(client), **overrides),
    )

    assert response.status_code == 400
    assert message in response.data
    assert state["users"][7]["password_hash"] == original_hash
    assert calls["change"] == []
    assert all(row["revoked_at"] is None for row in state["sessions"])


def test_password_change_rejects_missing_or_invalid_csrf(monkeypatch):
    state, calls = install_password_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)

    missing = client.post("/profile/security/password", data=password_form(client, ""))
    security_csrf_token(client)
    invalid = client.post("/profile/security/password", data=password_form(client, "invalid"))

    assert missing.status_code == 400
    assert invalid.status_code == 400
    assert calls["change"] == []
    assert all(row["revoked_at"] is None for row in state["sessions"])


def test_client_user_id_cannot_change_another_users_password(monkeypatch):
    state, calls = install_password_store(monkeypatch)
    other_hash = state["users"][99]["password_hash"]
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/password?user_id=99",
        data=password_form(client, security_csrf_token(client), user_id="99"),
    )

    assert response.status_code == 302
    assert calls["change"][-1][0] == 7
    assert state["users"][99]["password_hash"] == other_hash


def test_password_change_preserves_two_factor_state_and_login_requirement(monkeypatch):
    state, _ = install_password_store(monkeypatch, two_factor_enabled=True)
    original_credential = dict(state["credentials"][7])
    client = application.app.test_client()
    set_authenticated_session(client)
    client.post(
        "/profile/security/password",
        data=password_form(client, security_csrf_token(client)),
    )

    assert state["credentials"][7] == original_credential
    assert state["preferences"][7]["two_factor_enabled"] is True
    with client.session_transaction() as session:
        session.clear()

    password_login = client.post("/login", data={"email": "owner@example.com", "password": "new-password"})

    assert password_login.status_code == 302
    assert password_login.headers["Location"].endswith("/login/2fa")
    with client.session_transaction() as session:
        assert session["pending_2fa_user_id"] == 7
        assert "uid" not in session

    client.get("/login/2fa")
    with client.session_transaction() as session:
        csrf_token = session["two_factor_login_csrf_token"]
    verified_login = client.post(
        "/login/2fa",
        data={"_two_factor_login_csrf_token": csrf_token, "totp_code": pyotp.TOTP(state["totp_secret"]).now()},
    )

    assert verified_login.status_code == 302
    assert verified_login.headers["Location"].endswith("/dashboard")


def test_database_password_update_helper_hashes_password_and_scopes_session_revocation(monkeypatch):
    executions = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query, params):
            executions.append((query, params))

        def fetchone(self):
            return {"id": 7}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(database, "get_connection", connection)

    assert database.update_user_password_and_revoke_other_sessions(7, "new-password", "current-hash")

    password_update, session_update = executions
    assert password_update[1][1] == 7
    assert password_update[1][0] != "new-password"
    assert check_password_hash(password_update[1][0], "new-password")
    assert "WHERE id = %s" in password_update[0]
    assert session_update[1] == (7, "current-hash")
    assert "session_token_hash <> %s" in session_update[0]
