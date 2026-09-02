import pytest

import app as application


CSRF_TOKEN = "csrf-test-token"


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "CSRF Tester"
        session["budget_csrf_token"] = CSRF_TOKEN
        session["expense_csrf_token"] = CSRF_TOKEN


def budget_data(**overrides):
    data = {
        "budget_name": "Monthly Budget",
        "category": "Food & Dining",
        "status": "Active",
        "budget_amount": "1000.00",
        "spent_amount": "100.00",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "_budget_csrf_token": CSRF_TOKEN,
    }
    data.update(overrides)
    return data


def expense_data(**overrides):
    data = {
        "description": "Lunch",
        "amount": "25.00",
        "date": "2026-08-01",
        "category": "Food & Dining",
        "payment_mode": "Cash",
        "_expense_csrf_token": CSRF_TOKEN,
    }
    data.update(overrides)
    return data


@pytest.fixture
def client():
    client = application.app.test_client()
    set_session(client)
    return client


@pytest.fixture
def budget_store(monkeypatch):
    rows = []

    def create(user_id, payload):
        rows.append({"budget_id": len(rows) + 1, "user_id": user_id, **dict(payload)})

    def get(budget_id, user_id):
        return next((row for row in rows if row["budget_id"] == budget_id and row["user_id"] == user_id), None)

    def update(budget_id, user_id, payload):
        row = get(budget_id, user_id)
        if not row:
            return False
        row.update(dict(payload))
        return True

    def delete(budget_id, user_id):
        before = len(rows)
        rows[:] = [row for row in rows if not (row["budget_id"] == budget_id and row["user_id"] == user_id)]
        return len(rows) < before

    monkeypatch.setattr(application, "create_budget", create)
    monkeypatch.setattr(application, "get_budget", get)
    monkeypatch.setattr(application, "update_budget", update)
    monkeypatch.setattr(application, "delete_budget", delete)
    monkeypatch.setattr(application, "filter_budgets", lambda user_id, **kwargs: [row for row in rows if row["user_id"] == user_id])
    monkeypatch.setattr(application, "get_summary_stats", lambda user_id: {})
    return rows


@pytest.fixture
def expense_store(monkeypatch):
    rows = []

    def create(user_id, payload):
        rows.append({"id": len(rows) + 1, "user_id": user_id, **dict(payload)})

    def get(transaction_id, user_id):
        return next((row for row in rows if row["id"] == transaction_id and row["user_id"] == user_id), None)

    def update(transaction_id, user_id, payload):
        row = get(transaction_id, user_id)
        if not row:
            return False
        row.update(dict(payload))
        return True

    def delete(transaction_id, user_id):
        before = len(rows)
        rows[:] = [row for row in rows if not (row["id"] == transaction_id and row["user_id"] == user_id)]
        return len(rows) < before

    import db

    monkeypatch.setattr(db, "create_transaction", create)
    monkeypatch.setattr(db, "get_transaction", get)
    monkeypatch.setattr(db, "update_transaction", update)
    monkeypatch.setattr(db, "delete_transaction", delete)
    monkeypatch.setattr(db, "get_transactions", lambda user_id, **kwargs: [row for row in rows if row["user_id"] == user_id])
    monkeypatch.setattr(db, "get_expense_summary", lambda user_id: {})
    return rows


def test_budget_create_valid_csrf_succeeds(client, budget_store):
    response = client.post("/budget/create", data=budget_data())
    assert response.status_code == 302
    assert len(budget_store) == 1


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_budget_create_rejects_missing_or_invalid_csrf(client, budget_store, token):
    data = budget_data()
    if token is None:
        data.pop("_budget_csrf_token")
    else:
        data["_budget_csrf_token"] = token
    response = client.post("/budget/create", data=data)
    assert response.status_code == 400
    assert budget_store == []


def test_budget_edit_valid_csrf_succeeds(client, budget_store):
    budget_store.append({"budget_id": 1, "user_id": 7, **budget_data()})
    response = client.post("/budget/edit/1", data=budget_data(budget_name="Updated Budget"))
    assert response.status_code == 302
    assert budget_store[0]["budget_name"] == "Updated Budget"


def test_budget_edit_without_csrf_is_rejected(client, budget_store):
    budget_store.append({"budget_id": 1, "user_id": 7, **budget_data()})
    data = budget_data(budget_name="Should Not Update")
    data.pop("_budget_csrf_token")
    response = client.post("/budget/edit/1", data=data)
    assert response.status_code == 400
    assert budget_store[0]["budget_name"] == "Monthly Budget"


def test_budget_delete_valid_csrf_succeeds(client, budget_store):
    budget_store.append({"budget_id": 1, "user_id": 7, **budget_data()})
    response = client.post("/budget/delete/1", data={"_budget_csrf_token": CSRF_TOKEN})
    assert response.status_code == 302
    assert budget_store == []


def test_budget_delete_without_csrf_is_rejected(client, budget_store):
    budget_store.append({"budget_id": 1, "user_id": 7, **budget_data()})
    response = client.post("/budget/delete/1", data={})
    assert response.status_code == 302
    assert len(budget_store) == 1


def test_expense_create_valid_csrf_succeeds(client, expense_store):
    response = client.post("/expense/create", data=expense_data())
    assert response.status_code == 302
    assert len(expense_store) == 1


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_expense_create_rejects_missing_or_invalid_csrf(client, expense_store, token):
    data = expense_data()
    if token is None:
        data.pop("_expense_csrf_token")
    else:
        data["_expense_csrf_token"] = token
    response = client.post("/expense/create", data=data)
    assert response.status_code == 400
    assert expense_store == []


def test_expense_edit_valid_csrf_succeeds(client, expense_store):
    expense_store.append({"id": 1, "user_id": 7, **expense_data()})
    response = client.post("/expense/edit/1", data=expense_data(description="Updated Lunch"))
    assert response.status_code == 302
    assert expense_store[0]["description"] == "Updated Lunch"


def test_expense_edit_without_csrf_is_rejected(client, expense_store):
    expense_store.append({"id": 1, "user_id": 7, **expense_data()})
    data = expense_data(description="Should Not Update")
    data.pop("_expense_csrf_token")
    response = client.post("/expense/edit/1", data=data)
    assert response.status_code == 400
    assert expense_store[0]["description"] == "Lunch"


def test_expense_delete_valid_csrf_succeeds(client, expense_store):
    expense_store.append({"id": 1, "user_id": 7, **expense_data()})
    response = client.post("/expense/delete/1", data={"_expense_csrf_token": CSRF_TOKEN})
    assert response.status_code == 302
    assert expense_store == []


def test_expense_delete_without_csrf_is_rejected(client, expense_store):
    expense_store.append({"id": 1, "user_id": 7, **expense_data()})
    response = client.post("/expense/delete/1", data={})
    assert response.status_code == 302
    assert len(expense_store) == 1


def test_cross_user_budget_mutation_remains_denied(client, budget_store):
    budget_store.append({"budget_id": 1, "user_id": 99, **budget_data()})
    response = client.post("/budget/delete/1", data={"_budget_csrf_token": CSRF_TOKEN})
    assert response.status_code == 302
    assert len(budget_store) == 1


def test_cross_user_expense_mutation_remains_denied(client, expense_store):
    expense_store.append({"id": 1, "user_id": 99, **expense_data()})
    response = client.post("/expense/delete/1", data={"_expense_csrf_token": CSRF_TOKEN})
    assert response.status_code == 302
    assert len(expense_store) == 1


def test_get_cannot_delete_budget_or_expense(client, budget_store, expense_store):
    budget_store.append({"budget_id": 1, "user_id": 7, **budget_data()})
    expense_store.append({"id": 1, "user_id": 7, **expense_data()})
    assert client.get("/budget/delete/1").status_code == 405
    assert client.get("/expense/delete/1").status_code == 405
    assert len(budget_store) == 1
    assert len(expense_store) == 1
