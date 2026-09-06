from copy import deepcopy
from decimal import Decimal

import app as application


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = f"User {user_id}"


def dashboard_data(user_id):
    return {
        "stats": {
            "total_allocated": Decimal("1000"),
            "total_spent": Decimal("250"),
            "total_remaining": Decimal("750"),
        },
        "expense_stats": {
            "total_spent": Decimal("250"),
            "average_expense": Decimal("125"),
            "largest_expense": Decimal("150"),
            "total_expenses": 2,
            "month_spent": Decimal("250"),
            "month_expenses": 2,
        },
        "transactions": [
            {
                "user_id": user_id,
                "category": "Food",
                "description": "Owned expense",
                "date": "2026-08-01",
                "type": "Expense",
                "amount": Decimal("150"),
            },
            {
                "user_id": user_id,
                "category": "Transport",
                "description": "Second owned expense",
                "date": "2026-08-02",
                "type": "Expense",
                "amount": Decimal("100"),
            },
        ],
        "monthly_expenses": [{"month": "2026-08", "amount": Decimal("250")}],
        "budgets": [
            {
                "user_id": user_id,
                "budget_name": "Owned Budget",
                "category": "General",
                "budget_amount": Decimal("1000"),
                "spent_amount": Decimal("250"),
                "remaining_amount": Decimal("750"),
            }
        ],
        "goals": [],
        "investments": ([], {"return_percentage": None}),
    }


def patch_dashboard_data(monkeypatch, data, calls=None, financial_health=None):
    calls = calls if calls is not None else []
    financial_health = financial_health or {
        "available": False,
        "score": None,
        "grade": "Insufficient Data",
        "coverage": 0,
        "components": {},
    }

    def record(function, value):
        def loader(user_id):
            calls.append((function, user_id))
            return value

        return loader

    monkeypatch.setattr(
        application,
        "get_summary_stats",
        record("stats", data["stats"]),
    )
    monkeypatch.setattr(
        application,
        "get_expense_summary",
        record("expense_stats", data["expense_stats"]),
    )
    monkeypatch.setattr(
        application,
        "get_transactions",
        record("transactions", data["transactions"]),
    )
    monkeypatch.setattr(
        application,
        "get_monthly_expense_summary",
        record("monthly_expenses", data["monthly_expenses"]),
    )
    monkeypatch.setattr(
        application,
        "filter_budgets",
        record("budgets", data["budgets"]),
    )
    monkeypatch.setattr(
        application.goal_service,
        "list_for_user",
        record("goals", data["goals"]),
    )
    monkeypatch.setattr(
        application.investment_service,
        "list_for_user",
        record("investments", data["investments"]),
    )
    monkeypatch.setattr(
        application,
        "calculate_financial_health",
        lambda **kwargs: financial_health,
    )
    return calls


def test_unauthenticated_dashboard_redirects_to_login():
    response = application.app.test_client().get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_authenticated_dashboard_renders_dynamic_sections(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    patch_dashboard_data(monkeypatch, data)
    monkeypatch.setattr(
        application,
        "build_spending_recommendations",
        lambda *args: [
            {
                "title": "Review spending",
                "message": "Review this budget.",
                "style": "warning",
                "icon": "bi bi-exclamation-circle",
                "priority": "High",
            }
        ],
    )
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Owned expense" in response.data
    assert b"Food" in response.data
    assert b"Owned Budget" in response.data
    assert b"Budget vs Spending" in response.data
    assert b"Review spending" in response.data
    assert b"2026-08" in response.data


def test_dashboard_uses_authenticated_user_and_ignores_client_user_id(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    calls = patch_dashboard_data(monkeypatch, dashboard_data(7))
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard?user_id=99")

    assert response.status_code == 200
    assert calls
    assert all(user_id == 7 for _, user_id in calls)
    assert b"Owned expense" in response.data


def test_dashboard_does_not_render_another_users_expenses(monkeypatch, tracked_session_store):
    tracked_session_store(2)
    data = dashboard_data(2)
    patch_dashboard_data(monkeypatch, data)

    def scoped_transactions(user_id):
        return [
            {
                "user_id": user_id,
                "category": "Food",
                "description": f"User {user_id} expense",
                "date": "2026-08-01",
                "type": "Expense",
                "amount": Decimal("150"),
            }
        ]

    monkeypatch.setattr(application, "get_transactions", scoped_transactions)
    client = application.app.test_client()
    set_session(client, 2)

    response = client.get("/dashboard?user_id=1")

    assert response.status_code == 200
    assert b"User 2 expense" in response.data
    assert b"User 1 expense" not in response.data


def test_empty_budget_data_renders_safely(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    data["stats"] = {
        "total_allocated": 0,
        "total_spent": 0,
        "total_remaining": 0,
    }
    data["budgets"] = []
    patch_dashboard_data(monkeypatch, data)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"No budget data available" in response.data
    assert b"No budgets available yet" in response.data


def test_budget_progress_and_budget_spending_data_remain_correct(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    patch_dashboard_data(monkeypatch, dashboard_data(7))
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Owned Budget" in response.data
    assert b"25.0% used" in response.data
    assert b"width:25.0%" in response.data


def test_spending_recommendations_remain_correct(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    data["stats"] = {
        "total_allocated": 100,
        "total_spent": 125,
        "total_remaining": -25,
    }
    data["budgets"][0].update(
        {
            "budget_amount": 100,
            "spent_amount": 125,
            "remaining_amount": -25,
        }
    )
    patch_dashboard_data(monkeypatch, data)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Spending Recommendations" in response.data
    assert b"Your Owned Budget budget is over its stored limit" in response.data


def test_financial_health_score_remains_available(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    health = {
        "available": True,
        "score": 88,
        "grade": "Strong",
        "coverage": 75,
        "components": {
            name: {
                "available": False,
                "score": None,
                "weight": weight,
                "message": "Unavailable",
            }
            for name, weight in (
                ("budget", 35),
                ("spending", 20),
                ("goals", 25),
                ("investments", 20),
            )
        },
    }
    patch_dashboard_data(monkeypatch, dashboard_data(7), financial_health=health)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b">88</strong>" in response.data
    assert b"Strong" in response.data
    assert b"Based on 75%" in response.data


def test_dashboard_does_not_mutate_financial_records(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    original = deepcopy(data)
    patch_dashboard_data(monkeypatch, data)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert data == original


def test_dashboard_does_not_derive_unsupported_metrics(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    data["stats"].update(
        {
            "total_income": Decimal("987654321"),
            "total_savings": Decimal("876543210"),
            "balance": Decimal("765432109"),
        }
    )
    data["expense_stats"]["income"] = Decimal("654321098")
    patch_dashboard_data(monkeypatch, data)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"987654321" not in response.data
    assert b"876543210" not in response.data
    assert b"765432109" not in response.data
    assert b"654321098" not in response.data


def test_empty_expense_data_does_not_break_dashboard(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = dashboard_data(7)
    data["expense_stats"] = {
        "total_spent": 0,
        "average_expense": 0,
        "largest_expense": 0,
        "total_expenses": 0,
        "month_spent": 0,
        "month_expenses": 0,
    }
    data["transactions"] = []
    data["monthly_expenses"] = []
    patch_dashboard_data(monkeypatch, data)
    client = application.app.test_client()
    set_session(client, 7)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"No expense data available" in response.data
    assert b"No monthly spending data available" in response.data
