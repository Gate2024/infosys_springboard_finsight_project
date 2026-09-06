"""Small injectable email boundary used by authentication flows."""

import os
import smtplib
from email.message import EmailMessage
from html import escape

from i18n import translate


def _is_production_environment():
    return any(
        os.getenv(name, "").strip().lower() in {"production", "prod"}
        for name in ("FLASK_ENV", "APP_ENV", "ENVIRONMENT", "VERCEL_ENV", "ENV")
    )


class EmailConfigurationError(RuntimeError):
    pass


class SMTPEmailTransport:
    def __init__(self, host, port, username, password, sender, use_tls=True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.use_tls = use_tls

    def send(self, recipient, subject, body):
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        self._send_message(message)

    def send_html(self, recipient, subject, body, html_body):
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        message.add_alternative(html_body, subtype="html")
        self._send_message(message)

    def _send_message(self, message):
        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(message)


class EmailService:
    def __init__(self, transport_factory=None):
        self.transport_factory = transport_factory or self._smtp_transport

    @staticmethod
    def _smtp_transport():
        host = os.getenv("SMTP_HOST", "").strip()
        sender = os.getenv("SMTP_FROM_EMAIL", "").strip()
        username = os.getenv("SMTP_USERNAME", "").strip()
        use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {
            "0", "false", "no", "off"
        }
        if not host or not sender:
            raise EmailConfigurationError("SMTP email configuration is incomplete.")
        if _is_production_environment() and username and not use_tls:
            raise EmailConfigurationError("Encrypted SMTP transport is required in production.")
        return SMTPEmailTransport(
            host=host,
            port=int(os.getenv("SMTP_PORT", "587")),
            username=username,
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=sender,
            use_tls=use_tls,
        )

    def _send_otp(self, recipient, otp, purpose, language="en"):
        email = render_otp_email(otp, purpose=purpose, language=language)
        transport = self.transport_factory()
        if hasattr(transport, "send_html"):
            transport.send_html(
                recipient,
                email["subject"],
                email["text"],
                email["html"],
            )
            return
        transport.send(recipient, email["subject"], email["text"])

    def send_registration_otp(self, recipient, otp, language="en"):
        self._send_otp(recipient, otp, "registration", language)

    def send_password_reset_otp(self, recipient, otp, language="en"):
        self._send_otp(recipient, otp, "password_reset", language)


def render_otp_email(otp, purpose="registration", language="en"):
    """Build the shared text and HTML OTP email presentation."""
    is_password_reset = purpose == "password_reset"
    heading_key = "Reset Your Password" if is_password_reset else "Verify Your Email"
    detail_key = (
        "Use the verification code below to continue resetting your FinSight password."
        if is_password_reset
        else "Use the verification code below to complete your FinSight account registration."
    )
    subject = (
        "FinSight password reset verification code"
        if is_password_reset
        else "FinSight registration verification code"
    )
    heading = translate(heading_key, language)
    detail = translate(detail_key, language)
    expiry = translate("This code will expire in 10 minutes.", language)
    security = translate(
        "For your security, never share this code with anyone.", language
    )
    not_requested = translate("Didn't request this?", language)
    ignore = translate("You can safely ignore this email.", language)
    tagline = translate("Secure | Simple | Smarter", language)
    companion = translate("Your Personal Finance Companion", language)
    safe_otp = escape(str(otp))

    text = "\n".join(
        (
            "FinSight",
            tagline,
            "",
            "Hello,",
            heading,
            detail,
            "",
            f"Verification code: {otp}",
            expiry,
            security,
            "",
            not_requested,
            ignore,
            "",
            companion,
        )
    )
    html = f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#edf4f6;color:#122333;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#edf4f6;">
      <tr>
        <td align="center" style="padding:36px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
            <tr>
              <td style="padding:0 8px 18px;">
                <div style="font-size:24px;line-height:1;font-weight:800;letter-spacing:-.04em;color:#091a2b;">Fin<span style="color:#138a70;">Sight</span></div>
                <div style="padding-top:7px;color:#138a70;font-size:10px;line-height:1;font-weight:700;letter-spacing:2px;">{escape(tagline)}</div>
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff;border:1px solid #dfe6e9;border-radius:18px;box-shadow:0 16px 36px rgba(9,26,43,.10);padding:38px 36px;">
                <div style="color:#71808d;font-size:13px;line-height:1.5;">{escape(translate("Hello,", language))}</div>
                <h1 style="margin:12px 0 10px;color:#091a2b;font-size:30px;line-height:1.15;letter-spacing:-.04em;">{escape(heading)}</h1>
                <p style="margin:0;color:#526471;font-size:15px;line-height:1.65;">{escape(detail)}</p>
                <div style="margin:28px 0 22px;padding:22px 18px;background:#f1faf7;border:1px solid #bde6d9;border-radius:14px;text-align:center;">
                  <div style="color:#71808d;font-size:11px;line-height:1.4;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">{escape(translate("Verification code", language))}</div>
                  <div style="padding-top:12px;color:#08715c;font-size:34px;line-height:1;font-weight:800;letter-spacing:9px;">{safe_otp}</div>
                </div>
                <p style="margin:0;color:#526471;font-size:13px;line-height:1.6;">{escape(expiry)}</p>
                <p style="margin:7px 0 0;color:#526471;font-size:13px;line-height:1.6;">{escape(security)}</p>
                <div style="margin-top:28px;padding-top:20px;border-top:1px solid #e7eef0;">
                  <div style="color:#122333;font-size:13px;line-height:1.5;font-weight:700;">{escape(not_requested)}</div>
                  <div style="padding-top:4px;color:#71808d;font-size:13px;line-height:1.5;">{escape(ignore)}</div>
                </div>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:20px 8px 0;color:#71808d;font-size:12px;line-height:1.6;">
                <strong style="color:#122333;">FinSight</strong><br>{escape(companion)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return {"subject": subject, "text": text, "html": html}


email_service = EmailService()
