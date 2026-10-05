from io import BytesIO

import app as application


def set_session(client, user_id=7, username="Profile Owner"):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = username
        session["email"] = f"user{user_id}@example.com"
        session["auth_csrf_token"] = "profile-csrf"


def profile_user(user_id=7, username="Profile Owner", email="owner@example.com"):
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "full_name": username,
        "date_of_birth": None,
        "address": "",
        "has_profile_image": False,
    }


def test_authenticated_user_can_access_profile(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
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
        "get_user_profile_by_id",
        lambda user_id: profile_user(user_id, "Profile Owner", "owner@example.com"),
    )
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert b"Profile Owner" in response.data
    assert b"owner@example.com" in response.data


def test_profile_never_displays_password_hash(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
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

    monkeypatch.setattr(application, "get_user_profile_by_id", fake_get_user)
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

    monkeypatch.setattr(application, "get_user_profile_by_id", fake_get_user)
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/profile?user_id=99")

    assert response.status_code == 200
    assert calls == [7]
    assert b"Profile Owner" in response.data


def test_other_users_profile_data_is_not_rendered(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(
        application,
        "get_user_profile_by_id",
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

    monkeypatch.setattr(application, "get_user_profile_by_id", fake_get_user)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile")

    assert response.status_code == 200
    assert calls == [7]


def test_profile_rejects_mutating_requests():
    response = application.app.test_client().post("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_existing_login_page_behavior_remains_available():
    response = application.app.test_client().get("/login")

    assert response.status_code == 200
    assert b'id="signInForm"' in response.data


def test_profile_update_is_user_scoped_and_keeps_email_read_only(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
    monkeypatch.setattr(application, "is_username_available", lambda username, user_id: True)
    calls = []

    def save_profile(user_id, **data):
        calls.append((user_id, data))
        return profile_user(user_id, data["username"], "owner@example.com")

    monkeypatch.setattr(application, "update_user_profile", save_profile)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile",
        data={
            "_auth_csrf_token": "profile-csrf",
            "full_name": "Updated Owner",
            "username": "updated_owner",
            "date_of_birth": "1990-05-10",
            "address": "1 FinSight Way",
        },
    )

    assert response.status_code == 302
    assert calls == [
        (
            7,
            {
                "full_name": "Updated Owner",
                "username": "updated_owner",
                "date_of_birth": "1990-05-10",
                "address": "1 FinSight Way",
                "image_data": None,
                "image_mime": None,
                "image_selected": False,
            },
        )
    ]


def test_profile_rejects_duplicate_username(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
    monkeypatch.setattr(application, "is_username_available", lambda username, user_id: False)
    update_called = False

    def unexpected_update(*args, **kwargs):
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(application, "update_user_profile", unexpected_update)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile",
        data={
            "_auth_csrf_token": "profile-csrf",
            "full_name": "Updated Owner",
            "username": "taken_name",
            "date_of_birth": "1990-05-10",
            "address": "",
        },
    )

    assert response.status_code == 400
    assert b"already in use" in response.data
    assert not update_called


def test_profile_rejects_future_date_of_birth(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
    monkeypatch.setattr(application, "is_username_available", lambda username, user_id: True)
    monkeypatch.setattr(application, "update_user_profile", lambda *args, **kwargs: profile_user())
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile",
        data={
            "_auth_csrf_token": "profile-csrf",
            "full_name": "Updated Owner",
            "username": "updated_owner",
            "date_of_birth": "2999-01-01",
            "address": "",
        },
    )

    assert response.status_code == 400
    assert b"cannot be in the future" in response.data


def test_profile_avatar_requires_authentication():
    response = application.app.test_client().get("/profile/avatar")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_rejects_invalid_image_upload(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(application, "get_user_profile_by_id", lambda user_id: profile_user(user_id))
    monkeypatch.setattr(application, "is_username_available", lambda username, user_id: True)
    monkeypatch.setattr(
        application,
        "update_user_profile",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("invalid image was saved")),
    )
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile",
        data={
            "_auth_csrf_token": "profile-csrf",
            "full_name": "Profile Owner",
            "username": "profile_owner",
            "date_of_birth": "",
            "address": "",
            "profile_image": (BytesIO(b"not-an-image"), "avatar.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"not a valid image" in response.data


def test_profile_picture_removal_is_user_scoped_and_csrf_protected(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    removed = []
    monkeypatch.setattr(application, "remove_user_profile_image", lambda user_id: removed.append(user_id))
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/avatar/remove",
        data={"_auth_csrf_token": "profile-csrf"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert removed == [7]
