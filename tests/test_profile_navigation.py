import app as application


def set_authenticated_session(client):
    with client.session_transaction() as session:
        session["uid"] = 7
        session["username"] = "Profile Owner"
        session["email"] = "owner@example.com"


def assert_account_dropdown(response):
    assert response.status_code == 200
    assert b"data-account-menu" in response.data
    assert b"My Profile" in response.data
    assert b"Preferences" in response.data
    assert b"Security &amp; 2FA" in response.data
    assert b'href="/profile"' in response.data
    assert b'href="/profile/preferences"' in response.data
    assert b'href="/profile/security"' in response.data
    assert b"<span>Profile</span>" not in response.data


def test_profile_navigation_is_active_on_my_profile(monkeypatch):
    monkeypatch.setattr(
        application,
        "get_user_by_id",
        lambda user_id: {"id": user_id, "username": "Profile Owner", "email": "owner@example.com"},
    )
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile")
    assert_account_dropdown(response)
    for icon_class in (
        "fa-grip",
        "fa-circle-arrow-up",
        "fa-wallet",
        "fa-chart-line",
        "fa-bullseye",
        "fa-file-lines",
        "fa-right-from-bracket",
    ):
        assert icon_class.encode() in response.data
    assert b'class="bi ' not in response.data


def test_profile_navigation_is_active_on_preferences(monkeypatch):
    monkeypatch.setattr(
        application,
        "ensure_user_preferences",
        lambda user_id: {"theme": "default", "currency": "USD", "language": "en"},
    )
    monkeypatch.setattr(
        application,
        "list_preference_currencies",
        lambda: [{"code": "USD", "display_name": "US Dollar", "symbol": "$"}],
    )
    monkeypatch.setattr(
        application,
        "list_preference_languages",
        lambda: [{"code": "en", "display_name": "English"}],
    )
    client = application.app.test_client()
    set_authenticated_session(client)

    assert_account_dropdown(client.get("/profile/preferences"))


def test_profile_navigation_is_active_on_security_and_contains_password_form(monkeypatch):
    monkeypatch.setattr(application, "list_active_user_sessions", lambda *args: [])
    monkeypatch.setattr(
        application,
        "get_totp_status",
        lambda user_id: {"is_enabled": False, "setup_pending": False},
    )
    client = application.app.test_client()
    set_authenticated_session(client)

    response = client.get("/profile/security")

    assert_account_dropdown(response)
    assert b'action="/profile/security/password"' in response.data
