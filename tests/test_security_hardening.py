import csv
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

import app as application
import db


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_VARIABLES = (
    "FLASK_ENV",
    "APP_ENV",
    "ENVIRONMENT",
    "VERCEL_ENV",
    "ENV",
)


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Security Tester"


def clear_environment_mode(monkeypatch):
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def assert_security_headers(response):
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == (
        "camera=(), geolocation=(), microphone=()"
    )
    content_security_policy = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in content_security_policy
    assert "https://cdn.jsdelivr.net" in content_security_policy
    assert "'unsafe-inline'" in content_security_policy


def report_data():
    return {
        "date_range": {"start_date": None, "end_date": None},
        "expenses": {
            "expense_summary": {
                "total_expenses": 0.0,
                "transaction_count": 0,
                "average_expense": 0.0,
                "largest_expense": 0.0,
            },
            "category_totals": [],
            "monthly_totals": [],
        },
        "budgets": {
            "total_budget": 0.0,
            "total_spent": 0.0,
            "total_remaining": 0.0,
            "overall_utilization": None,
            "budget_count": 0,
            "budgets": [],
        },
        "investments": {
            "holding_count": 0,
            "holdings": [],
            "stats": {
                "total_invested": 0.0,
                "current_value": None,
                "absolute_return": None,
                "return_percentage": None,
            },
        },
        "goals": {"goal_count": 0, "goals": []},
        "financial_health": {"available": False},
        "unavailable_metrics": {},
    }


@pytest.fixture(autouse=True)
def clear_login_failures():
    application._login_failures.clear()
    yield
    application._login_failures.clear()


def test_csv_formula_leading_text_is_neutralized_without_touching_amounts(monkeypatch):
    rows = [
        {
            "date": "2026-08-01",
            "category": "=SUM(A1:A2)",
            "description": "+123",
            "payment_mode": "-123",
            "type": "@SUM(A1:A2)",
            "amount": Decimal("125.50"),
        }
    ]
    monkeypatch.setattr(application, "get_transactions", lambda user_id: rows)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses/export")
    parsed_rows = list(csv.reader(StringIO(response.get_data(as_text=True))))

    assert parsed_rows[1] == [
        "2026-08-01",
        "'=SUM(A1:A2)",
        "'+123",
        "'-123",
        "'@SUM(A1:A2)",
        "125.50",
    ]


def test_csv_normal_and_empty_fields_remain_parseable(monkeypatch):
    rows = [
        {
            "date": "2026-08-02",
            "category": "Food",
            "description": "Lunch, at cafe",
            "payment_mode": "UPI",
            "type": "Expense",
            "amount": "42.50",
        },
        {
            "date": None,
            "category": "",
            "description": None,
            "payment_mode": None,
            "type": "",
            "amount": Decimal("0"),
        },
    ]
    monkeypatch.setattr(application, "get_transactions", lambda user_id: rows)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses/export")
    parsed_rows = list(csv.reader(StringIO(response.get_data(as_text=True))))

    assert parsed_rows[1] == [
        "2026-08-02",
        "Food",
        "Lunch, at cafe",
        "UPI",
        "Expense",
        "42.50",
    ]
    assert parsed_rows[2] == ["", "", "", "", "", "0"]


def test_security_headers_apply_to_html_and_download_responses(monkeypatch):
    client = application.app.test_client()
    assert_security_headers(client.get("/login"))

    monkeypatch.setattr(application, "get_transactions", lambda user_id: [])
    monkeypatch.setattr(application, "build_reporting_data", lambda *args, **kwargs: report_data())
    set_session(client)

    responses = [
        client.get("/expenses/export"),
        client.get("/reports?format=json", headers={"Accept": "application/json"}),
        client.get("/reports/export/pdf"),
        client.get("/reports/export/excel"),
    ]
    for response in responses:
        assert response.status_code == 200
        assert_security_headers(response)


def test_session_cookie_flags_are_hardened_for_local_authenticated_sessions(monkeypatch):
    clear_environment_mode(monkeypatch)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setitem(application.app.config, "SESSION_COOKIE_SECURE", False)
    application._configure_security_settings()

    monkeypatch.setattr(
        application,
        "login_user",
        lambda email, password: (True, {"id": 7, "username": "Tester", "email": email}),
    )
    monkeypatch.setattr(application, "create_user_session", lambda *args: {"id": 1})
    response = application.app.test_client().post(
        "/login",
        data={"email": "tester@example.com", "password": "password"},
    )

    assert response.status_code == 302
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie


def test_session_cookie_secure_is_forced_in_production(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setitem(application.app.config, "SESSION_COOKIE_SECURE", False)
    application._configure_security_settings()

    assert application.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert application.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert application.app.config["SESSION_COOKIE_SECURE"] is True


def test_login_limits_repeated_failed_attempts_without_waiting(monkeypatch):
    calls = []

    def failed_login(email, password):
        calls.append((email, password))
        return False, None

    monkeypatch.setattr(application, "login_user", failed_login)
    client = application.app.test_client()

    responses = [
        client.post(
            "/login",
            data={"email": "attacker@example.com", "password": "wrong"},
        )
        for _ in range(application.LOGIN_MAX_FAILURES)
    ]
    blocked_response = client.post(
        "/login",
        data={"email": "attacker@example.com", "password": "wrong"},
    )

    assert all(response.status_code == 200 for response in responses)
    assert blocked_response.status_code == 429
    assert len(calls) == application.LOGIN_MAX_FAILURES


def test_successful_login_still_works_and_clears_failures(monkeypatch):
    outcomes = iter(
        [
            (False, None),
            (True, {"id": 7, "username": "Tester", "email": "tester@example.com"}),
        ]
    )
    monkeypatch.setattr(application, "login_user", lambda email, password: next(outcomes))
    monkeypatch.setattr(application, "create_user_session", lambda *args: {"id": 1})
    client = application.app.test_client()

    assert client.post(
        "/login",
        data={"email": "tester@example.com", "password": "wrong"},
    ).status_code == 200
    response = client.post(
        "/login",
        data={"email": "tester@example.com", "password": "correct"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    with client.session_transaction() as session:
        assert session["uid"] == 7
    assert application._login_failures == {}


def test_login_rate_limit_does_not_affect_unrelated_routes(monkeypatch):
    monkeypatch.setattr(application, "login_user", lambda email, password: (False, None))
    client = application.app.test_client()
    for _ in range(application.LOGIN_MAX_FAILURES):
        client.post("/login", data={"email": "attacker@example.com", "password": "wrong"})

    assert client.get("/login").status_code == 200
    assert client.get("/dashboard").status_code == 302
    assert client.get("/expenses/export").status_code == 302


def test_database_ssl_is_omitted_for_local_development(monkeypatch):
    clear_environment_mode(monkeypatch)
    monkeypatch.setattr(db.Config, "DB_SSLMODE", None)
    monkeypatch.setattr(db.Config, "DB_SSLROOTCERT", None)

    kwargs = db._connection_kwargs()

    assert "sslmode" not in kwargs
    assert "sslrootcert" not in kwargs


def test_database_ssl_requires_encryption_in_production(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(db.Config, "DB_SSLMODE", None)
    monkeypatch.setattr(db.Config, "DB_SSLROOTCERT", None)

    assert db._connection_kwargs()["sslmode"] == "require"


def test_database_ssl_rejects_unencrypted_production_modes(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(db.Config, "DB_SSLMODE", "prefer")

    with pytest.raises(RuntimeError, match="encrypted PostgreSQL"):
        db._connection_kwargs()


def test_database_ssl_honors_explicit_certificate_configuration(monkeypatch):
    clear_environment_mode(monkeypatch)
    monkeypatch.setattr(db.Config, "DB_SSLMODE", "verify-full")
    monkeypatch.setattr(db.Config, "DB_SSLROOTCERT", "/etc/ssl/finsight-ca.crt")

    kwargs = db._connection_kwargs()

    assert kwargs["sslmode"] == "verify-full"
    assert kwargs["sslrootcert"] == "/etc/ssl/finsight-ca.crt"


def test_invalid_database_ssl_mode_is_rejected(monkeypatch):
    monkeypatch.setattr(db.Config, "DB_SSLMODE", "unsafe-mode")

    with pytest.raises(RuntimeError, match="DB_SSLMODE"):
        db._connection_kwargs()


def test_known_debug_financial_output_is_removed():
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    health_source = (PROJECT_ROOT / "financial_health_service.py").read_text(encoding="utf-8")

    assert "DEBUG FINANCIAL HEALTH" not in app_source
    assert "DEBUG SPENDING RESULT" not in health_source
    assert "print(" not in app_source
    assert "print(" not in health_source
