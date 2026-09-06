import app as application


def set_session(client, user_id=7, username="Profile Owner"):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = username
        session["email"] = f"user{user_id}@example.com"


def profile_user(user_id=7, username="Profile Owner", email="owner@example.com"):
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": "never-render-this-password-hash",
    }


def test_authenticated_user_can_access_profile(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_by_id", lambda user_id: profile_user(user_id))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert response.status_code == 200
    assert b"My Profile" in response.data


def test_profile_requires_authentication():
    response = application.app.test_client().get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_displays_logged_in_username_and_email(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: profile_user(user_id, "Profile Owner", "owner@example.com"),
    )
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert b"Profile Owner" in response.data
    assert b"owner@example.com" in response.data


def test_profile_never_displays_password_hash(monkeypatch):
    monkeypatch.setattr(application, "get_user_by_id", lambda user_id: profile_user(user_id))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert b"never-render-this-password-hash" not in response.data
    assert b"password_hash" not in response.data


def test_profile_uses_authenticated_session_user_id(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    calls = []

    def fake_get_user(user_id):
        calls.append(user_id)
        return profile_user(user_id)

    monkeypatch.setattr(application, "get_user_by_id", fake_get_user)
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/profile")

    assert response.status_code == 200
    assert calls == [7]


def test_client_user_id_cannot_access_another_profile(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    calls = []

    def fake_get_user(user_id):
        calls.append(user_id)
        return profile_user(user_id, "Profile Owner", "owner@example.com")

    monkeypatch.setattr(application, "get_user_by_id", fake_get_user)
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/profile?user_id=99")

    assert response.status_code == 200
    assert calls == [7]
    assert b"Profile Owner" in response.data


def test_other_users_profile_data_is_not_rendered(monkeypatch):
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: profile_user(user_id, "Profile Owner", "owner@example.com"),
    )
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/profile?user_id=99")

    assert b"Other User" not in response.data
    assert b"other@example.com" not in response.data


def test_viewing_profile_is_read_only(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    calls = []

    def fake_get_user(user_id):
        calls.append(user_id)
        return profile_user(user_id)

    monkeypatch.setattr(application, "get_user_by_id", fake_get_user)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert response.status_code == 200
    assert calls == [7]


def test_profile_rejects_mutating_requests():
    response = application.app.test_client().post("/profile")

    assert response.status_code == 405


def test_existing_login_page_behavior_remains_available():
    response = application.app.test_client().get("/login")

    assert response.status_code == 200
    assert b'id="signInForm"' in response.data
