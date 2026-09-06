from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import app as application


class FakeGoalRepository:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def list_for_user(self, user_id):
        return [deepcopy(row) for row in self.rows if row["user_id"] == user_id]

    def get_for_user(self, goal_id, user_id):
        for row in self.rows:
            if row["goal_id"] == goal_id and row["user_id"] == user_id:
                return deepcopy(row)
        return None

    def create(self, user_id, payload):
        row = dict(payload)
        row.update({"goal_id": self.next_id, "user_id": user_id, "created_at": date.today()})
        self.next_id += 1
        self.rows.append(row)
        return {"goal_id": row["goal_id"]}

    def update(self, goal_id, user_id, payload):
        for row in self.rows:
            if row["goal_id"] == goal_id and row["user_id"] == user_id:
                row.update(payload)
                return True
        return False

    def delete(self, goal_id, user_id):
        before = len(self.rows)
        self.rows = [row for row in self.rows if not (
            row["goal_id"] == goal_id and row["user_id"] == user_id
        )]
        return len(self.rows) < before


@pytest.fixture
def goal_repository():
    repository = FakeGoalRepository()
    application.goal_service.repository = repository
    return repository


@pytest.fixture
def client(goal_repository, tracked_session_store):
    tracked_session_store(7)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Goal Tester"
        session["goal_csrf_token"] = "goal-test-token"
    return client


def goal_data(**overrides):
    data = {
        "goal_name": "Emergency Fund",
        "goal_category": "Savings",
        "target_amount": "10000.00",
        "current_amount": "2500.00",
        "target_date": "2030-01-01",
        "_goal_csrf_token": "goal-test-token",
    }
    data.update(overrides)
    return data


def test_empty_goal_list(client):
    response = client.get("/goals")
    assert response.status_code == 200
    assert b"No financial goals yet" in response.data


def test_create_list_and_view_goal(client, goal_repository):
    response = client.post("/goals/create", data=goal_data())
    assert response.status_code == 302
    assert goal_repository.rows[0]["status"] == "Active"

    response = client.get("/goals")
    assert b"Emergency Fund" in response.data
    assert b"25.00%" in response.data
    assert b"$7,500.00" in response.data

    response = client.get("/goals/1")
    assert response.status_code == 200
    assert b"Target Amount" in response.data


def test_update_goal_recalculates_progress_and_completion(client, goal_repository):
    client.post("/goals/create", data=goal_data())
    response = client.post(
        "/goals/1/edit",
        data=goal_data(current_amount="10000"),
    )
    assert response.status_code == 302
    assert goal_repository.rows[0]["status"] == "Completed"

    response = client.get("/goals/1")
    assert b"100.00%" in response.data
    assert b"Completed" in response.data
    assert b"$0.00 remaining" in response.data


def test_delete_goal_and_cross_user_access_are_denied(client, goal_repository):
    goal_repository.create(99, {
        "goal_name": "Private Goal", "goal_category": "Travel",
        "target_amount": Decimal("1000"), "current_amount": Decimal("0"),
        "target_date": date(2030, 1, 1), "status": "Active",
    })
    assert client.get("/goals/1").status_code == 302
    assert client.post("/goals/1/delete", data={"_goal_csrf_token": "goal-test-token"}).status_code == 302
    assert goal_repository.get_for_user(1, 99) is not None

    client.post("/goals/create", data=goal_data())
    response = client.post("/goals/2/delete", data={"_goal_csrf_token": "goal-test-token"})
    assert response.status_code == 302
    assert goal_repository.get_for_user(2, 7) is None


@pytest.mark.parametrize("field,value", [
    ("goal_name", ""),
    ("goal_category", "Unrelated"),
    ("target_amount", "0"),
    ("target_amount", "not-a-number"),
    ("current_amount", "-1"),
    ("current_amount", "not-a-number"),
    ("target_date", "not-a-date"),
])
def test_invalid_goal_is_rejected(client, field, value):
    response = client.post("/goals/create", data=goal_data(**{field: value}))
    assert response.status_code == 400
    assert b"danger" in response.data


def test_goal_csrf_is_required(client):
    data = goal_data()
    data.pop("_goal_csrf_token")
    assert client.post("/goals/create", data=data).status_code == 400


def test_goal_migration_is_forward_safe():
    sql = Path("database/migrations/003_create_goals.sql").read_text(encoding="utf-8").upper()
    assert "CREATE TABLE IF NOT EXISTS GOALS" in sql
    assert "REFERENCES USERS(ID) ON DELETE CASCADE" in sql
    assert "TARGET_AMOUNT NUMERIC(14, 2) NOT NULL CHECK (TARGET_AMOUNT > 0)" in sql
    assert "CURRENT_AMOUNT NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (CURRENT_AMOUNT >= 0)" in sql
    assert "DROP TABLE" not in sql
    assert "DELETE FROM" not in sql
