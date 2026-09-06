import pyotp
import pytest
from time import time

import app as application
from tests.auth_helpers import post_login


@pytest.fixture(autouse=True)
def clear_login_failures():
    application._login_failures.clear()
    yield
    application._login_failures.clear()


def set_authenticated_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Two Factor Owner"
        session["email"] = f"user{user_id}@example.com"
        session["auth_session_token"] = f"tracked-token-{user_id}"


def users():
    return {
        7: {"id": 7, "username": "Two Factor Owner", "email": "owner@example.com"},
        99: {"id": 99, "username": "Other User", "email": "other@example.com"},
    }


def install_two_factor_store(monkeypatch, credentials=None):
    state = {
        "credentials": {user_id: dict(credential) for user_id, credential in (credentials or {}).items()},
        "sessions": [],
    }
    calls = {"create_session": [], "save": [], "enable": [], "disable": [], "verify_password": []}

    def get_status(user_id):
        credential = state["credentials"].get(user_id)
        return {
            "is_enabled": bool(credential and credential["enabled_at"] is not None),
            "setup_pending": bool(credential and credential["enabled_at"] is None),
        }

    def get_credential(user_id):
        credential = state["credentials"].get(user_id)
        return dict(credential) if credential else None

    def save_pending(user_id, secret_encrypted):
        calls["save"].append((user_id, secret_encrypted))
        state["credentials"][user_id] = {
            "secret_encrypted": secret_encrypted,
            "enabled_at": None,
        }
        return True

    def enable(user_id):
        calls["enable"].append(user_id)
        credential = state["credentials"].get(user_id)
        if not credential or credential["enabled_at"] is not None:
            return False
        credential["enabled_at"] = "2026-09-03 12:00:00+00:00"
        return True

    def disable(user_id):
        calls["disable"].append(user_id)
        return state["credentials"].pop(user_id, None) is not None

    def create_session(user_id, session_token_hash, device_info, ip_address):
        calls["create_session"].append((user_id, session_token_hash, device_info, ip_address))
        state["sessions"].append({"id": len(state["sessions"]) + 1, "user_id": user_id})
        return {"id": len(state["sessions"])}

    def list_sessions(user_id, current_session_token_hash):
        return [
            {
                "id": row["id"],
                "device_info": "Current browser",
                "ip_address": "127.0.0.1",
                "created_at": "2026-09-03 10:00:00+00:00",
                "last_active_at": "2026-09-03 10:00:00+00:00",
                "is_current": True,
            }
            for row in state["sessions"]
            if row["user_id"] == user_id
        ]

    monkeypatch.setattr(application, "get_totp_status", get_status)
    monkeypatch.setattr(application, "get_totp_credential", get_credential)
    monkeypatch.setattr(application, "save_pending_totp_secret", save_pending)
    monkeypatch.setattr(application, "enable_totp_for_user", enable)
    monkeypatch.setattr(application, "disable_totp_for_user", disable)
    monkeypatch.setattr(application, "create_user_session", create_session)
    monkeypatch.setattr(application, "is_user_session_active", lambda *args: True)
    monkeypatch.setattr(application, "list_active_user_sessions", list_sessions)
    monkeypatch.setattr(application, "revoke_current_user_session", lambda *args: True)
    monkeypatch.setattr(application, "revoke_all_user_sessions", lambda *args: 1)
    monkeypatch.setattr(application, "revoke_all_remember_me_tokens", lambda *args: 0)
    monkeypatch.setattr(application, "revoke_user_session", lambda *args: True)
    monkeypatch.setattr(application, "verify_user_password", lambda user_id, password: calls["verify_password"].append((user_id, password)) or password == "correct-password")
    monkeypatch.setattr(application, "get_user_by_id", lambda user_id: users().get(user_id))
    return state, calls


def security_csrf_token(client):
    client.get("/profile/security")
    with client.session_transaction() as session:
        return session["security_sessions_csrf_token"]


def pending_login_csrf_token(client):
    client.get("/login/2fa")
    with client.session_transaction() as session:
        return session["two_factor_login_csrf_token"]


def enable_credential(state, user_id=7, secret=None):
    secret = secret or pyotp.random_base32()
    state["credentials"][user_id] = {
        "secret_encrypted": application.encrypt_totp_secret(secret),
        "enabled_at": "2026-09-03 12:00:00+00:00",
    }
    return secret


def test_authenticated_user_can_access_security_page(monkeypatch):
    install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile/security")

    assert response.status_code == 200
    assert b"Two-Factor Authentication" in response.data


def test_setup_generates_encrypted_pending_secret_without_enabling_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/totp/setup",
        data={"_security_sessions_csrf_token": security_csrf_token(client)},
    )

    encrypted_secret = calls["save"][-1][1]
    assert response.status_code == 200
    assert calls["save"][-1][0] == 7
    assert encrypted_secret != application.decrypt_totp_secret(encrypted_secret)
    assert state["credentials"][7]["enabled_at"] is None
    assert calls["enable"] == []
    assert application.decrypt_totp_secret(encrypted_secret).encode() in response.data


def test_opening_security_page_does_not_enable_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile/security")

    assert response.status_code == 200
    assert state["credentials"] == {}
    assert calls["enable"] == []


def test_setup_secret_is_not_exposed_to_another_user(monkeypatch):
    state, _ = install_two_factor_store(monkeypatch)
    owner = application.app.test_client()
    set_authenticated_session(owner, user_id=7)
    setup = owner.post(
        "/profile/security/totp/setup",
        data={"_security_sessions_csrf_token": security_csrf_token(owner)},
    )
    owner_secret = application.decrypt_totp_secret(state["credentials"][7]["secret_encrypted"])

    other_user = application.app.test_client()
    set_authenticated_session(other_user, user_id=99)
    response = other_user.get("/profile/security?user_id=7")

    assert owner_secret.encode() in setup.data
    assert owner_secret.encode() not in response.data


def test_valid_totp_verification_enables_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)
    token = security_csrf_token(client)
    client.post("/profile/security/totp/setup", data={"_security_sessions_csrf_token": token})
    secret = application.decrypt_totp_secret(state["credentials"][7]["secret_encrypted"])

    response = client.post(
        "/profile/security/totp/verify",
        data={"_security_sessions_csrf_token": token, "totp_code": pyotp.TOTP(secret).now()},
    )

    assert response.status_code == 302
    assert calls["enable"] == [7]
    assert state["credentials"][7]["enabled_at"] is not None


def test_invalid_totp_does_not_enable_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)
    token = security_csrf_token(client)
    client.post("/profile/security/totp/setup", data={"_security_sessions_csrf_token": token})

    response = client.post(
        "/profile/security/totp/verify",
        data={"_security_sessions_csrf_token": token, "totp_code": "000000"},
    )

    assert response.status_code == 400
    assert calls["enable"] == []
    assert state["credentials"][7]["enabled_at"] is None


def test_expired_totp_does_not_enable_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)
    token = security_csrf_token(client)
    client.post("/profile/security/totp/setup", data={"_security_sessions_csrf_token": token})
    secret = application.decrypt_totp_secret(state["credentials"][7]["secret_encrypted"])

    response = client.post(
        "/profile/security/totp/verify",
        data={
            "_security_sessions_csrf_token": token,
            "totp_code": pyotp.TOTP(secret).at(int(time()) - 60),
        },
    )

    assert response.status_code == 400
    assert calls["enable"] == []
    assert state["credentials"][7]["enabled_at"] is None


def test_two_factor_setup_rejects_missing_or_invalid_csrf(monkeypatch):
    state, _ = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client)

    missing = client.post("/profile/security/totp/setup", data={})
    security_csrf_token(client)
    invalid = client.post(
        "/profile/security/totp/setup",
        data={"_security_sessions_csrf_token": "invalid"},
    )

    assert missing.status_code == 400
    assert invalid.status_code == 400
    assert state["credentials"] == {}


def test_valid_password_and_totp_disable_two_factor_and_remove_secret(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    secret = enable_credential(state)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/totp/disable",
        data={
            "_security_sessions_csrf_token": security_csrf_token(client),
            "current_password": "correct-password",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 302
    assert calls["verify_password"] == [(7, "correct-password")]
    assert calls["disable"] == [7]
    assert 7 not in state["credentials"]


def test_incorrect_password_cannot_disable_two_factor(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    secret = enable_credential(state)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.post(
        "/profile/security/totp/disable",
        data={
            "_security_sessions_csrf_token": security_csrf_token(client),
            "current_password": "wrong-password",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 400
    assert calls["disable"] == []
    assert 7 in state["credentials"]


def test_disable_two_factor_rejects_invalid_csrf(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    enable_credential(state)
    client = application.app.test_client()
    set_authenticated_session(client)
    security_csrf_token(client)

    response = client.post(
        "/profile/security/totp/disable",
        data={"_security_sessions_csrf_token": "invalid"},
    )

    assert response.status_code == 400
    assert calls["disable"] == []


def test_user_without_two_factor_logs_in_and_creates_tracked_session(monkeypatch):
    _, calls = install_two_factor_store(monkeypatch)
    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, users()[7]),
    )
    client = application.app.test_client()

    response = post_login(client, "/login", data={"email": "owner@example.com", "password": "password"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert len(calls["create_session"]) == 1
    with client.session_transaction() as session:
        assert session["uid"] == 7
        assert "pending_2fa_user_id" not in session


def test_two_factor_login_requires_code_before_creating_device_session(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    enable_credential(state)
    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, users()[7]),
    )
    client = application.app.test_client()

    response = post_login(client, "/login", data={"email": "owner@example.com", "password": "password"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login/2fa")
    assert calls["create_session"] == []
    with client.session_transaction() as session:
        assert session["pending_2fa_user_id"] == 7
        assert "uid" not in session


def test_invalid_totp_login_does_not_authenticate_or_create_device_session(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    enable_credential(state)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["pending_2fa_user_id"] = 7

    response = client.post(
        "/login/2fa",
        data={"_two_factor_login_csrf_token": pending_login_csrf_token(client), "totp_code": "000000"},
    )

    assert response.status_code == 200
    assert calls["create_session"] == []
    with client.session_transaction() as session:
        assert session["pending_2fa_user_id"] == 7
        assert "uid" not in session


def test_valid_totp_login_authenticates_and_creates_tracked_device(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    secret = enable_credential(state)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["pending_2fa_user_id"] = 7

    response = client.post(
        "/login/2fa",
        data={
            "_two_factor_login_csrf_token": pending_login_csrf_token(client),
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert len(calls["create_session"]) == 1
    with client.session_transaction() as session:
        assert session["uid"] == 7
        assert "pending_2fa_user_id" not in session


def test_pending_two_factor_session_cannot_access_protected_routes(monkeypatch):
    install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["pending_2fa_user_id"] = 7

    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_client_user_id_cannot_start_two_factor_for_another_user(monkeypatch):
    state, calls = install_two_factor_store(monkeypatch)
    client = application.app.test_client()
    set_authenticated_session(client, user_id=7)

    response = client.post(
        "/profile/security/totp/setup?user_id=99",
        data={"_security_sessions_csrf_token": security_csrf_token(client), "user_id": "99"},
    )

    assert response.status_code == 200
    assert calls["save"][-1][0] == 7
    assert 99 not in state["credentials"]


def test_two_factor_secret_is_not_rendered_after_it_is_enabled(monkeypatch):
    state, _ = install_two_factor_store(monkeypatch)
    secret = enable_credential(state)
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile/security")

    assert secret.encode() not in response.data
    assert state["credentials"][7]["secret_encrypted"].encode() not in response.data


def test_two_factor_page_does_not_query_financial_data(monkeypatch):
    install_two_factor_store(monkeypatch)
    monkeypatch.setattr(
        application,
        "get_summary_stats",
        lambda *args: (_ for _ in ()).throw(AssertionError("financial data was queried")),
    )
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile/security")

    assert response.status_code == 200
