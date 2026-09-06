import app as application


def set_session(client, user_id=7, username="Preference Owner"):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = username
        session["email"] = f"user{user_id}@example.com"


def preference_row(user_id=7, **overrides):
    preferences = {
        "user_id": user_id,
        "theme": "default",
        "currency": "USD",
        "language": "en",
        "budget_overspending_alerts": False,
        "weekly_savings_digest_enabled": False,
        "sip_due_date_reminders_enabled": False,
        "bill_due_date_reminders_enabled": False,
        "two_factor_enabled": False,
    }
    preferences.update(overrides)
    return preferences


def install_preference_store(monkeypatch, initial_preferences=None):
    state = {
        user_id: dict(preferences)
        for user_id, preferences in (
            initial_preferences if initial_preferences is not None else {7: preference_row()}
        ).items()
    }
    calls = {"ensure": [], "get": [], "update": [], "currencies": 0, "languages": 0}
    currencies = [
        {"code": "USD", "display_name": "US Dollar", "symbol": "$"},
        {"code": "INR", "display_name": "Indian Rupee", "symbol": "Rs."},
        {"code": "EUR", "display_name": "Euro", "symbol": "EUR"},
        {"code": "JPY", "display_name": "Japanese Yen", "symbol": "JPY"},
    ]
    languages = [
        {"code": "en", "display_name": "English"},
        {"code": "hi", "display_name": "Hindi"},
        {"code": "fr", "display_name": "French"},
    ]

    def ensure(user_id):
        calls["ensure"].append(user_id)
        state.setdefault(user_id, preference_row(user_id))
        return dict(state[user_id])

    def get(user_id):
        calls["get"].append(user_id)
        row = state.get(user_id)
        return dict(row) if row else None

    def update(user_id, values):
        calls["update"].append((user_id, dict(values)))
        state.setdefault(user_id, preference_row(user_id))
        state[user_id].update(values)
        return dict(state[user_id])

    def list_currencies():
        calls["currencies"] += 1
        return list(currencies)

    def list_languages():
        calls["languages"] += 1
        return list(languages)

    monkeypatch.setattr(application, "ensure_user_preferences", ensure)
    monkeypatch.setattr(application, "get_user_preferences", get)
    monkeypatch.setattr(application, "update_user_preferences", update)
    monkeypatch.setattr(application, "list_preference_currencies", list_currencies)
    monkeypatch.setattr(application, "list_preference_languages", list_languages)
    return state, calls


def preferences_csrf_token(client):
    client.get("/profile/preferences")
    with client.session_transaction() as session:
        return session["preferences_csrf_token"]


def valid_form(token, **overrides):
    form = {
        "_preferences_csrf_token": token,
        "theme": "default",
        "currency": "USD",
        "language": "en",
    }
    form.update(overrides)
    return form


def test_authenticated_user_can_access_preferences(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile/preferences")

    assert response.status_code == 200
    assert b"Preferences" in response.data


def test_preferences_require_authentication():
    response = application.app.test_client().get("/profile/preferences")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_existing_preferences_are_displayed(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    install_preference_store(
        monkeypatch,
        {7: preference_row(currency="EUR", budget_overspending_alerts=True)},
    )
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile/preferences")

    assert b'value="EUR" selected' in response.data
    assert b'budget_overspending_alerts" type="checkbox" value="true" checked' in response.data


def test_currency_and_language_options_are_loaded_from_database_helpers(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    _, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile/preferences")

    assert response.status_code == 200
    assert b"USD - US Dollar ($)" in response.data
    assert b"JPY - Japanese Yen (JPY)" in response.data
    assert b"Hindi" in response.data
    assert calls["currencies"] == 1
    assert calls["languages"] == 1


def test_theme_preference_can_be_saved(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), theme="default"),
    )

    assert response.status_code == 302
    assert calls["update"][-1][0] == 7
    assert state[7]["theme"] == "default"


def test_currency_preference_can_be_saved(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), currency="EUR"),
    )

    assert response.status_code == 302
    assert state[7]["currency"] == "EUR"


def test_database_backed_jpy_currency_preference_can_be_saved(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), currency="JPY"),
    )

    assert response.status_code == 302
    assert state[7]["currency"] == "JPY"


def test_language_preference_can_be_saved(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch, {7: preference_row(language="fr")})
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), language="en"),
    )

    assert response.status_code == 302
    assert state[7]["language"] == "en"


def test_budget_overspending_alert_can_be_enabled_and_disabled(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    token = preferences_csrf_token(client)

    client.post("/profile/preferences", data=valid_form(token, budget_overspending_alerts="true"))
    assert state[7]["budget_overspending_alerts"] is True
    client.post("/profile/preferences", data=valid_form(token))

    assert state[7]["budget_overspending_alerts"] is False


def test_weekly_digest_can_be_enabled_and_disabled(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    token = preferences_csrf_token(client)

    client.post("/profile/preferences", data=valid_form(token, weekly_savings_digest_enabled="true"))
    assert state[7]["weekly_savings_digest_enabled"] is True
    client.post("/profile/preferences", data=valid_form(token))

    assert state[7]["weekly_savings_digest_enabled"] is False


def test_sip_reminder_can_be_enabled_and_disabled(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    token = preferences_csrf_token(client)

    client.post("/profile/preferences", data=valid_form(token, sip_due_date_reminders_enabled="true"))
    assert state[7]["sip_due_date_reminders_enabled"] is True
    client.post("/profile/preferences", data=valid_form(token))

    assert state[7]["sip_due_date_reminders_enabled"] is False


def test_bill_reminder_can_be_enabled_and_disabled(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    token = preferences_csrf_token(client)

    client.post("/profile/preferences", data=valid_form(token, bill_due_date_reminders_enabled="true"))
    assert state[7]["bill_due_date_reminders_enabled"] is True
    client.post("/profile/preferences", data=valid_form(token))

    assert state[7]["bill_due_date_reminders_enabled"] is False


def test_preferences_persist_after_a_new_get_request(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, _ = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), currency="INR"),
    )
    response = client.get("/profile/preferences")

    assert state[7]["currency"] == "INR"
    assert b'value="INR" selected' in response.data


def test_invalid_theme_is_rejected_without_saving(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), theme="<script>dark</script>"),
    )

    assert response.status_code == 400
    assert calls["update"] == []
    assert state[7]["theme"] == "default"


def test_invalid_currency_is_rejected_without_saving(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), currency="BAD"),
    )

    assert response.status_code == 400
    assert calls["update"] == []
    assert state[7]["currency"] == "USD"


def test_invalid_language_is_rejected_without_saving(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), language="zz"),
    )

    assert response.status_code == 400
    assert calls["update"] == []
    assert state[7]["language"] == "en"


def test_missing_csrf_token_is_rejected_without_creating_preferences(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch, {})
    client = application.app.test_client()
    set_session(client)

    response = client.post("/profile/preferences", data=valid_form(""))

    assert response.status_code == 400
    assert state == {}
    assert calls["ensure"] == []
    assert calls["update"] == []


def test_invalid_csrf_token_is_rejected_without_saving(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    preferences_csrf_token(client)

    response = client.post("/profile/preferences", data=valid_form("invalid-token"))

    assert response.status_code == 400
    assert calls["update"] == []
    assert state[7]["currency"] == "USD"


def test_client_user_id_cannot_modify_another_users_preferences(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(
        monkeypatch,
        {7: preference_row(), 99: preference_row(99, currency="INR")},
    )
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.post(
        "/profile/preferences?user_id=99",
        data=valid_form(preferences_csrf_token(client), currency="EUR", user_id="99"),
    )

    assert response.status_code == 302
    assert calls["update"][-1][0] == 7
    assert state[7]["currency"] == "EUR"
    assert state[99]["currency"] == "INR"


def test_other_users_preferences_are_never_returned(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    install_preference_store(
        monkeypatch,
        {7: preference_row(currency="USD"), 99: preference_row(99, currency="INR")},
    )
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/profile/preferences?user_id=99")

    assert b'value="USD" selected' in response.data
    assert b'value="INR" selected' not in response.data


def test_preferences_do_not_modify_financial_records(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state, calls = install_preference_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    response = client.post(
        "/profile/preferences",
        data=valid_form(preferences_csrf_token(client), currency="EUR"),
    )

    assert response.status_code == 302
    assert state[7]["currency"] == "EUR"
    assert [user_id for user_id, _ in calls["update"]] == [7]


def test_existing_login_page_behavior_remains_available():
    response = application.app.test_client().get("/login")

    assert response.status_code == 200
    assert b'id="signInForm"' in response.data
