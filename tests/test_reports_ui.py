from copy import deepcopy
from decimal import Decimal

import app as application


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Reports Tester"


def report_data():
    return {
        "date_range": {"start_date": "2026-05-01", "end_date": "2026-05-31"},
        "expenses": {
            "expense_summary": {
                "total_expenses": 600.5,
                "transaction_count": 3,
                "average_expense": 200.1667,
                "largest_expense": 300.0,
                "month_expenses": 1,
                "month_spent": 100.0,
            },
            "category_totals": [{"category": "Food", "amount": 600.5}],
            "monthly_totals": [{"month": "2026-05", "amount": 600.5}],
        },
        "budgets": {"overall_utilization": 75.0},
        "investments": {
            "stats": {
                "current_value": 1200.0,
                "total_invested": 1000.0,
                "absolute_return": 200.0,
                "return_percentage": 20.0,
                "allocation": [{"asset_type": "Stocks", "percentage": 100.0}],
            }
        },
        "goals": {
            "goal_count": 1,
            "goals": [
                {
                    "goal_name": "Emergency Fund",
                    "goal_category": "Savings",
                    "status": "Active",
                    "current_amount": Decimal("250"),
                    "target_amount": Decimal("1000"),
                    "progress_percentage": Decimal("25"),
                    "remaining_amount": Decimal("750"),
                    "target_date": "2030-01-01",
                }
            ],
        },
        "financial_health": {
            "available": True,
            "score": 79,
            "grade": "Good",
            "components": {
                "budget": {"available": True, "score": 35, "message": "Budget is healthy."}
            },
        },
        "unavailable_metrics": {
            "recent_alerts": {"reason": "No persisted alerts available."},
        },
    }


def test_authenticated_reports_page_renders_real_report_data(monkeypatch):
    data = report_data()
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: deepcopy(data))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert b"Reports Overview" in response.data
    assert b"Food" in response.data
    assert b"2026-05" in response.data
    assert b"Emergency Fund" in response.data
    assert "$1,200.00".encode() in response.data
    assert b"window.reportsExpenseCategories" in response.data
    assert b"window.reportsMonthlyExpenses" in response.data


def test_reports_page_requires_authentication():
    response = application.app.test_client().get(
        "/reports", headers={"Accept": "text/html"}
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_reports_page_uses_session_user_not_client_user_id(monkeypatch):
    calls = []

    def fake_build(user_id, start_date, end_date, *, investment_service, goal_service):
        calls.append(user_id)
        return report_data()

    monkeypatch.setattr(application, "build_reporting_data", fake_build)
    client = application.app.test_client()
    set_session(client)

    response = client.get(
        "/reports?user_id=99", headers={"Accept": "text/html"}
    )

    assert response.status_code == 200
    assert calls == [7]


def test_unavailable_report_metrics_are_displayed_without_fake_values(monkeypatch):
    data = report_data()
    data["expenses"]["category_totals"] = []
    data["expenses"]["monthly_totals"] = []
    data["goals"] = {"goal_count": 0, "goals": []}
    data["investments"]["stats"] = {
        "current_value": None,
        "total_invested": 0,
        "absolute_return": None,
        "return_percentage": None,
        "allocation": [],
    }
    data["financial_health"] = {"available": False, "score": None, "grade": "Insufficient Data", "components": {}}
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: data)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert b"Not available" in response.data
    assert b"No expense categories in this period." in response.data
    assert b"No monthly expense data available." in response.data
    assert b"No financial goals available." in response.data
    assert b"Historical portfolio performance is not available." in response.data


def test_existing_reports_json_behavior_remains_available(monkeypatch):
    data = report_data()
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: deepcopy(data))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports?format=json")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["expenses"]["category_totals"][0]["category"] == "Food"
