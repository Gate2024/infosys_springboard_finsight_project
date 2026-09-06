from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import app as application
import report_service


class FakeCursor:
    def __init__(self, one_rows=None, all_rows=None):
        self.one_rows = list(one_rows or [])
        self.all_rows = list(all_rows or [])
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((query, params))

    def fetchone(self):
        return self.one_rows.pop(0)

    def fetchall(self):
        return self.all_rows.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_result = cursor

    def cursor(self):
        return self.cursor_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def run_expense_report(monkeypatch, summary, categories, monthly, user_id=7):
    cursor = FakeCursor([summary], [categories, monthly])
    connection = FakeConnection(cursor)

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(report_service, "get_connection", fake_connection)
    return report_service.get_expense_report(
        user_id, "2026-05-01", "2026-05-31"
    ), cursor


def test_valid_report_date_range_is_inclusive():
    assert report_service.parse_report_date_range("2026-05-01", "2026-05-31") == (
        date(2026, 5, 1),
        date(2026, 5, 31),
    )
    assert report_service.parse_report_date_range() == (None, None)


def test_invalid_report_date_format_is_rejected():
    try:
        report_service.parse_report_date_range("05/01/2026", "2026-05-31")
    except report_service.ReportValidationError as error:
        assert "YYYY-MM-DD" in str(error)
    else:
        raise AssertionError("Invalid date should be rejected")


def test_reversed_report_date_range_is_rejected():
    try:
        report_service.parse_report_date_range("2026-06-01", "2026-05-31")
    except report_service.ReportValidationError as error:
        assert "cannot be later" in str(error)
    else:
        raise AssertionError("Reversed date range should be rejected")


def test_partial_report_date_range_is_rejected():
    try:
        report_service.parse_report_date_range("2026-05-01", None)
    except report_service.ReportValidationError as error:
        assert "required together" in str(error)
    else:
        raise AssertionError("Partial date range should be rejected")


def test_expense_report_aggregates_total_and_categories(monkeypatch):
    result, cursor = run_expense_report(
        monkeypatch,
        {
            "transaction_count": 3,
            "total_expenses": Decimal("600.50"),
            "average_expense": Decimal("200.1667"),
            "largest_expense": Decimal("300.00"),
            "month_expenses": 1,
            "month_spent": Decimal("100.00"),
        },
        [{"category": "Food", "amount": Decimal("400.50")}],
        [{"month": "2026-05", "amount": Decimal("600.50")}],
    )

    assert result["expense_summary"]["total_expenses"] == 600.5
    assert result["expense_summary"]["transaction_count"] == 3
    assert result["category_totals"] == [{"category": "Food", "amount": 400.5}]
    assert result["monthly_totals"] == [{"month": "2026-05", "amount": 600.5}]
    assert cursor.executions[0][1] == (7, date(2026, 5, 1), date(2026, 5, 31))


def test_expense_report_is_expense_only_and_user_scoped(monkeypatch):
    _, cursor = run_expense_report(
        monkeypatch,
        {"transaction_count": 0},
        [],
        [],
        user_id=42,
    )

    for query, params in cursor.executions:
        assert "type = 'Expense'" in query
        assert "user_id = %s" in query
        assert params == (42, date(2026, 5, 1), date(2026, 5, 31))


def test_empty_expense_report_is_safe(monkeypatch):
    result, _ = run_expense_report(
        monkeypatch,
        {"transaction_count": 0},
        [],
        [],
    )

    assert result["expense_summary"] == {
        "total_expenses": 0.0,
        "transaction_count": 0,
        "average_expense": 0.0,
        "largest_expense": 0.0,
        "month_expenses": 0,
        "month_spent": 0.0,
    }
    assert result["category_totals"] == []
    assert result["monthly_totals"] == []


def test_budget_snapshot_reuses_scoped_stored_data(monkeypatch):
    calls = []
    monkeypatch.setattr(
        report_service,
        "get_summary_stats",
        lambda user_id: (calls.append(("stats", user_id)) or {
            "total_allocated": Decimal("1000"),
            "total_spent": Decimal("750"),
            "total_remaining": Decimal("250"),
            "total_budgets": 2,
        }),
    )
    monkeypatch.setattr(
        report_service,
        "filter_budgets",
        lambda user_id: (calls.append(("budgets", user_id)) or [
            {
                "budget_name": "Food",
                "category": "Food",
                "budget_amount": 1000,
                "spent_amount": 750,
                "remaining_amount": 250,
                "status": "Active",
                "start_date": "2026-05-01",
                "end_date": "2026-05-31",
            }
        ]),
    )

    result = report_service.get_budget_snapshot(7)

    assert result["scope"] == "current"
    assert result["date_range_applied"] is False
    assert result["overall_utilization"] == 75.0
    assert result["budget_count"] == 2
    assert calls == [("stats", 7), ("budgets", 7)]


def test_zero_budget_snapshot_has_no_utilization(monkeypatch):
    monkeypatch.setattr(
        report_service,
        "get_summary_stats",
        lambda user_id: {
            "total_allocated": 0,
            "total_spent": 0,
            "total_remaining": 0,
            "total_budgets": 0,
        },
    )
    monkeypatch.setattr(report_service, "filter_budgets", lambda user_id: [])

    assert report_service.get_budget_snapshot(7)["overall_utilization"] is None


def test_investment_snapshot_reuses_current_service_values():
    class FakeInvestmentService:
        def list_for_user(self, user_id):
            assert user_id == 7
            return (
                [{"asset_name": "Fund", "current_value": None}],
                {
                    "total_invested": Decimal("100"),
                    "current_value": None,
                    "absolute_return": None,
                    "return_percentage": None,
                },
            )

    result = report_service.get_investment_snapshot(7, FakeInvestmentService())

    assert result["holding_count"] == 1
    assert result["holdings"][0]["current_value"] is None
    assert result["stats"]["return_percentage"] is None
    assert result["date_range_applied"] is False


def test_goal_snapshot_reuses_current_progress_values():
    class FakeGoalService:
        def list_for_user(self, user_id):
            assert user_id == 7
            return [
                {
                    "goal_name": "Emergency Fund",
                    "target_amount": Decimal("1000"),
                    "current_amount": Decimal("250"),
                    "progress_percentage": Decimal("25"),
                    "remaining_amount": Decimal("750"),
                    "status": "Active",
                }
            ]

    result = report_service.get_goal_snapshot(7, FakeGoalService())

    assert result["goal_count"] == 1
    assert result["goals"][0]["progress_percentage"] == 25.0
    assert result["goals"][0]["remaining_amount"] == 750.0


def test_financial_health_snapshot_reuses_existing_calculation():
    result = report_service.get_financial_health_snapshot(
        {
            "total_budget": 1000,
            "total_spent": 500,
        },
        {
            "total_expenses": 500,
            "transaction_count": 5,
            "average_expense": 100,
            "largest_expense": 150,
            "month_expenses": 2,
            "month_spent": 200,
        },
        {
            "goals": [
                {"current_amount": 250, "target_amount": 1000},
            ]
        },
        {"stats": {"return_percentage": None}},
    )

    assert result["available"] is True
    assert result["components"]["budget"]["score"] == 35.0
    assert result["components"]["goals"]["percentage"] == 25.0


def test_unavailable_metrics_are_explicit_and_not_fabricated():
    metrics = report_service.unavailable_metrics()

    assert metrics
    assert all(item["available"] is False for item in metrics.values())
    assert all(item["value"] is None for item in metrics.values())
    assert "income" in metrics["total_income"]["reason"].lower()
    assert "savings" in metrics["total_savings"]["reason"].lower()
    assert "net worth" in metrics["net_worth"]["reason"].lower()


def test_reports_route_requires_authentication():
    client = application.app.test_client()

    response = client.get("/reports")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_reports_route_uses_session_user_not_client_user_id(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    calls = []

    def fake_build(user_id, start_date, end_date, *, investment_service, goal_service):
        calls.append((user_id, start_date, end_date))
        return {"date_range": {"start_date": start_date, "end_date": end_date}}

    monkeypatch.setattr(application, "build_reporting_data", fake_build)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Report Tester"

    response = client.get(
        "/reports?user_id=99&start_date=2026-05-01&end_date=2026-05-31"
    )

    assert response.status_code == 200
    assert calls == [(7, "2026-05-01", "2026-05-31")]


def test_reports_route_rejects_invalid_dates(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Report Tester"

    response = client.get("/reports?start_date=invalid&end_date=2026-05-31")

    assert response.status_code == 400
    assert b"YYYY-MM-DD" in response.data


def test_reporting_queries_do_not_mutate_database(monkeypatch):
    result, cursor = run_expense_report(
        monkeypatch,
        {"transaction_count": 0},
        [],
        [],
    )

    assert result["expense_summary"]["transaction_count"] == 0
    assert all(
        command not in query.upper()
        for query, _ in cursor.executions
        for command in ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP")
    )


def test_existing_expense_csv_export_still_works(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    monkeypatch.setattr(
        application,
        "get_transactions",
        lambda user_id: [
            {
                "date": "2026-05-01",
                "category": "Food",
                "description": "Lunch",
                "payment_mode": "UPI",
                "type": "Expense",
                "amount": "100.00",
            }
        ],
    )
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Report Tester"

    response = client.get("/expenses/export")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"Date,Category,Description,Payment Mode,Type,Amount" in response.data
    assert b"Lunch" in response.data
