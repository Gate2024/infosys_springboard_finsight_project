from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock

import app as application
from psycopg2 import OperationalError


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
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


def test_authenticated_reports_page_renders_real_report_data(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_reports_pdf_action_prints_embedded_report_without_preview_request(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    report_builder = Mock(return_value=report_data())
    monkeypatch.setattr(application, "build_reporting_data", report_builder)
    client = application.app.test_client()
    set_session(client)

    response = client.get(
        "/reports?start_date=2026-05-01&end_date=2026-05-31",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'type="button"' in body
    assert "data-report-print" in body
    assert "/reports/print-preview" not in body
    assert 'target="_blank"' not in body
    for section in (
        "Expense Summary",
        "Expense by Category",
        "Monthly Spending",
        "Budget Snapshot",
        "Investment Snapshot",
        "Goal Progress",
        "Financial Health",
        "Unavailable Metrics",
    ):
        assert section in body
    assert "May 1, 2026 - May 31, 2026" in body
    assert "preview-toolbar" not in body
    assert "Back to Reports" not in body
    assert "Print / Save as PDF" not in body
    assert "printReportButton" not in body
    assert "report-print.css" in body
    stylesheet = client.get("/static/css/report-print.css")
    assert stylesheet.status_code == 200
    stylesheet_body = stylesheet.get_data(as_text=True)
    assert "@media print" in stylesheet_body
    assert ".navbar" in stylesheet_body
    assert ".reports-page" in stylesheet_body
    assert ".report-print-document" in stylesheet_body
    assert "display: block !important" in stylesheet_body
    script = client.get("/static/js/reports.js")
    assert script.status_code == 200
    script_body = script.get_data(as_text=True)
    assert "window.print()" in script_body
    assert 'document.querySelector("[data-report-print]")' in script_body
    assert "printReportButton" not in script_body
    assert report_builder.call_count == 1


def test_reports_retry_once_after_transient_database_disconnect(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    report_builder = Mock(
        side_effect=[OperationalError("SSL connection has been closed unexpectedly"), report_data()]
    )
    connection_reset = Mock()
    monkeypatch.setattr(application, "build_reporting_data", report_builder)
    monkeypatch.setattr(application, "close_request_connection", connection_reset)
    monkeypatch.setattr(
        application, "get_user_preferences", lambda _user_id: application.PREFERENCE_DEFAULTS
    )
    monkeypatch.setattr(application, "get_notifications", lambda *args, **kwargs: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda _user_id: 0)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert report_builder.call_count == 2
    assert connection_reset.called


def test_removed_print_preview_route_is_not_available(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    report_builder = Mock(return_value=report_data())
    monkeypatch.setattr(application, "build_reporting_data", report_builder)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports/print-preview")

    assert response.status_code == 404
    report_builder.assert_not_called()


def test_reports_page_requires_authentication():
    response = application.app.test_client().get(
        "/reports", headers={"Accept": "text/html"}
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_reports_mobile_styles_constrain_controls_and_content():
    response = application.app.test_client().get("/static/css/reports.css")

    assert response.status_code == 200
    styles = response.get_data(as_text=True)
    assert ".reports-page, .reports-header" in styles
    assert "min-width: 0; max-width: 100%" in styles
    assert ".report-filter-panel { width: 100%" in styles
    assert ".report-date-form label, .report-date-form input, .report-date-form .btn" in styles
    assert ".reports-export-actions .btn { width: 100%; }" in styles


def test_reports_page_uses_session_user_not_client_user_id(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_unavailable_report_metrics_are_displayed_without_fake_values(monkeypatch, tracked_session_store):
    tracked_session_store(7)
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


def test_existing_reports_json_behavior_remains_available(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    data = report_data()
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: deepcopy(data))
    client = application.app.test_client()
    set_session(client)

    response = client.get("/reports?format=json")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["expenses"]["category_totals"][0]["category"] == "Food"
