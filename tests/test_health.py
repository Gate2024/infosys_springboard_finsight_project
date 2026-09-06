import app as application


def test_health_is_public_machine_readable_and_database_independent(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("health check must not access the database")

    monkeypatch.setattr(application, "get_connection", fail_if_called, raising=False)

    response = application.app.test_client().get("/health")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_health_does_not_allow_state_changing_methods():
    client = application.app.test_client()

    assert client.post("/health").status_code == 405
    assert client.delete("/health").status_code == 405
