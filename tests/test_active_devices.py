import hashlib

import app as application
from tests.auth_helpers import post_login


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_row(session_id, user_id, token, device_info, **overrides):
    row = {
        "id": session_id,
        "user_id": user_id,
        "session_token_hash": token_hash(token),
        "device_info": device_info,
        "ip_address": "127.0.0.1",
        "created_at": "2026-09-03 10:00:00+00:00",
        "last_active_at": "2026-09-03 10:00:00+00:00",
        "revoked_at": None,
    }
    row.update(overrides)
    return row


def set_authenticated_session(client, user_id=7, token="current-device-token"):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Device Owner"
        session["email"] = f"user{user_id}@example.com"
        session["auth_session_token"] = token


def install_session_store(monkeypatch, rows=None):
    state = {"rows": [dict(row) for row in (rows or [])]}
    calls = {"create": [], "active": [], "list": [], "revoke": [], "revoke_current": [], "revoke_all": []}

    def create(user_id, session_token_hash, device_info, ip_address):
        calls["create"].append((user_id, session_token_hash, device_info, ip_address))
        record = {
            "id": len(state["rows"]) + 1,
            "user_id": user_id,
            "session_token_hash": session_token_hash,
            "device_info": device_info,
            "ip_address": ip_address,
            "created_at": "2026-09-03 10:00:00+00:00",
            "last_active_at": "2026-09-03 10:00:00+00:00",
            "revoked_at": None,
        }
        state["rows"].append(record)
        return {key: value for key, value in record.items() if key != "session_token_hash"}

    def is_active(user_id, session_token_hash, *_timeouts):
        calls["active"].append((user_id, session_token_hash))
        return any(
            row["user_id"] == user_id
            and row["session_token_hash"] == session_token_hash
            and row["revoked_at"] is None
            for row in state["rows"]
        )

    def list_active(user_id, current_session_token_hash):
        calls["list"].append((user_id, current_session_token_hash))
        return [
            {
                "id": row["id"],
                "device_info": row["device_info"],
                "ip_address": row["ip_address"],
                "created_at": row["created_at"],
                "last_active_at": row["last_active_at"],
                "is_current": row["session_token_hash"] == current_session_token_hash,
            }
            for row in state["rows"]
            if row["user_id"] == user_id and row["revoked_at"] is None
        ]

    def revoke(session_id, user_id, current_session_token_hash):
        calls["revoke"].append((session_id, user_id, current_session_token_hash))
        for row in state["rows"]:
            if (
                row["id"] == session_id
                and row["user_id"] == user_id
                and row["session_token_hash"] != current_session_token_hash
                and row["revoked_at"] is None
            ):
                row["revoked_at"] = "2026-09-03 11:00:00+00:00"
                return True
        return False

    def revoke_current(user_id, session_token_hash):
        calls["revoke_current"].append((user_id, session_token_hash))
        for row in state["rows"]:
            if (
                row["user_id"] == user_id
                and row["session_token_hash"] == session_token_hash
                and row["revoked_at"] is None
            ):
                row["revoked_at"] = "2026-09-03 11:00:00+00:00"
                return True
        return False

    def revoke_all(user_id):
        calls["revoke_all"].append(user_id)
        active_rows = [
            row for row in state["rows"]
            if row["user_id"] == user_id and row["revoked_at"] is None
        ]
        for row in active_rows:
            row["revoked_at"] = "2026-09-03 11:00:00+00:00"
        return len(active_rows)

    monkeypatch.setattr(application, "create_user_session", create)
    monkeypatch.setattr(application, "is_user_session_active", is_active)
    monkeypatch.setattr(application, "list_active_user_sessions", list_active)
    monkeypatch.setattr(application, "revoke_user_session", revoke)
    monkeypatch.setattr(application, "revoke_current_user_session", revoke_current)
    monkeypatch.setattr(application, "revoke_all_user_sessions", revoke_all)
    monkeypatch.setattr(application, "revoke_all_remember_me_tokens", lambda *args: 0)
    return state, calls


def security_csrf_token(client):
    client.get("/profile/security")
    with client.session_transaction() as session:
        return session["security_sessions_csrf_token"]


def test_unauthenticated_user_cannot_access_active_devices():
    response = application.app.test_client().get("/profile/security")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_authenticated_user_can_see_only_own_active_devices(monkeypatch):
    current_token = "current-device-token"
    _, calls = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 7, "other-device-token", "Other browser"),
            session_row(3, 99, "other-user-token", "Other user's browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.get("/profile/security?user_id=99")

    assert response.status_code == 200
    assert b"Current browser" in response.data
    assert b"Other browser" in response.data
    assert b"Other user&#39;s browser" not in response.data
    assert calls["list"][-1][0] == 7


def test_successful_login_creates_only_a_hashed_session_record(monkeypatch):
    _, calls = install_session_store(monkeypatch)
    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, {"id": 7, "username": "Device Owner", "email": email}),
    )
    client = application.app.test_client()

    response = post_login(client, "/login", data={"email": "owner@example.com", "password": "password"})

    assert response.status_code == 302
    with client.session_transaction() as session:
        raw_session_token = session["auth_session_token"]
    persisted_hash = calls["create"][-1][1]
    assert persisted_hash == token_hash(raw_session_token)
    assert persisted_hash != raw_session_token
    assert raw_session_token.encode() not in response.data


def test_failed_login_does_not_create_an_active_session(monkeypatch):
    _, calls = install_session_store(monkeypatch)
    monkeypatch.setattr(application, "login_user", lambda email, password: (False, None))

    response = post_login(application.app.test_client(),
        "/login", data={"email": "owner@example.com", "password": "wrong"}
    )

    assert response.status_code == 200
    assert calls["create"] == []


def test_single_device_logout_requires_post(monkeypatch):
    current_token = "current-device-token"
    install_session_store(monkeypatch, [session_row(1, 7, current_token, "Current browser")])
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.get("/profile/security/sessions/2/logout")

    assert response.status_code == 405


def test_single_device_logout_revokes_only_owned_other_device(monkeypatch):
    current_token = "current-device-token"
    state, calls = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 7, "other-device-token", "Other browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.post(
        "/profile/security/sessions/2/logout",
        data={"_security_sessions_csrf_token": security_csrf_token(client)},
    )

    assert response.status_code == 302
    assert calls["revoke"][-1][1] == 7
    assert state["rows"][0]["revoked_at"] is None
    assert state["rows"][1]["revoked_at"] is not None


def test_revoked_device_is_not_listed_as_active(monkeypatch):
    current_token = "current-device-token"
    state, _ = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 7, "other-device-token", "Other browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)
    token = security_csrf_token(client)

    client.post("/profile/security/sessions/2/logout", data={"_security_sessions_csrf_token": token})
    response = client.get("/profile/security")

    assert state["rows"][1]["revoked_at"] is not None
    assert b"Other browser" not in response.data


def test_single_device_logout_rejects_missing_or_invalid_csrf(monkeypatch):
    current_token = "current-device-token"
    state, _ = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 7, "other-device-token", "Other browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    missing = client.post("/profile/security/sessions/2/logout", data={})
    security_csrf_token(client)
    invalid = client.post(
        "/profile/security/sessions/2/logout",
        data={"_security_sessions_csrf_token": "invalid"},
    )

    assert missing.status_code == 400
    assert invalid.status_code == 400
    assert state["rows"][1]["revoked_at"] is None


def test_user_cannot_revoke_another_users_session(monkeypatch):
    current_token = "current-device-token"
    state, calls = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 99, "other-user-token", "Other user's browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.post(
        "/profile/security/sessions/2/logout?user_id=99",
        data={"_security_sessions_csrf_token": security_csrf_token(client), "user_id": "99"},
    )

    assert response.status_code == 302
    assert calls["revoke"][-1][1] == 7
    assert state["rows"][1]["revoked_at"] is None


def test_logout_all_is_post_only_and_revokes_only_authenticated_users_sessions(monkeypatch):
    current_token = "current-device-token"
    state, calls = install_session_store(
        monkeypatch,
        [
            session_row(1, 7, current_token, "Current browser"),
            session_row(2, 7, "other-device-token", "Other browser"),
            session_row(3, 99, "other-user-token", "Other user's browser"),
        ],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    assert client.get("/profile/security/sessions/logout-all").status_code == 405
    response = client.post(
        "/profile/security/sessions/logout-all",
        data={"_security_sessions_csrf_token": security_csrf_token(client)},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert calls["revoke_all"] == [7]
    assert all(row["revoked_at"] is not None for row in state["rows"][:2])
    assert state["rows"][2]["revoked_at"] is None
    with client.session_transaction() as session:
        assert "uid" not in session


def test_logout_all_requires_csrf(monkeypatch):
    current_token = "current-device-token"
    state, calls = install_session_store(monkeypatch, [session_row(1, 7, current_token, "Current browser")])
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.post("/profile/security/sessions/logout-all", data={})

    assert response.status_code == 400
    assert calls["revoke_all"] == []
    assert state["rows"][0]["revoked_at"] is None


def test_revoked_tracked_session_cannot_access_authenticated_routes(monkeypatch):
    current_token = "revoked-device-token"
    install_session_store(
        monkeypatch,
        [session_row(1, 7, current_token, "Revoked browser", revoked_at="2026-09-03 11:00:00+00:00")],
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as session:
        assert "uid" not in session


def test_normal_logout_revokes_current_tracked_session(monkeypatch):
    current_token = "current-device-token"
    state, calls = install_session_store(monkeypatch, [session_row(1, 7, current_token, "Current browser")])
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    client.get("/profile/security")
    with client.session_transaction() as session:
        csrf_token = session["auth_csrf_token"]
    response = client.post("/logout", data={"_auth_csrf_token": csrf_token})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert calls["revoke_current"] == [(7, token_hash(current_token))]
    assert state["rows"][0]["revoked_at"] is not None


def test_active_devices_never_render_hashes_or_financial_data(monkeypatch):
    current_token = "current-device-token"
    _, _ = install_session_store(
        monkeypatch,
        [session_row(1, 7, current_token, "Current browser")],
    )
    monkeypatch.setattr(
        application,
        "get_summary_stats",
        lambda *args: (_ for _ in ()).throw(AssertionError("financial data was queried")),
    )
    client = application.app.test_client()
    set_authenticated_session(client, token=current_token)

    response = client.get("/profile/security")

    assert token_hash(current_token).encode() not in response.data
    assert current_token.encode() not in response.data
    assert b"password_hash" not in response.data
