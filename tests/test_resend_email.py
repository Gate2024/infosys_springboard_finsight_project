import pytest

import email_service as email_module


class Response:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_resend_sends_expected_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(email_module.urllib_request, "urlopen", fake_urlopen)
    transport = email_module.ResendEmailTransport("test-key", "FinSight <noreply@example.com>")
    transport.send_html("user@example.com", "Subject", "Plain", "<p>HTML</p>")

    request = captured["request"]
    assert request.full_url == email_module.ResendEmailTransport.endpoint
    assert request.get_header("Authorization") == "Bearer test-key"
    assert request.get_header("Content-type") == "application/json"
    assert request.method == "POST"
    assert email_module.json.loads(request.data) == {
        "from": "FinSight <noreply@example.com>",
        "to": ["user@example.com"],
        "subject": "Subject",
        "text": "Plain",
        "html": "<p>HTML</p>",
    }


def test_resend_non_success_response_fails_without_response_body(monkeypatch):
    monkeypatch.setattr(email_module.urllib_request, "urlopen", lambda *_args, **_kwargs: Response(500))

    with pytest.raises(email_module.EmailDeliveryError) as error:
        email_module.ResendEmailTransport("secret-key", "noreply@example.com").send(
            "user@example.com", "Subject", "Plain"
        )

    assert "secret-key" not in str(error.value)


def test_resend_network_failure_is_sanitized(monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("API key secret-key leaked")

    monkeypatch.setattr(email_module.urllib_request, "urlopen", fail)

    with pytest.raises(email_module.EmailDeliveryError) as error:
        email_module.ResendEmailTransport("secret-key", "noreply@example.com").send(
            "user@example.com", "Subject", "Plain"
        )

    assert "secret-key" not in str(error.value)
    assert "API key" not in str(error.value)


@pytest.mark.parametrize(
    ("transport", "expected"),
    [("resend", email_module.ResendEmailTransport), ("smtp", email_module.SMTPEmailTransport)],
)
def test_transport_selection(monkeypatch, transport, expected):
    monkeypatch.setenv("EMAIL_TRANSPORT", transport)
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")

    selected = email_module.EmailService().transport_factory()

    assert isinstance(selected, expected)
