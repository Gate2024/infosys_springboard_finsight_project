from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest
from werkzeug.security import check_password_hash

import app as application
import db
import email_service as email_module
from tests.auth_helpers import auth_form


def registration_data(client, **overrides):
    data = auth_form(
        client,
        username="New Owner",
        email="new-owner@example.com",
        mobile_number="9876543210",
        password="correct-password",
        confirm_password="correct-password",
    )
    data.update(overrides)
    return data


@pytest.fixture
def registration_store(monkeypatch):
    calls = {
        "register": Mock(return_value=(True, {"id": 9, "email": "new-owner@example.com"})),
    }
    monkeypatch.setattr(application, "register_user", calls["register"])
    return calls


def test_registration_creates_account_without_email_or_pending_registration(registration_store):
    client = application.app.test_client()
    response = client.post("/register", data=registration_data(client))

    assert response.status_code == 200
    assert b"Account Created Successfully" in response.data
    registration_store["register"].assert_called_once_with(
        "New Owner", "new-owner@example.com", "correct-password", "9876543210"
    )


@pytest.mark.parametrize(
    "field_data, expected",
    [
        ({"mobile_number": ""}, b"All fields are required."),
        ({"confirm_password": "different"}, b"Passwords do not match."),
        ({"password": "short", "confirm_password": "short"}, b"at least 8 characters"),
    ],
)
def test_registration_validation(field_data, expected, registration_store):
    client = application.app.test_client()
    response = client.post("/register", data=registration_data(client, **field_data))

    assert response.status_code == 200
    assert expected in response.data
    registration_store["register"].assert_not_called()


def test_registration_requires_auth_csrf(registration_store):
    client = application.app.test_client()
    data = registration_data(client)
    data.pop("_auth_csrf_token")

    response = client.post("/register", data=data)

    assert response.status_code == 400
    registration_store["register"].assert_not_called()


def test_registration_otp_routes_are_removed():
    client = application.app.test_client()

    assert client.get("/verify-registration-otp").status_code == 404
    assert client.post("/resend-registration-otp", data={}).status_code == 404


def test_register_user_hashes_password_and_stores_mobile(monkeypatch):
    cursor = Mock()
    cursor.fetchone.side_effect = [None, {"id": 1, "username": "New Owner", "email": "new-owner@example.com"}]

    @contextmanager
    def cursor_context():
        yield cursor

    connection = Mock()
    connection.cursor = cursor_context

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(db, "get_connection", connect)
    success, user = db.register_user(
        "New Owner", "NEW-OWNER@example.com", "correct-password", "9876543210"
    )

    assert success is True
    assert user["email"] == "new-owner@example.com"
    insert_params = cursor.execute.call_args_list[1].args[1]
    assert insert_params[2] == "9876543210"
    assert insert_params[3] != "correct-password"
    assert check_password_hash(insert_params[3], "correct-password")


def test_register_user_rejects_duplicate_email(monkeypatch):
    cursor = Mock()
    cursor.fetchone.return_value = {"email": "existing@example.com"}

    @contextmanager
    def cursor_context():
        yield cursor

    connection = Mock()
    connection.cursor = cursor_context

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(db, "get_connection", connect)
    success, message = db.register_user(
        "New Owner", "existing@example.com", "correct-password", "9876543210"
    )

    assert (success, message) == (False, "Email already exists.")
    assert cursor.execute.call_count == 1


def test_phase_2a_migration_adds_active_email_uniqueness_and_resend_limit():
    migration = Path("database/migrations/011_harden_pending_registration_challenges.sql").read_text()
    upper_migration = migration.upper()

    assert "ADD COLUMN IF NOT EXISTS RESEND_COUNT" in upper_migration
    assert "CREATE UNIQUE INDEX IF NOT EXISTS UQ_PENDING_REGISTRATIONS_ACTIVE_EMAIL" in upper_migration
    assert "WHERE CONSUMED_AT IS NULL" in upper_migration
    assert "DROP TABLE" not in upper_migration
    assert "DELETE FROM" not in upper_migration


def test_phase_2d_display_name_migration_is_additive():
    migration = Path("database/migrations/014_add_user_display_name.sql").read_text()
    upper_migration = migration.upper()

    assert "ALTER TABLE USERS" in upper_migration
    assert "ADD COLUMN IF NOT EXISTS DISPLAY_NAME VARCHAR(150)" in upper_migration
    assert "DROP TABLE" not in upper_migration
    assert "DELETE FROM" not in upper_migration


def test_phase_2d_auth_strings_are_available_in_all_languages():
    required = {
        "Account Created Successfully",
        "Your account has been successfully created.",
        "You can now sign in to FinSight.",
        "Go to Login",
        "Resend OTP",
        "Resend OTP in {seconds}s",
        "Verification Failed",
        "Dismiss",
        "Password must contain at least 8 characters.",
    }
    for language in ("en", "hi", "ja", "de", "fr", "es", "mr"):
        assert required <= application.TRANSLATIONS[language].keys()
        assert "{seconds}" in application.TRANSLATIONS[language][
            "Resend OTP in {seconds}s"
        ]


def test_production_smtp_with_credentials_requires_tls(monkeypatch):
    monkeypatch.setattr(email_module, "_is_production_environment", lambda: True)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    with pytest.raises(email_module.EmailConfigurationError):
        email_module.EmailService._smtp_transport()
