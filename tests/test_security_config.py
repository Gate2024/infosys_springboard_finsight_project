import pytest

import app as application


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setattr(application.Config, "SECRET_KEY", None)
    monkeypatch.setenv("FLASK_ENV", "production")

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set in production"):
        application._get_secret_key()


def test_development_uses_a_transient_non_predictable_key(monkeypatch):
    monkeypatch.setattr(application.Config, "SECRET_KEY", None)
    monkeypatch.setenv("FLASK_ENV", "development")

    first_key = application._get_secret_key()
    second_key = application._get_secret_key()

    assert first_key != "finsight-dev-secret-key"
    assert first_key
    assert first_key != second_key


def test_configured_secret_key_is_used_in_production(monkeypatch):
    configured_key = "configured-production-secret"
    monkeypatch.setattr(application.Config, "SECRET_KEY", configured_key)
    monkeypatch.setenv("FLASK_ENV", "production")

    assert application._get_secret_key() == configured_key


def test_debug_is_disabled_by_default_and_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert application._debug_enabled() is False

    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert application._debug_enabled() is True
