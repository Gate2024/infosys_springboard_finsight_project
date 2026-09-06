from decimal import Decimal

import app as application
from app import (
    BUDGET_APPROACHING_LIMIT,
    BUDGET_HEALTHY_LIMIT,
    build_budget_spending_analysis,
    calculate_budget_utilization,
    classify_budget_status,
)


def budget(name, amount, spent, remaining=None, user_id=7):
    return {
        "budget_name": name,
        "category": "General",
        "budget_amount": amount,
        "spent_amount": spent,
        "remaining_amount": remaining,
        "user_id": user_id,
    }


def test_budget_utilization_and_status_thresholds():
    assert calculate_budget_utilization(100, 79) == Decimal("79")
    assert classify_budget_status(BUDGET_HEALTHY_LIMIT - 1) == "Healthy"
    assert classify_budget_status(BUDGET_HEALTHY_LIMIT) == "Approaching Limit"
    assert classify_budget_status(BUDGET_APPROACHING_LIMIT) == "Approaching Limit"
    assert classify_budget_status(BUDGET_APPROACHING_LIMIT + 1) == "Over Budget"


def test_zero_budget_has_unavailable_utilization():
    assert calculate_budget_utilization(0, 0) is None
    assert calculate_budget_utilization(-100, -10) is None
    assert classify_budget_status(None) == "Unavailable"


def test_budget_analysis_calculates_rows_and_totals():
    rows, summary = build_budget_spending_analysis(
        [
            budget("Housing", Decimal("1000"), Decimal("650"), Decimal("350")),
            budget("Travel", Decimal("500"), Decimal("600"), Decimal("-100")),
        ],
        {
            "total_allocated": Decimal("1500"),
            "total_spent": Decimal("1250"),
            "total_remaining": Decimal("250"),
        },
    )

    assert len(rows) == 2
    assert rows[0]["utilization_percentage"] == Decimal("65")
    assert rows[0]["status"] == "Healthy"
    assert rows[1]["utilization_percentage"] == Decimal("120")
    assert rows[1]["status"] == "Over Budget"
    assert summary["total_budget"] == Decimal("1500")
    assert summary["total_spent"] == Decimal("1250")
    assert summary["total_remaining"] == Decimal("250")
    assert summary["utilization_percentage"] == Decimal("83.33333333333333333333333333")


def test_empty_budget_analysis_is_safe():
    rows, summary = build_budget_spending_analysis(
        [],
        {"total_allocated": 0, "total_spent": 0, "total_remaining": 0},
    )

    assert rows == []
    assert summary["utilization_percentage"] is None
    assert summary["status"] == "Unavailable"


def test_budget_analysis_does_not_mix_user_records():
    rows, _ = build_budget_spending_analysis(
        [budget("Owned Budget", 100, 50, 50, user_id=7)],
        {"total_allocated": 100, "total_spent": 50, "total_remaining": 50},
    )

    assert [row["budget_name"] for row in rows] == ["Owned Budget"]
    assert all(row["budget_name"] != "Other User Budget" for row in rows)


def test_budget_analysis_does_not_modify_stored_budget_data():
    stored_budget = budget("Owned Budget", 100, 50, 50)
    original_budget = stored_budget.copy()

    build_budget_spending_analysis(
        [stored_budget],
        {"total_allocated": 100, "total_spent": 50, "total_remaining": 50},
    )

    assert stored_budget == original_budget


def test_dashboard_queries_budgets_for_authenticated_user(monkeypatch, tracked_session_store):
    budget_calls = []

    monkeypatch.setattr(
        application,
        "get_summary_stats",
        lambda user_id: {
            "total_allocated": 100,
            "total_spent": 50,
            "total_remaining": 50,
        },
    )
    monkeypatch.setattr(
        application,
        "get_expense_summary",
        lambda user_id: {
            "total_spent": 0,
            "average_expense": 0,
            "largest_expense": 0,
            "total_expenses": 0,
            "month_spent": 0,
            "month_expenses": 0,
        },
    )
    monkeypatch.setattr(application, "get_transactions", lambda user_id: [])
    monkeypatch.setattr(application, "get_monthly_expense_summary", lambda user_id: [])

    def owned_budgets(user_id):
        budget_calls.append(user_id)
        return [budget("Owned Budget", 100, 50, 50, user_id=user_id)]

    monkeypatch.setattr(application, "filter_budgets", owned_budgets)
    monkeypatch.setattr(application.goal_service, "list_for_user", lambda user_id: [])
    monkeypatch.setattr(
        application.investment_service,
        "list_for_user",
        lambda user_id: ([], {"return_percentage": None}),
    )
    monkeypatch.setattr(
        application,
        "calculate_financial_health",
        lambda **kwargs: {
            "available": False,
            "score": None,
            "grade": "Insufficient Data",
            "coverage": 0,
            "components": {},
        },
    )

    tracked_session_store(7)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Budget Tester"

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert budget_calls == [7]
    assert b"Owned Budget" in response.data
    assert b"Other User Budget" not in response.data
