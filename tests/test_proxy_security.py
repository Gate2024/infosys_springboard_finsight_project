import app as application


def test_health_has_no_hsts_for_local_http(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")

    response = application.app.test_client().get("/health")

    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_is_added_only_for_secure_production_request(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")

    with application.app.test_request_context(
        "/health", base_url="https://finsight.example"
    ):
        response = application.app.make_response(application.jsonify(status="ok"))
        response = application.add_security_headers(response)

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
