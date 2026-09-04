import app as application


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Notification Owner"
        session["email"] = f"user{user_id}@example.com"


def sample_notifications():
    return [
        {
            "id": 1,
            "user_id": 7,
            "type": "alert",
            "title": "Budget alert",
            "message": "A budget needs attention.",
            "is_read": False,
            "created_at": None,
        },
        {
            "id": 2,
            "user_id": 7,
            "type": "milestone",
            "title": "Goal milestone",
            "message": "A goal reached a milestone.",
            "is_read": True,
            "created_at": None,
        },
    ]


def install_notification_store(monkeypatch):
    rows = sample_notifications()
    calls = []

    def get_notifications(user_id, filter_type="all", limit=None):
        calls.append(("get", user_id, filter_type, limit))
        filtered = [row for row in rows if row["user_id"] == user_id]
        if filter_type == "unread":
            filtered = [row for row in filtered if not row["is_read"]]
        elif filter_type in {"alert", "milestone"}:
            filtered = [row for row in filtered if row["type"] == filter_type]
        return filtered[:limit] if limit is not None else filtered

    def unread_count(user_id):
        calls.append(("count", user_id))
        return sum(not row["is_read"] for row in rows if row["user_id"] == user_id)

    def mark_read(user_id, notification_id):
        calls.append(("read", user_id, notification_id))
        for row in rows:
            if row["user_id"] == user_id and row["id"] == notification_id:
                row["is_read"] = True
                return True
        return False

    monkeypatch.setattr(application, "get_notifications", get_notifications)
    monkeypatch.setattr(application, "get_unread_notification_count", unread_count)
    monkeypatch.setattr(application, "mark_notification_read", mark_read)
    return rows, calls


def test_notifications_require_authentication():
    response = application.app.test_client().get("/notifications")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_notification_filters_are_server_side_and_user_scoped(monkeypatch):
    _, calls = install_notification_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)

    for filter_type, expected_title in (
        ("all", "Budget alert"),
        ("unread", "Budget alert"),
        ("alert", "Budget alert"),
        ("milestone", "Goal milestone"),
    ):
        response = client.get(f"/notifications?filter={filter_type}")
        assert response.status_code == 200
        assert expected_title.encode() in response.data
        assert any(call[0] == "get" and call[2] == filter_type and call[1] == 7 for call in calls)

    assert all(call[1] == 7 for call in calls)


def test_notification_read_requires_csrf_and_preserves_ownership(monkeypatch):
    _, calls = install_notification_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    client.get("/notifications")
    with client.session_transaction() as session:
        token = session["notifications_csrf_token"]

    response = client.post("/notifications/1/read", data={"_notifications_csrf_token": token})
    assert response.status_code == 302
    assert ("read", 7, 1) in calls
    assert ("read", 7, 999) not in calls


def test_notification_read_cannot_target_another_users_record(monkeypatch):
    _, calls = install_notification_store(monkeypatch)
    client = application.app.test_client()
    set_session(client, user_id=8)
    client.get("/notifications")
    with client.session_transaction() as session:
        token = session["notifications_csrf_token"]

    response = client.post(
        "/notifications/1/read",
        data={"_notifications_csrf_token": token},
    )
    assert response.status_code == 302
    assert ("read", 8, 1) in calls


def test_mark_all_read_is_csrf_protected_and_user_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(application, "get_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda _user_id: 0)
    monkeypatch.setattr(application, "mark_all_notifications_read", lambda user_id: calls.append(user_id))
    client = application.app.test_client()
    set_session(client, user_id=7)
    client.get("/notifications")
    with client.session_transaction() as session:
        token = session["notifications_csrf_token"]

    response = client.post(
        "/notifications/read-all",
        data={"_notifications_csrf_token": token},
    )
    assert response.status_code == 302
    assert calls == [7]


def test_notification_popup_uses_real_count_and_categories(monkeypatch):
    install_notification_store(monkeypatch)
    client = application.app.test_client()
    set_session(client)
    response = client.get("/notifications")
    assert response.status_code == 200
    assert b"notification-count" in response.data
    assert b"All" in response.data and b"Unread" in response.data
    assert b"Alerts" in response.data and b"Milestone" in response.data
    assert b"data-notification-theme-choice=\"light\"" in response.data
    assert b"data-notification-theme-choice=\"dark\"" in response.data
    assert b'action=\"/profile/preferences\"' in response.data
