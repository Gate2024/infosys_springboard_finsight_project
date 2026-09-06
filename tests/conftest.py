import hashlib

import pytest

import app as application


@pytest.fixture
def tracked_session_store(monkeypatch):
    """Explicit test double for the application's tracked-session lookup."""
    sessions = {}

    def add(user_id, token=None):
        token = token or f"fixture-session-{user_id}"
        sessions[(user_id, hashlib.sha256(token.encode()).hexdigest())] = True
        return token

    def is_active(user_id, token_hash, *_timeouts):
        return sessions.get((user_id, token_hash), False)

    monkeypatch.setattr(application, "is_user_session_active", is_active)
    return add
