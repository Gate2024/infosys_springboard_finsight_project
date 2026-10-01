import pytest

import app as application
import db


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
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


def test_notification_filters_are_server_side_and_user_scoped(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_notification_read_requires_csrf_and_preserves_ownership(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_notification_read_cannot_target_another_users_record(monkeypatch, tracked_session_store):
    tracked_session_store(8)
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


def test_mark_all_read_is_csrf_protected_and_user_scoped(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_notification_popup_uses_real_count_and_categories(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_budget_threshold_notification_is_created_once_for_owned_user(monkeypatch):
    created = []
    monkeypatch.setattr(application, "get_notifications", lambda _user_id: created)
    monkeypatch.setattr(
        application,
        "create_notification",
        lambda user_id, notification_type, title, message: created.append(
            {"user_id": user_id, "type": notification_type, "title": title, "message": message}
        ),
    )
    previous = {"budget_amount": "1000", "spent_amount": "700", "alert_percentage": "80"}
    current = {
        "budget_name": "Food",
        "budget_amount": "1000",
        "spent_amount": "850",
        "alert_percentage": "80",
    }

    application._notify_for_budget_transition(7, previous, current)
    application._notify_for_budget_transition(7, previous, current)

    assert len(created) == 1
    assert created[0]["user_id"] == 7
    assert created[0]["type"] == "alert"


def test_goal_completion_notification_is_created_once_and_isolated(monkeypatch):
    created = []
    monkeypatch.setattr(application, "get_notifications", lambda _user_id: created)
    monkeypatch.setattr(
        application,
        "create_notification",
        lambda user_id, notification_type, title, message: created.append(
            {"user_id": user_id, "type": notification_type, "title": title, "message": message}
        ),
    )
    incomplete = {"status": "Active"}
    completed = {"status": "Completed", "goal_name": "Emergency Fund"}

    application._notify_for_goal_transition(8, incomplete, completed)
    application._notify_for_goal_transition(8, completed, completed)

    assert len(created) == 1
    assert created[0]["user_id"] == 8
    assert created[0]["type"] == "milestone"

    def failing_create(*_args):
        raise RuntimeError("notification unavailable")

    monkeypatch.setattr(application, "create_notification", failing_create)
    application._notify_for_goal_transition(9, incomplete, {**completed, "goal_name": "Travel"})


def test_budget_success_survives_post_operation_lookup_failure(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    client = application.app.test_client()
    set_session(client, 7)
    with client.session_transaction() as session:
        session["budget_csrf_token"] = "budget-token"
    monkeypatch.setattr(application, "create_budget", lambda *_args: {"budget_id": 1})
    monkeypatch.setattr(application, "get_budget", lambda *_args: (_ for _ in ()).throw(RuntimeError("read failed")))

    response = client.post(
        "/budget/create",
        data={
            "_budget_csrf_token": "budget-token",
            "budget_name": "Food",
            "category": "Food & Dining",
            "status": "Active",
            "budget_amount": "1000",
            "spent_amount": "0",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )

    assert response.status_code == 302


def test_goal_success_survives_post_operation_lookup_failure(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    client = application.app.test_client()
    set_session(client, 7)
    with client.session_transaction() as session:
        session["goal_csrf_token"] = "goal-token"
    monkeypatch.setattr(application.goal_service, "create", lambda *_args: ({"goal_id": 1}, []))
    monkeypatch.setattr(application.goal_service, "get_for_user", lambda *_args: (_ for _ in ()).throw(RuntimeError("read failed")))

    response = client.post(
        "/goals/create",
        data={
            "_goal_csrf_token": "goal-token",
            "goal_name": "Emergency Fund",
            "goal_category": "Savings",
            "target_amount": "10000",
            "current_amount": "10000",
            "target_date": "2030-01-01",
        },
    )

    assert response.status_code == 302


@pytest.mark.parametrize(
    ("title", "message"),
    [
        ("Password changed", "Your account password was changed successfully."),
    ],
)
def test_security_notification_content_is_user_scoped_and_non_sensitive(
    monkeypatch, title, message
):
    created = []
    monkeypatch.setattr(application, "get_notifications", lambda _user_id: created)
    monkeypatch.setattr(
        application,
        "create_notification",
        lambda user_id, notification_type, notification_title, notification_message: created.append(
            {
                "user_id": user_id,
                "type": notification_type,
                "title": notification_title,
                "message": notification_message,
            }
        ),
    )

    application._create_business_notification(7, "alert", title, message)

    assert created == [{"user_id": 7, "type": "alert", "title": title, "message": message}]
    assert all(secret not in str(created[0]) for secret in ("password123", "123456", "secret"))


def test_security_notification_failure_is_isolated(monkeypatch):
    monkeypatch.setattr(application, "get_notifications", lambda _user_id: [])
    monkeypatch.setattr(
        application,
        "create_notification",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("notification unavailable")),
    )

    application._create_business_notification(
        7,
        "alert",
        "Password changed",
        "Your account password was changed successfully.",
    )


class HealthStateDatabase:
    def __init__(self):
        self.states = {}
        self.notifications = []
        self.fail_state = False
        self.fail_notification = False
        self.lock_calls = []

    def connection(self):
        database = self

        class Connection:
            def __enter__(self):
                self.snapshot = (
                    dict(database.states),
                    list(database.notifications),
                )
                return self

            def __exit__(self, exc_type, _exc, _tb):
                if exc_type:
                    database.states.clear()
                    database.states.update(self.snapshot[0])
                    database.notifications[:] = self.snapshot[1]
                return False

            def cursor(self):
                return Cursor(database)

        return Connection()


class Cursor:
    def __init__(self, database):
        self.database = database
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split()).lower()
        if "pg_advisory_xact_lock" in normalized:
            self.database.lock_calls.append(tuple(params))
        elif normalized.startswith("select grade"):
            state = self.database.states.get(params[0])
            self.result = {"grade": state["grade"]} if state else None
        elif normalized.startswith("insert into financial_health_state"):
            if self.database.fail_state:
                raise RuntimeError("state persistence failed")
            self.database.states[params[0]] = {"grade": params[1], "score": params[2]}
        elif normalized.startswith("insert into notifications"):
            if self.database.fail_notification:
                raise RuntimeError("notification insertion failed")
            self.database.notifications.append({"user_id": params[0]})

    def fetchone(self):
        return self.result


def health_state_store(monkeypatch):
    store = HealthStateDatabase()
    monkeypatch.setattr(db, "get_connection", store.connection)
    return store


@pytest.mark.parametrize("grade", ["Fair", "Good", "Excellent", "Needs Improvement"])
def test_health_first_meaningful_grade_establishes_baseline_without_notification(monkeypatch, grade):
    store = health_state_store(monkeypatch)

    assert db.record_financial_health_evaluation(7, grade, 20) is False
    assert store.states[7]["grade"] == grade
    assert store.notifications == []


@pytest.mark.parametrize("previous", ["Fair", "Good", "Excellent"])
def test_health_meaningful_grade_to_needs_improvement_notifies(monkeypatch, previous):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": previous, "score": 50}

    assert db.record_financial_health_evaluation(7, "Needs Improvement", 20) is True
    assert store.notifications == [{"user_id": 7}]


def test_health_staying_needs_improvement_does_not_duplicate(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Needs Improvement", "score": 20}

    assert db.record_financial_health_evaluation(7, "Needs Improvement", 15) is False
    assert store.notifications == []


def test_health_improvement_then_reentry_notifies_again(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Good", "score": 70}

    assert db.record_financial_health_evaluation(7, "Needs Improvement", 20) is True
    assert db.record_financial_health_evaluation(7, "Fair", 45) is False
    assert db.record_financial_health_evaluation(7, "Needs Improvement", 20) is True
    assert len(store.notifications) == 2


def test_health_insufficient_data_does_not_overwrite_state(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Good", "score": 70}

    assert db.record_financial_health_evaluation(7, "Insufficient Data", None) is False
    assert store.states[7]["grade"] == "Good"
    assert store.notifications == []


def test_health_notification_failure_rolls_back_state_and_retries(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Fair", "score": 45}
    store.fail_notification = True

    with pytest.raises(RuntimeError):
        db.record_financial_health_evaluation(7, "Needs Improvement", 20)
    assert store.states[7]["grade"] == "Fair"
    assert store.notifications == []

    store.fail_notification = False
    assert db.record_financial_health_evaluation(7, "Needs Improvement", 20) is True
    assert store.states[7]["grade"] == "Needs Improvement"
    assert len(store.notifications) == 1


def test_health_state_persistence_failure_preserves_existing_state(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Good", "score": 70}
    store.fail_state = True

    with pytest.raises(RuntimeError):
        db.record_financial_health_evaluation(7, "Needs Improvement", 20)
    assert store.states[7]["grade"] == "Good"
    assert store.notifications == []


def test_health_state_is_user_scoped(monkeypatch):
    store = health_state_store(monkeypatch)
    store.states[7] = {"grade": "Good", "score": 70}
    store.states[8] = {"grade": "Needs Improvement", "score": 20}

    assert db.record_financial_health_evaluation(7, "Needs Improvement", 20) is True
    assert db.record_financial_health_evaluation(8, "Needs Improvement", 20) is False
    assert store.notifications == [{"user_id": 7}]
    assert {user_id for _, user_id in store.lock_calls} == {7, 8}
