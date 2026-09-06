from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

import app as application
import db
import email_service as email_module
from tests.auth_helpers import auth_form


class PendingRegistrationDatabase:
    """Small transactional double used while executing the real db helpers."""

    def __init__(self):
        self.pending = {}
        self.users = {}
        self.next_id = 1
        self.now = datetime.now(timezone.utc)
        self.result = None

    @contextmanager
    def cursor(self):
        yield self

    @contextmanager
    def connect(self):
        yield self

    def execute(self, query, params=()):
        normalized = " ".join(query.split()).lower()
        self.result = None
        if normalized.startswith("select 1 from users"):
            email = params[0]
            self.result = (1,) if any(
                row["email"].lower() == email.lower()
                for row in self.users.values()
            ) else None
        elif normalized.startswith("update pending_registrations set consumed_at"):
            email = params[0].lower()
            for row in self.pending.values():
                if row["email"].lower() == email and row["consumed_at"] is None:
                    row["consumed_at"] = self.now
        elif normalized.startswith("insert into pending_registrations"):
            full_name, email, mobile, password_hash, otp_hash, expires_at = params
            if any(
                row["email"].lower() == email.lower() and row["consumed_at"] is None
                for row in self.pending.values()
            ):
                return
            pending_id = self.next_id
            self.next_id += 1
            self.pending[pending_id] = {
                "id": pending_id,
                "full_name": full_name,
                "email": email,
                "mobile_number": mobile,
                "password_hash": password_hash,
                "otp_hash": otp_hash,
                "otp_expires_at": expires_at,
                "otp_attempts": 0,
                "last_sent_at": self.now,
                "resend_count": 0,
                "created_at": self.now,
                "verified_at": None,
                "consumed_at": None,
            }
            self.result = {"id": pending_id}
        elif normalized.startswith("select id, full_name, email, mobile_number"):
            pending_id = params[0]
            row = self.pending.get(pending_id)
            if row and row["consumed_at"] is None:
                self.result = dict(row)
        elif normalized.startswith("select resend_count"):
            row = self.pending.get(params[0])
            if row and row["consumed_at"] is None:
                self.result = {
                    "resend_count": row["resend_count"],
                    "last_sent_at": row["last_sent_at"],
                    "can_resend": row["resend_count"] < 5
                    and row["last_sent_at"] <= self.now - timedelta(seconds=60),
                }
        elif normalized.startswith("update pending_registrations set otp_hash"):
            otp_hash, expires_at, pending_id = params
            row = self.pending.get(pending_id)
            if (
                row
                and row["consumed_at"] is None
                and row["resend_count"] < 5
                and row["last_sent_at"] <= self.now - timedelta(seconds=60)
            ):
                row.update(
                    otp_hash=otp_hash,
                    otp_expires_at=expires_at,
                    otp_attempts=0,
                    last_sent_at=self.now,
                    resend_count=row["resend_count"] + 1,
                )
                self.result = {"id": pending_id, "email": row["email"]}
        elif normalized.startswith("update pending_registrations set otp_attempts"):
            self.pending[params[0]]["otp_attempts"] += 1
        elif normalized.startswith("insert into users"):
            username, email, mobile, password_hash, display_name = params
            if any(
                row["email"].lower() == email.lower()
                or row["username"].lower() == username.lower()
                for row in self.users.values()
            ):
                return
            user_id = len(self.users) + 1
            self.users[user_id] = {
                "id": user_id,
                "username": username,
                "email": email,
                "mobile_number": mobile,
                "password_hash": password_hash,
                "display_name": display_name,
            }
            self.result = {
                "id": user_id,
                "username": display_name,
                "email": email,
            }
        elif normalized.startswith("update pending_registrations set verified_at"):
            row = self.pending[params[0]]
            row["verified_at"] = self.now
            row["consumed_at"] = self.now

    def fetchone(self):
        return self.result


@pytest.fixture
def real_pending_db(monkeypatch):
    database = PendingRegistrationDatabase()
    monkeypatch.setattr(db, "get_connection", database.connect)
    monkeypatch.setattr(db.Config, "SECRET_KEY", "test-registration-pepper")
    return database


def create_real_pending(database, email="new-owner@example.com", otp="123456", expires=None):
    return db.create_pending_registration(
        "New Owner",
        email,
        "9876543210",
        "werkzeug-hashed-password",
        db.registration_otp_digest(otp),
        expires or database.now + timedelta(minutes=10),
    )["id"]


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
    pending = {"id": 41, "email": "new-owner@example.com"}
    calls = {
        "create": Mock(return_value=pending),
        "send": Mock(),
        "get": Mock(return_value=pending),
        "resend_status": Mock(return_value={"resend_count": 0, "can_resend": True}),
        "replace": Mock(return_value=pending),
        "complete": Mock(return_value=(True, {"id": 9, "username": "New Owner", "email": pending["email"]})),
    }
    monkeypatch.setattr(application, "create_pending_registration", calls["create"])
    monkeypatch.setattr(application.email_service, "send_registration_otp", calls["send"])
    monkeypatch.setattr(application, "get_pending_registration", calls["get"])
    monkeypatch.setattr(application, "get_registration_resend_status", calls["resend_status"])
    monkeypatch.setattr(application, "replace_pending_registration_otp", calls["replace"])
    monkeypatch.setattr(application, "complete_pending_registration", calls["complete"])
    return calls


def pending_client():
    return application.app.test_client()


def set_pending_session(client, pending_id=41):
    with client.session_transaction() as session:
        session["pending_registration_id"] = pending_id


def test_registration_sends_otp_without_creating_final_account(registration_store):
    client = pending_client()
    response = client.post("/register", data=registration_data(client))

    assert response.status_code == 200
    assert b"verification code" in response.data
    registration_store["create"].assert_called_once()
    registration_store["send"].assert_called_once()
    password_hash = registration_store["create"].call_args.args[3]
    otp_hash = registration_store["create"].call_args.args[4]
    sent_otp = registration_store["send"].call_args.args[1]
    assert password_hash != "correct-password"
    assert len(otp_hash) == 64
    assert otp_hash != sent_otp
    assert sent_otp.isdigit() and len(sent_otp) == 6

    with client.session_transaction() as session:
        assert session["pending_registration_id"] == 41


def test_registration_otp_uses_server_derived_resend_countdown(registration_store):
    registration_store["resend_status"].return_value = {
        "resend_count": 0,
        "can_resend": False,
        "remaining_seconds": 37,
    }
    client = pending_client()

    response = client.post("/register", data=registration_data(client))

    assert response.status_code == 200
    assert b'data-otp-remaining-seconds="37"' in response.data
    assert b"Resend OTP in 37s" in response.data
    assert b'data-otp-resend-eligible="true"' in response.data
    assert b'data-otp-resend' in response.data


@pytest.mark.parametrize(
    "field_data, expected",
    [
        ({"mobile_number": ""}, b"All fields are required."),
        ({"confirm_password": "different"}, b"Passwords do not match."),
        ({"password": "short", "confirm_password": "short"}, b"at least 8 characters"),
    ],
)
def test_registration_validation(field_data, expected, registration_store):
    client = pending_client()
    response = client.post("/register", data=registration_data(client, **field_data))

    assert response.status_code == 200
    assert expected in response.data
    registration_store["create"].assert_not_called()
    registration_store["send"].assert_not_called()


def test_registration_requires_auth_csrf(registration_store):
    client = pending_client()
    data = registration_data(client)
    data.pop("_auth_csrf_token")

    response = client.post("/register", data=data)

    assert response.status_code == 400
    registration_store["create"].assert_not_called()


def test_wrong_otp_is_rejected_and_success_consumes_pending_session(registration_store):
    client = pending_client()
    token_data = auth_form(client)
    set_pending_session(client)

    registration_store["complete"].return_value = (False, "invalid")
    response = client.post(
        "/verify-registration-otp",
        data={**token_data, "otp": "000000"},
    )
    assert response.status_code == 200
    assert b"verification code is invalid" in response.data

    registration_store["complete"].return_value = (
        True,
        {"id": 9, "username": "New Owner", "email": "new-owner@example.com"},
    )
    response = client.post(
        "/verify-registration-otp",
        data={**token_data, "otp": "123456"},
    )
    assert response.status_code == 200
    assert b"Account Created Successfully" in response.data
    assert b"Go to Login" in response.data
    assert b"data-dismiss-auth-alert" in response.data
    with client.session_transaction() as session:
        assert "pending_registration_id" not in session
    assert registration_store["complete"].call_count == 2


@pytest.mark.parametrize(
    "result, expected",
    [
        ((False, "expired"), b"expired"),
        ((False, "attempts"), b"Too many verification attempts"),
    ],
)
def test_expired_and_limited_otp_challenges_are_rejected(registration_store, result, expected):
    registration_store["complete"].return_value = result
    client = pending_client()
    token_data = auth_form(client)
    set_pending_session(client)

    response = client.post(
        "/verify-registration-otp",
        data={**token_data, "otp": "123456"},
    )

    assert response.status_code == 200
    assert expected in response.data


def test_resend_replaces_challenge_and_enforces_cooldown(registration_store):
    client = pending_client()
    token_data = auth_form(client)
    set_pending_session(client)

    response = client.post("/resend-registration-otp", data=token_data)
    assert response.status_code == 200
    registration_store["replace"].assert_called_once()
    registration_store["send"].assert_called_once()
    assert len(registration_store["replace"].call_args.args[1]) == 64

    registration_store["resend_status"].return_value = {"resend_count": 0, "can_resend": False}
    registration_store["send"].reset_mock()
    response = client.post("/resend-registration-otp", data=token_data)
    assert response.status_code == 429
    registration_store["send"].assert_not_called()


def test_resend_email_failure_preserves_existing_challenge(registration_store):
    client = pending_client()
    token_data = auth_form(client)
    set_pending_session(client)
    registration_store["send"].side_effect = RuntimeError("smtp-secret-details")

    response = client.post("/resend-registration-otp", data=token_data)

    assert response.status_code == 503
    registration_store["replace"].assert_not_called()
    assert b"smtp-secret-details" not in response.data


def test_resend_limit_is_reported_without_sending(registration_store):
    client = pending_client()
    token_data = auth_form(client)
    set_pending_session(client)
    registration_store["resend_status"].return_value = {"resend_count": 5, "can_resend": False}

    response = client.post("/resend-registration-otp", data=token_data)

    assert response.status_code == 429
    assert b"resend limit" in response.data
    registration_store["send"].assert_not_called()


def test_otp_is_not_in_verification_response_or_logs(registration_store, caplog):
    client = pending_client()
    response = client.post("/register", data=registration_data(client))
    sent_otp = registration_store["send"].call_args.args[1]

    assert sent_otp.encode() not in response.data
    assert sent_otp not in caplog.text


def test_real_db_helper_creates_and_consumes_user_atomically(real_pending_db):
    pending_id = create_real_pending(real_pending_db)

    success, user = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )

    assert success is True
    assert user["email"] == "new-owner@example.com"
    assert len(real_pending_db.users) == 1
    assert db.get_pending_registration(pending_id) is None
    assert real_pending_db.pending[pending_id]["consumed_at"] is not None


def test_real_db_helper_rejects_wrong_otp_and_persists_attempt(real_pending_db):
    pending_id = create_real_pending(real_pending_db)

    success, reason = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("000000"), now=real_pending_db.now
    )

    assert (success, reason) == (False, "invalid")
    assert real_pending_db.pending[pending_id]["otp_attempts"] == 1
    assert not real_pending_db.users


def test_real_db_helper_rejects_expired_otp(real_pending_db):
    pending_id = create_real_pending(
        real_pending_db,
        expires=real_pending_db.now - timedelta(seconds=1),
    )

    success, reason = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )

    assert (success, reason) == (False, "expired")
    assert real_pending_db.pending[pending_id]["otp_attempts"] == 0
    assert not real_pending_db.users


def test_real_db_helper_allows_fifth_attempt_but_rejects_sixth(real_pending_db):
    pending_id = create_real_pending(real_pending_db)

    for _ in range(4):
        success, reason = db.complete_pending_registration(
            pending_id, db.registration_otp_digest("000000"), now=real_pending_db.now
        )
        assert (success, reason) == (False, "invalid")
    assert real_pending_db.pending[pending_id]["otp_attempts"] == 4

    success, user = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )
    assert success is True
    assert user["id"] == 1

    success, reason = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )
    assert (success, reason) == (False, "invalid")


def test_real_db_helper_rejects_sixth_wrong_attempt(real_pending_db):
    pending_id = create_real_pending(real_pending_db)

    for _ in range(5):
        db.complete_pending_registration(
            pending_id, db.registration_otp_digest("000000"), now=real_pending_db.now
        )
    success, reason = db.complete_pending_registration(
        pending_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )

    assert (success, reason) == (False, "attempts")
    assert real_pending_db.pending[pending_id]["otp_attempts"] == 5
    assert not real_pending_db.users


def test_real_db_helper_invalidates_otp_on_resend(real_pending_db):
    pending_id = create_real_pending(real_pending_db, otp="111111")
    real_pending_db.pending[pending_id]["last_sent_at"] = (
        real_pending_db.now - timedelta(seconds=61)
    )

    replacement = db.replace_pending_registration_otp(
        pending_id,
        db.registration_otp_digest("222222"),
        real_pending_db.now + timedelta(minutes=10),
    )
    assert replacement["id"] == pending_id
    assert real_pending_db.pending[pending_id]["resend_count"] == 1
    assert db.complete_pending_registration(
        pending_id, db.registration_otp_digest("111111"), now=real_pending_db.now
    ) == (False, "invalid")
    assert db.complete_pending_registration(
        pending_id, db.registration_otp_digest("222222"), now=real_pending_db.now
    )[0] is True


def test_real_db_helper_enforces_cumulative_resend_limit(real_pending_db):
    pending_id = create_real_pending(real_pending_db)
    for count in range(5):
        real_pending_db.pending[pending_id]["last_sent_at"] = (
            real_pending_db.now - timedelta(seconds=61)
        )
        replacement = db.replace_pending_registration_otp(
            pending_id,
            db.registration_otp_digest(f"{count + 1:06d}"),
            real_pending_db.now + timedelta(minutes=10),
        )
        assert replacement["id"] == pending_id
    assert real_pending_db.pending[pending_id]["resend_count"] == 5
    real_pending_db.pending[pending_id]["last_sent_at"] = (
        real_pending_db.now - timedelta(seconds=61)
    )
    assert db.replace_pending_registration_otp(
        pending_id,
        db.registration_otp_digest("999999"),
        real_pending_db.now + timedelta(minutes=10),
    ) is None


def test_real_db_helper_isolates_pending_challenges(real_pending_db):
    owner_a = create_real_pending(real_pending_db, email="a@example.com", otp="111111")
    owner_b = create_real_pending(real_pending_db, email="b@example.com", otp="222222")

    success, reason = db.complete_pending_registration(
        owner_b, db.registration_otp_digest("111111"), now=real_pending_db.now
    )

    assert (success, reason) == (False, "invalid")
    assert real_pending_db.pending[owner_a]["consumed_at"] is None
    assert real_pending_db.pending[owner_b]["consumed_at"] is None
    assert not real_pending_db.users


def test_real_db_helper_second_verification_cannot_reuse_consumed_challenge(real_pending_db):
    pending_id = create_real_pending(real_pending_db)
    digest = db.registration_otp_digest("123456")

    assert db.complete_pending_registration(pending_id, digest, now=real_pending_db.now)[0] is True
    assert db.complete_pending_registration(pending_id, digest, now=real_pending_db.now) == (
        False,
        "invalid",
    )
    assert len(real_pending_db.users) == 1


def test_repeated_pending_registration_leaves_one_active_record(real_pending_db):
    first_id = create_real_pending(real_pending_db, email="repeat@example.com", otp="111111")
    second_id = create_real_pending(real_pending_db, email="repeat@example.com", otp="222222")

    active = [
        row for row in real_pending_db.pending.values()
        if row["email"] == "repeat@example.com" and row["consumed_at"] is None
    ]
    assert [row["id"] for row in active] == [second_id]
    assert real_pending_db.pending[first_id]["consumed_at"] is not None


def test_duplicate_full_names_are_allowed_for_different_emails(real_pending_db):
    first_id = create_real_pending(real_pending_db, email="first@example.com")
    second_id = create_real_pending(real_pending_db, email="second@example.com")

    assert second_id != first_id
    assert len(real_pending_db.pending) == 2

    assert db.complete_pending_registration(
        first_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )[0] is True
    assert db.complete_pending_registration(
        second_id, db.registration_otp_digest("123456"), now=real_pending_db.now
    )[0] is True
    assert [user["display_name"] for user in real_pending_db.users.values()] == [
        "New Owner",
        "New Owner",
    ]


def test_registration_otp_pepper_is_required(monkeypatch):
    monkeypatch.setattr(db.Config, "SECRET_KEY", None)

    with pytest.raises(RuntimeError):
        db.registration_otp_digest("123456")


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


def test_email_service_supports_an_injected_test_transport():
    sent = []

    class Transport:
        def send(self, recipient, subject, body):
            sent.append((recipient, subject, body))

    service = email_module.EmailService(transport_factory=lambda: Transport())
    service.send_registration_otp("owner@example.com", "123456")

    assert sent[0][0] == "owner@example.com"
    assert "123456" in sent[0][2]


def test_production_smtp_with_credentials_requires_tls(monkeypatch):
    monkeypatch.setattr(email_module, "_is_production_environment", lambda: True)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_USE_TLS", "false")

    with pytest.raises(email_module.EmailConfigurationError):
        email_module.EmailService._smtp_transport()
