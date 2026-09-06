from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib

from werkzeug.security import check_password_hash

import app as application
import db
from tests.auth_helpers import auth_form


class ResetStore:
    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc)
        self.users = {
            "owner@example.com": {
                "id": 7,
                "email": "owner@example.com",
                "password_hash": "old-password-hash",
            },
        }
        self.challenges = []
        self.sessions = []
        self.remember_tokens = []
        self.cursor_obj = None

    @contextmanager
    def connect(self):
        self.cursor_obj = ResetCursor(self)
        yield self

    @contextmanager
    def cursor(self):
        yield self.cursor_obj

    def add_challenge(
        self,
        user_id=7,
        otp_hash=None,
        otp_expires_at=None,
        otp_attempts=0,
        last_sent_at=None,
        resend_count=0,
        verified_at=None,
        reset_token_expires_at=None,
        consumed_at=None,
    ):
        row = {
            "id": len(self.challenges) + 1,
            "user_id": user_id,
            "email": next(
                (user["email"] for user in self.users.values() if user["id"] == user_id),
                "owner@example.com",
            ),
            "otp_hash": otp_hash or db.registration_otp_digest("123456"),
            "otp_expires_at": otp_expires_at or self.now + timedelta(minutes=10),
            "otp_attempts": otp_attempts,
            "last_sent_at": last_sent_at or self.now,
            "resend_count": resend_count,
            "created_at": self.now,
            "verified_at": verified_at,
            "reset_token_hash": None,
            "reset_token_expires_at": reset_token_expires_at,
            "consumed_at": consumed_at,
        }
        self.challenges.append(row)
        return row


class ResetCursor:
    def __init__(self, store):
        self.store = store
        self.result = None
        self.rowcount = 0

    def execute(self, query, params):
        normalized = " ".join(query.lower().split())
        self.result = None
        self.rowcount = 0

        if normalized.startswith("select id, email from users"):
            self._find_user(params[0])
        elif normalized.startswith("select id, user_id, email, otp_expires_at"):
            if "where user_id" in normalized:
                self._find_challenge(user_id=params[0])
            else:
                self._find_challenge(challenge_id=params[0])
        elif normalized.startswith("with expired as"):
            self._create_challenge(params)
        elif normalized.startswith("select resend_count, last_sent_at"):
            self._resend_status(params[0])
        elif normalized.startswith("update password_reset_challenges"):
            if "set otp_hash" in normalized:
                self._replace_otp(params)
            elif "set otp_attempts" in normalized:
                self._increment_attempts(params[0])
            elif "set verified_at" in normalized:
                self._authorize_reset(params)
            elif "set consumed_at" in normalized:
                self._consume_challenge(params[0])
        elif normalized.startswith("select id, otp_hash"):
            self._find_raw_challenge(params[0])
        elif normalized.startswith("select id, user_id"):
            self._find_authorization(params[0])
        elif normalized.startswith("select user_id from password_reset_challenges"):
            self._find_authorization_for_reset(params[0])
        elif normalized.startswith("update users"):
            self._update_password(params)
        elif normalized.startswith("update user_sessions"):
            self._revoke_sessions(params[0])
        elif normalized.startswith("update remember_me_tokens"):
            self._revoke_remember_tokens(params[0])

    def fetchone(self):
        return self.result

    def _find_user(self, email):
        self.result = self.store.users.get(str(email).lower())

    def _active_challenges(self, user_id=None):
        return [
            row
            for row in self.store.challenges
            if row["consumed_at"] is None
            and (user_id is None or row["user_id"] == user_id)
        ]

    def _find_challenge(self, user_id=None, challenge_id=None):
        rows = self._active_challenges(user_id)
        if challenge_id is not None:
            rows = [row for row in rows if row["id"] == challenge_id]
        self.result = max(rows, key=lambda row: row["id"], default=None)

    def _create_challenge(self, params):
        _, user_id, email, otp_hash, expires_at, _ = params
        for row in self._active_challenges(user_id):
            reset_expired = (
                row["reset_token_expires_at"] is not None
                and row["reset_token_expires_at"] <= self.store.now
            )
            if row["otp_expires_at"] <= self.store.now or reset_expired:
                row["consumed_at"] = self.store.now
        if self._active_challenges(user_id):
            return
        self.result = self.store.add_challenge(
            user_id=user_id,
            otp_hash=otp_hash,
            otp_expires_at=expires_at,
            last_sent_at=self.store.now,
        )
        self.result["email"] = email

    def _resend_status(self, challenge_id):
        row = next(
            (row for row in self._active_challenges() if row["id"] == challenge_id),
            None,
        )
        if row:
            self.result = {
                "resend_count": row["resend_count"],
                "last_sent_at": row["last_sent_at"],
                "remaining_seconds": max(
                    0,
                    int(
                        (
                            row["last_sent_at"]
                            + timedelta(seconds=60)
                            - self.store.now
                        ).total_seconds()
                        + 0.999999
                    ),
                ),
                "otp_expired": row["otp_expires_at"] <= self.store.now,
                "can_resend": (
                    row["verified_at"] is None
                    and row["resend_count"] < 5
                    and row["last_sent_at"]
                    <= self.store.now - timedelta(seconds=60)
                ),
            }

    def _replace_otp(self, params):
        otp_hash, expires_at, challenge_id = params
        row = next(
            (row for row in self._active_challenges() if row["id"] == challenge_id),
            None,
        )
        if (
            not row
            or row["verified_at"] is not None
            or row["resend_count"] >= 5
            or row["last_sent_at"]
            > self.store.now - timedelta(seconds=60)
        ):
            return
        row.update(
            otp_hash=otp_hash,
            otp_expires_at=expires_at,
            otp_attempts=0,
            last_sent_at=self.store.now,
            resend_count=row["resend_count"] + 1,
        )
        self.result = row

    def _find_raw_challenge(self, challenge_id):
        self.result = next(
            (row for row in self.store.challenges if row["id"] == challenge_id), None
        )

    def _increment_attempts(self, challenge_id):
        row = next(
            (row for row in self.store.challenges if row["id"] == challenge_id), None
        )
        if row:
            row["otp_attempts"] += 1

    def _authorize_reset(self, params):
        reset_hash, expires_at, challenge_id = params
        row = next(
            (row for row in self._active_challenges() if row["id"] == challenge_id),
            None,
        )
        if not row or row["verified_at"] is not None:
            return
        row["verified_at"] = self.store.now
        row["reset_token_hash"] = reset_hash
        row["reset_token_expires_at"] = expires_at
        self.result = {"id": challenge_id}

    def _find_authorization(self, challenge_id):
        row = next(
            (
                row
                for row in self._active_challenges()
                if row["id"] == challenge_id
                and row["verified_at"] is not None
                and row["reset_token_hash"] is not None
                and row["reset_token_expires_at"] > self.store.now
            ),
            None,
        )
        self.result = {"id": row["id"], "user_id": row["user_id"]} if row else None

    def _find_authorization_for_reset(self, challenge_id):
        row = next(
            (
                row
                for row in self._active_challenges()
                if row["id"] == challenge_id
                and row["verified_at"] is not None
                and row["reset_token_hash"] is not None
                and row["reset_token_expires_at"] > self.store.now
            ),
            None,
        )
        self.result = {"user_id": row["user_id"]} if row else None

    def _consume_challenge(self, challenge_id):
        row = next(
            (row for row in self.store.challenges if row["id"] == challenge_id), None
        )
        if row and row["consumed_at"] is None:
            row["consumed_at"] = self.store.now
            row["reset_token_hash"] = None
            row["reset_token_expires_at"] = None
            self.result = {"id": challenge_id}

    def _update_password(self, params):
        password_hash, user_id = params
        user = next((user for user in self.store.users.values() if user["id"] == user_id), None)
        if user:
            user["password_hash"] = password_hash
            self.result = {"id": user_id}

    def _revoke_sessions(self, user_id):
        for row in self.store.sessions:
            if row["user_id"] == user_id and row["revoked_at"] is None:
                row["revoked_at"] = self.store.now
                self.rowcount += 1

    def _revoke_remember_tokens(self, user_id):
        for row in self.store.remember_tokens:
            if row["user_id"] == user_id and row["revoked_at"] is None:
                row["revoked_at"] = self.store.now
                self.rowcount += 1


def patch_reset_environment(monkeypatch, store, sent=None):
    sent = sent if sent is not None else []
    monkeypatch.setattr(db, "get_connection", store.connect)
    monkeypatch.setattr(
        application.email_service,
        "send_password_reset_otp",
        lambda recipient, otp: sent.append((recipient, otp)),
    )
    return sent


def post_forgot(client, email):
    return client.post(
        "/forgot-password", data=auth_form(client, email=email)
    )


def post_reset_otp(client, otp):
    return client.post(
        "/forgot-password/verify",
        data=auth_form(client, otp=otp),
    )


def test_forgot_password_page_and_login_link_render(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()

    page = client.get("/forgot-password")
    login_page = client.get("/login")

    assert page.status_code == 200
    assert b"Send verification code" in page.data
    assert b"/forgot-password" in login_page.data


def test_forgot_password_otp_uses_server_derived_resend_countdown(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()

    post_forgot(client, "owner@example.com")
    response = client.get("/forgot-password/verify")

    assert response.status_code == 200
    assert b'data-otp-remaining-seconds="60"' in response.data
    assert b"Resend OTP in 60s" in response.data
    assert b'data-otp-resend-eligible="true"' in response.data


def test_registered_and_unknown_email_have_identical_generic_response(monkeypatch):
    store = ResetStore()
    sent = patch_reset_environment(monkeypatch, store)
    known = application.app.test_client()
    unknown = application.app.test_client()

    known_response = post_forgot(known, "owner@example.com")
    unknown_response = post_forgot(unknown, "missing@example.com")

    assert known_response.status_code == unknown_response.status_code == 302
    assert known_response.location == unknown_response.location == "/forgot-password/verify"
    assert sent == [("owner@example.com", sent[0][1])]
    assert len(store.challenges) == 1

    known_page = known.get("/forgot-password/verify")
    unknown_page = unknown.get("/forgot-password/verify")
    assert b'data-otp-remaining-seconds="60"' in known_page.data
    assert b'data-otp-remaining-seconds="60"' in unknown_page.data
    assert b'data-otp-resend-eligible="true"' in known_page.data
    assert b'data-otp-resend-eligible="true"' in unknown_page.data


def test_otp_is_hmac_protected_and_correct_code_creates_short_lived_authorization(
    monkeypatch,
):
    store = ResetStore()
    sent = patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()

    post_forgot(client, "owner@example.com")
    raw_otp = sent[0][1]
    challenge = store.challenges[0]
    assert challenge["otp_hash"] == db.registration_otp_digest(raw_otp)
    assert raw_otp != challenge["otp_hash"]

    response = post_reset_otp(client, raw_otp)

    assert response.status_code == 302
    assert response.location == "/forgot-password/reset"
    assert challenge["verified_at"] is not None
    assert challenge["reset_token_hash"]
    assert len(challenge["reset_token_hash"]) == 64
    with client.session_transaction() as session:
        assert "password_reset_authorized_challenge_id" in session
        assert all(raw_otp not in str(value) for value in session.values())


def test_leading_zero_otp_is_verified_as_text(monkeypatch):
    store = ResetStore()
    sent = patch_reset_environment(monkeypatch, store)
    monkeypatch.setattr(application.secrets, "randbelow", lambda _: 12345)
    client = application.app.test_client()

    post_forgot(client, "owner@example.com")

    assert sent[0][1] == "012345"
    response = post_reset_otp(client, sent[0][1])

    assert response.status_code == 302
    assert response.location == "/forgot-password/reset"


def test_invalid_otp_attempts_persist_and_limit_is_enforced(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()
    post_forgot(client, "owner@example.com")

    for _ in range(5):
        response = post_reset_otp(client, "000000")
        assert response.status_code == 400
    assert store.challenges[0]["otp_attempts"] == 5
    response = post_reset_otp(client, "123456")
    assert response.status_code == 400
    assert b"Too many verification attempts" in response.data


def test_expired_and_consumed_codes_cannot_be_used(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()
    expired = store.add_challenge(
        otp_expires_at=store.now - timedelta(seconds=1),
        last_sent_at=store.now - timedelta(seconds=61),
    )
    with client.session_transaction() as session:
        session["password_reset_challenge_id"] = expired["id"]

    expired_response = post_reset_otp(client, "123456")
    assert expired_response.status_code == 400
    assert b"expired" in expired_response.data

    store.challenges[0]["otp_expires_at"] = store.now + timedelta(minutes=10)
    store.challenges[0]["otp_attempts"] = 0
    store.challenges[0]["consumed_at"] = store.now
    consumed_response = post_reset_otp(client, "123456")
    assert consumed_response.status_code == 400


def test_resend_cooldown_limit_and_successful_replacement(monkeypatch):
    store = ResetStore()
    sent = patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()
    post_forgot(client, "owner@example.com")
    challenge = store.challenges[0]
    first_otp = sent[0][1]

    cooldown = client.post(
        "/forgot-password/resend", data=auth_form(client)
    )
    assert cooldown.status_code == 429
    assert challenge["resend_count"] == 0

    store.now += timedelta(seconds=61)
    resend = client.post(
        "/forgot-password/resend", data=auth_form(client)
    )
    assert resend.status_code == 200
    assert len(sent) == 2
    assert challenge["resend_count"] == 1
    assert challenge["otp_hash"] == db.registration_otp_digest(sent[1][1])
    assert challenge["otp_hash"] != db.registration_otp_digest(first_otp)

    old_code = post_reset_otp(client, first_otp)
    assert old_code.status_code == 400


def test_resend_failure_preserves_existing_challenge(monkeypatch):
    store = ResetStore()
    sent = patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()
    post_forgot(client, "owner@example.com")
    challenge = store.challenges[0]
    original_hash = challenge["otp_hash"]
    store.now += timedelta(seconds=61)
    monkeypatch.setattr(
        application.email_service,
        "send_password_reset_otp",
        lambda recipient, otp: (_ for _ in ()).throw(RuntimeError("smtp unavailable")),
    )

    response = client.post(
        "/forgot-password/resend", data=auth_form(client)
    )

    assert response.status_code == 503
    assert challenge["otp_hash"] == original_hash
    assert challenge["resend_count"] == 0
    assert len(sent) == 1
    with client.session_transaction() as session:
        assert session["password_reset_challenge_id"] == challenge["id"]


def test_resend_limit_is_persisted_and_concurrent_update_cannot_bypass_it(monkeypatch):
    store = ResetStore()
    row = store.add_challenge(
        last_sent_at=store.now - timedelta(seconds=61), resend_count=5
    )
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert db.replace_password_reset_otp(row["id"], "new-hash", store.now) is None
    assert row["resend_count"] == 5

    row["resend_count"] = 0
    first = db.replace_password_reset_otp(row["id"], "first-hash", store.now)
    second = db.replace_password_reset_otp(row["id"], "second-hash", store.now)
    assert first is not None
    assert second is None
    assert row["resend_count"] == 1


def test_reset_authorization_expires_and_is_single_use(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    row = store.add_challenge(
        verified_at=store.now,
        reset_token_expires_at=store.now + timedelta(minutes=10),
    )
    row["reset_token_hash"] = "a" * 64
    monkeypatch.setattr(db, "get_connection", store.connect)

    assert db.get_password_reset_authorization(row["id"])
    row["reset_token_expires_at"] = store.now - timedelta(seconds=1)
    assert db.get_password_reset_authorization(row["id"]) is None

    row["reset_token_expires_at"] = store.now + timedelta(minutes=10)
    assert db.reset_password_with_authorization(row["id"], "new-hash")
    assert not db.reset_password_with_authorization(row["id"], "another-hash")


def test_successful_reset_hashes_password_revokes_sessions_and_remember_tokens(
    monkeypatch,
):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()
    post_forgot(client, "owner@example.com")
    code = "123456"
    store.challenges[0]["otp_hash"] = db.registration_otp_digest(code)
    assert post_reset_otp(client, code).status_code == 302
    store.sessions = [
        {"user_id": 7, "revoked_at": None},
        {"user_id": 99, "revoked_at": None},
    ]
    store.remember_tokens = [
        {"user_id": 7, "revoked_at": None},
        {"user_id": 99, "revoked_at": None},
    ]
    new_password = "new-secure-password"
    response = client.post(
        "/forgot-password/reset",
        data=auth_form(
            client,
            new_password=new_password,
            confirm_password=new_password,
        ),
    )

    assert response.status_code == 302
    assert response.location == "/login?reset=success"
    user = store.users["owner@example.com"]
    assert user["password_hash"] != "old-password-hash"
    assert check_password_hash(user["password_hash"], new_password)
    assert store.sessions[0]["revoked_at"] is not None
    assert store.sessions[1]["revoked_at"] is None
    assert store.remember_tokens[0]["revoked_at"] is not None
    assert store.remember_tokens[1]["revoked_at"] is None
    assert store.challenges[0]["consumed_at"] is not None
    with client.session_transaction() as session:
        assert "uid" not in session

    login = client.get("/login?reset=success")
    assert login.status_code == 200
    assert b"Password reset successful" in login.data
    assert b"data-dismiss-auth-alert" in login.data


def test_password_policy_and_csrf_protect_reset_posts(monkeypatch):
    store = ResetStore()
    patch_reset_environment(monkeypatch, store)
    client = application.app.test_client()

    assert client.post("/forgot-password", data={"email": "owner@example.com"}).status_code == 400
    post_forgot(client, "owner@example.com")
    assert client.post("/forgot-password/verify", data={"otp": "123456"}).status_code == 400
    assert client.post("/forgot-password/resend", data={}).status_code == 400

    row = store.challenges[0]
    row["otp_hash"] = db.registration_otp_digest("123456")
    assert post_reset_otp(client, "123456").status_code == 302
    assert client.post(
        "/forgot-password/reset",
        data={"new_password": "short", "confirm_password": "short"},
    ).status_code == 400
    mismatch = client.post(
        "/forgot-password/reset",
        data=auth_form(
            client,
            new_password="new-secure-password",
            confirm_password="different-password",
        ),
    )
    assert mismatch.status_code == 400
    assert b"Passwords do not match" in mismatch.data


def test_new_reset_strings_are_available_in_all_supported_languages():
    required = {
        "Reset your password",
        "Send verification code",
        "Verify code",
        "Resend code",
        "Choose a new password",
        "Reset password",
        "Password reset successful. Please sign in with your new password.",
        "Resend OTP",
        "Resend OTP in {seconds}s",
        "Resend limit reached",
        "Dismiss",
        "Password must contain at least 8 characters.",
    }
    for language in ("en", "hi", "ja", "de", "fr", "es", "mr"):
        assert required <= application.TRANSLATIONS[language].keys()
