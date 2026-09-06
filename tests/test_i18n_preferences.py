import pytest
from pathlib import Path

import app as application
import db as database
from i18n import TRANSLATIONS, format_currency, translate


def set_session(client, user_id=7):
    with client.session_transaction() as session:
        session["uid"] = user_id
        session["auth_session_token"] = f"fixture-session-{session['uid']}"
        session["username"] = "Preference Owner"
        session["email"] = f"user{user_id}@example.com"


@pytest.mark.parametrize(
    ("currency", "expected"),
    [
        ("USD", "$1,000.00"),
        ("INR", "₹1,000.00"),
        ("EUR", "€1,000.00"),
        ("JPY", "¥1,000"),
        ("GBP", "£1,000.00"),
        ("CAD", "CA$1,000.00"),
        ("AUD", "A$1,000.00"),
        ("CNY", "¥1,000.00"),
    ],
)
def test_format_currency_uses_selected_display_currency(currency, expected):
    assert format_currency(1000, currency) == expected


@pytest.mark.parametrize(
    ("currency", "expected"),
    [
        ("USD", "+$20.75"),
        ("INR", "+₹20.75"),
        ("EUR", "+€20.75"),
        ("JPY", "+¥21"),
        ("GBP", "+£20.75"),
        ("CAD", "+CA$20.75"),
        ("AUD", "+A$20.75"),
        ("CNY", "+¥20.75"),
    ],
)
def test_signed_currency_format_is_consistent_and_keeps_sign_before_symbol(currency, expected):
    assert format_currency("20.75", currency, show_sign=True) == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "Expenses"),
        ("hi", "खर्च"),
        ("ja", "支出"),
        ("de", "Ausgaben"),
        ("fr", "Dépenses"),
        ("es", "Gastos"),
    ],
)
def test_representative_application_text_is_available_in_each_supported_language(language, expected):
    assert translate("Expenses", language) == expected


def test_user_content_matching_translation_key_is_not_translated():
    template = Path("templates/expenses/dashboard.html").read_text(encoding="utf-8")
    javascript = Path("static/js/main.js").read_text(encoding="utf-8")

    assert "{{ expense.description or t(\"Untitled expense\") }}" in template
    assert "TreeWalker" not in javascript
    assert translate("Expenses", "hi") == "खर्च"


def test_excel_currency_formats_cover_all_supported_display_currencies():
    expected_decimals = {
        "USD": ".00",
        "INR": ".00",
        "EUR": ".00",
        "JPY": "#",
        "GBP": ".00",
        "CAD": ".00",
        "AUD": ".00",
        "CNY": ".00",
    }
    for currency, decimal_marker in expected_decimals.items():
        number_format = application._excel_currency_format(currency)
        assert currency not in number_format
        if currency == "JPY":
            assert number_format.endswith("#,##0")
        else:
            assert number_format.endswith("#,##0.00")


def test_pdf_uses_registered_unicode_font_for_display_currency():
    assert application.PDF_FONT != "Helvetica"


def test_authenticated_header_uses_user_language_and_currency(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    preferences = {
        "currency": "INR",
        "language": "hi",
        "budget_overspending_alerts": False,
        "weekly_savings_digest_enabled": False,
        "sip_due_date_reminders_enabled": False,
        "bill_due_date_reminders_enabled": False,
    }
    monkeypatch.setattr(application, "get_user_preferences", lambda _user_id: preferences)
    monkeypatch.setattr(application, "get_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda _user_id: 0)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/notifications")

    assert response.status_code == 200
    assert b'<html lang="hi" data-language="hi"' in response.data
    assert "डैशबोर्ड".encode() in response.data
    assert b'"currency": "INR"' in response.data
    assert b'"language": "hi"' in response.data


def test_user_preferences_are_scoped_to_the_authenticated_session(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    tracked_session_store(8)
    preferences = {
        7: {"currency": "EUR", "language": "de"},
        8: {"currency": "JPY", "language": "ja"},
    }
    monkeypatch.setattr(
        application,
        "get_user_preferences",
        lambda user_id: preferences[user_id],
    )
    monkeypatch.setattr(application, "get_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda _user_id: 0)

    first_client = application.app.test_client()
    second_client = application.app.test_client()
    set_session(first_client, 7)
    set_session(second_client, 8)

    first = first_client.get("/notifications")
    second = second_client.get("/notifications")

    assert b'"currency": "EUR"' in first.data
    assert b'"currency": "JPY"' in second.data
    assert b'"currency": "JPY"' not in first.data
    assert b'"currency": "EUR"' not in second.data


def test_marathi_is_available_in_preferences_and_persists(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    state = {
        "currency": "USD",
        "language": "en",
        "theme": "light",
        "budget_overspending_alerts": False,
        "weekly_savings_digest_enabled": False,
        "sip_due_date_reminders_enabled": False,
        "bill_due_date_reminders_enabled": False,
    }
    monkeypatch.setattr(application, "list_preference_currencies", lambda: [
        {"code": "USD", "display_name": "US Dollar", "symbol": "$"},
    ])
    monkeypatch.setattr(application, "list_preference_languages", lambda: [
        {"code": "en", "display_name": "English"},
    ])
    monkeypatch.setattr(application, "ensure_user_preferences", lambda _user_id: dict(state))
    monkeypatch.setattr(application, "get_user_preferences", lambda _user_id: dict(state))

    def update(_user_id, values):
        state.update(values)
        return dict(state)

    monkeypatch.setattr(application, "update_user_preferences", update)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/profile/preferences")
    assert response.status_code == 200
    assert b'value="mr"' in response.data
    assert b">Marathi</option>" in response.data

    with client.session_transaction() as session:
        token = session["preferences_csrf_token"]
    response = client.post(
        "/profile/preferences",
        data={
            "_preferences_csrf_token": token,
            "theme": "light",
            "currency": "USD",
            "language": "mr",
        },
    )
    assert response.status_code == 302
    assert state["language"] == "mr"


def test_marathi_renders_application_ui_without_translating_user_content(monkeypatch, tracked_session_store):
    tracked_session_store(7)
    preferences = {
        "currency": "INR",
        "language": "mr",
        "theme": "light",
        "budget_overspending_alerts": False,
        "weekly_savings_digest_enabled": False,
        "sip_due_date_reminders_enabled": False,
        "bill_due_date_reminders_enabled": False,
    }
    user_expenses = [
        {
            "id": 41,
            "description": "Expenses",
            "category": "Score",
            "payment_mode": "Cash",
            "amount": 125.50,
            "date": "2026-09-05",
        },
        {
            "id": 42,
            "description": "<script>alert(1)</script>",
            "category": "Personal Care",
            "payment_mode": "Card",
            "amount": 50.00,
            "date": "2026-09-04",
        },
    ]
    expense_summary = {
        "total_spent": 175.50,
        "month_spent": 175.50,
        "total_expenses": 2,
        "average_expense": 87.75,
        "largest_expense": 125.50,
        "month_expenses": 2,
        "top_category": "Score",
    }
    monkeypatch.setattr(application, "get_user_preferences", lambda _user_id: preferences)
    monkeypatch.setattr(application, "get_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(application, "get_unread_notification_count", lambda _user_id: 0)
    monkeypatch.setattr(
        database,
        "get_transactions",
        lambda _user_id, **_kwargs: user_expenses,
    )
    monkeypatch.setattr(database, "get_expense_summary", lambda _user_id: expense_summary)
    client = application.app.test_client()
    set_session(client)

    response = client.get("/expenses")

    assert response.status_code == 200
    assert b'<html lang="mr" data-language="mr"' in response.data
    assert "डॅशबोर्ड".encode() in response.data
    assert "खर्च".encode() in response.data
    assert b"<strong>Expenses</strong>" in response.data
    assert b"Score" in response.data
    assert "स्कोअर".encode() not in response.data
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data
    assert TRANSLATIONS["mr"]["Expenses"] == "खर्च"


def test_marathi_catalog_covers_all_explicit_application_translation_keys():
    import re

    keys = set()
    for path in Path("templates").rglob("*.html"):
        keys.update(
            re.findall(
                r'\bt\(\s*["\x27]([^"\x27]+)["\x27]',
                path.read_text(encoding="utf-8"),
            )
        )
    for path in Path("static/js").rglob("*.js"):
        keys.update(
            re.findall(
                r'\b(?:finSightTranslate|tr)\(\s*["\x27]([^"\x27]+)["\x27]',
                path.read_text(encoding="utf-8"),
            )
        )

    assert keys <= set(TRANSLATIONS["mr"])
