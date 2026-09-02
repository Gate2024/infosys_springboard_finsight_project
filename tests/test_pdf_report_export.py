from copy import deepcopy

import pytest

import app as application


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "PDF Tester"


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
        "budgets": {
            "total_budget": 1000,
            "total_spent": 750,
            "total_remaining": 250,
            "overall_utilization": 75,
            "budget_count": 1,
            "budgets": [
                {
                    "budget_name": "Food Budget",
                    "category": "Food",
                    "budget_amount": 1000,
                    "spent_amount": 750,
                    "remaining_amount": 250,
                    "status": "Active",
                }
            ],
        },
        "investments": {
            "holding_count": 1,
            "stats": {
                "total_invested": 1000,
                "current_value": 1200,
                "absolute_return": 200,
                "return_percentage": 20,
                "allocation": [{"asset_type": "Stocks", "percentage": 100}],
            },
        },
        "goals": {
            "goal_count": 1,
            "goals": [
                {
                    "goal_name": "Emergency Fund",
                    "target_amount": 1000,
                    "current_amount": 250,
                    "progress_percentage": 25,
                    "remaining_amount": 750,
                    "status": "Active",
                    "target_date": "2030-01-01",
                }
            ],
        },
        "financial_health": {
            "available": True,
            "score": 79,
            "grade": "Good",
            "coverage": 80,
            "earned_points": 63,
            "available_weight": 80,
            "components": {
                "budget": {
                    "available": True,
                    "score": 35,
                    "message": "Budget usage is healthy.",
                }
            },
        },
        "unavailable_metrics": {
            "total_income": {
                "available": False,
                "value": None,
                "reason": "No reliable actual income source exists.",
            },
            "total_savings": {
                "available": False,
                "value": None,
                "reason": "No actual savings balance exists.",
            },
        },
    }


def test_authenticated_user_can_download_pdf_with_report_sections(monkeypatch):
    data = report_data()
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: deepcopy(data))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports/export/pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=\"finsight_financial_report.pdf\""
    )
    assert response.data.startswith(b"%PDF")
    for text in (
        b"FinSight",
        b"Financial Report",
        b"Expense Summary",
        b"Food Budget",
        b"Stocks",
        b"Emergency Fund",
        b"Financial Health",
        b"Total Income",
    ):
        assert text in response.data
    assert b"85000" not in response.data


def test_pdf_export_requires_authentication():
    response = application.app.test_client().get("/reports/export/pdf")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_pdf_export_uses_session_user_and_preserves_date_range(monkeypatch):
    calls = []

    def fake_build(user_id, start_date, end_date, *, investment_service, goal_service):
        calls.append((user_id, start_date, end_date))
        return report_data()

    monkeypatch.setattr(application, "build_reporting_data", fake_build)
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get(
        "/reports/export/pdf?user_id=99&start_date=2026-01-01&end_date=2026-03-31"
    )

    assert response.status_code == 200
    assert calls == [(7, "2026-01-01", "2026-03-31")]


@pytest.mark.parametrize(
    "query_string",
    [
        {"start_date": "2026-01-01"},
        {"start_date": "invalid", "end_date": "2026-03-31"},
        {"start_date": "2026-04-01", "end_date": "2026-03-31"},
    ],
)
def test_pdf_export_rejects_invalid_date_ranges(query_string):
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports/export/pdf", query_string=query_string)

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["error"]


def test_empty_expense_data_still_produces_a_valid_pdf(monkeypatch):
    data = report_data()
    data["date_range"] = {"start_date": None, "end_date": None}
    data["expenses"]["expense_summary"] = {
        "total_expenses": 0,
        "transaction_count": 0,
        "average_expense": 0,
        "largest_expense": 0,
        "month_expenses": 0,
        "month_spent": 0,
    }
    data["expenses"]["category_totals"] = []
    data["expenses"]["monthly_totals"] = []
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: data)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports/export/pdf")

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
    assert b"All Available Expense History" in response.data
    assert b"No expense data available for the selected period." in response.data
    assert b"No monthly expense data available." in response.data


def test_pdf_export_does_not_mutate_report_data(monkeypatch):
    data = report_data()
    original = deepcopy(data)
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: data)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports/export/pdf")

    assert response.status_code == 200
    assert data == original


def test_existing_reports_json_behavior_remains_available(monkeypatch):
    data = report_data()
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: deepcopy(data))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports?format=json")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["expenses"]["category_totals"][0]["category"] == "Food"
