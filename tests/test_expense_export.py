import csv
from copy import deepcopy
from io import StringIO

import app as application
import db


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["username"] = "Expense Tester"


def test_authenticated_user_can_export_expenses(monkeypatch):
    rows = [
        {
            "date": "2026-08-01",
            "category": "Food",
            "description": "Lunch",
            "payment_mode": "UPI",
            "type": "Expense",
            "amount": "250.00",
        },
        {
            "date": "2026-08-02",
            "category": "Travel",
            "description": "Cab",
            "payment_mode": "Cash",
            "type": "Expense",
            "amount": "400.00",
        },
    ]
    calls = []

    def fake_get_transactions(user_id):
        calls.append(user_id)
        return deepcopy(rows)

    monkeypatch.setattr(application, "get_transactions", fake_get_transactions)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses/export")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"] == (
        "attachment; filename=finsight_expenses.csv"
    )
    assert calls == [7]
    exported_rows = list(csv.DictReader(StringIO(response.get_data(as_text=True))))
    assert exported_rows == [
        {
            "Date": "2026-08-01",
            "Category": "Food",
            "Description": "Lunch",
            "Payment Mode": "UPI",
            "Type": "Expense",
            "Amount": "250.00",
        },
        {
            "Date": "2026-08-02",
            "Category": "Travel",
            "Description": "Cab",
            "Payment Mode": "Cash",
            "Type": "Expense",
            "Amount": "400.00",
        },
    ]


def test_export_is_empty_but_valid_for_user_with_no_expenses(monkeypatch):
    monkeypatch.setattr(application, "get_transactions", lambda user_id: [])
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses/export")

    assert response.status_code == 200
    assert list(csv.reader(StringIO(response.get_data(as_text=True)))) == [
        ["Date", "Category", "Description", "Payment Mode", "Type", "Amount"]
    ]


def test_export_scope_uses_session_user_not_query_parameter(monkeypatch):
    rows_by_user = {
        7: [
            {
                "date": "2026-08-03",
                "category": "Bills",
                "description": "Electricity",
                "payment_mode": "Bank",
                "type": "Expense",
                "amount": "1200.00",
            }
        ],
        99: [
            {
                "date": "2026-08-03",
                "category": "Private",
                "description": "Other user's expense",
                "payment_mode": "Card",
                "type": "Expense",
                "amount": "9999.00",
            }
        ],
    }
    calls = []

    def fake_get_transactions(user_id):
        calls.append(user_id)
        return rows_by_user.get(user_id, [])

    monkeypatch.setattr(application, "get_transactions", fake_get_transactions)
    client = application.app.test_client()
    set_session(client, user_id=7)

    response = client.get("/expenses/export?user_id=99")

    assert response.status_code == 200
    assert calls == [7]
    assert "99" not in response.get_data(as_text=True)
    assert "Electricity" in response.get_data(as_text=True)
    assert "Other user's expense" not in response.get_data(as_text=True)


def test_export_does_not_modify_source_rows(monkeypatch):
    rows = [
        {
            "date": "2026-08-04",
            "category": "Health",
            "description": "Medicine",
            "payment_mode": "Card",
            "type": "Expense",
            "amount": "80.00",
        }
    ]
    original_rows = deepcopy(rows)
    monkeypatch.setattr(application, "get_transactions", lambda user_id: rows)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses/export")

    assert response.status_code == 200
    assert rows == original_rows


def test_export_requires_authentication(monkeypatch):
    calls = []
    monkeypatch.setattr(
        application,
        "get_transactions",
        lambda user_id: calls.append(user_id),
    )
    client = application.app.test_client()

    response = client.get("/expenses/export")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert calls == []


def test_expenses_page_includes_export_action(monkeypatch):
    monkeypatch.setattr(db, "get_transactions", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        db,
        "get_expense_summary",
        lambda user_id: {
            "total_spent": 0,
            "month_spent": 0,
            "total_expenses": 0,
            "average_expense": 0,
            "top_category": "None",
            "month_expenses": 0,
            "largest_expense": 0,
        },
    )
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses")

    assert response.status_code == 200
    assert 'href="/expenses/export"' in response.get_data(as_text=True)


def test_existing_expense_crud_routes_remain_registered():
    routes = {rule.rule for rule in application.app.url_map.iter_rules()}

    assert "/expense/create" in routes
    assert "/expense/edit/<int:transaction_id>" in routes
    assert "/expense/delete/<int:transaction_id>" in routes
