import csv
import base64
import hashlib
import os
import secrets
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
from io import BytesIO, StringIO

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    Response,
    request,
    session,
    url_for,
)
import pyotp
from cryptography.fernet import Fernet, InvalidToken
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import Config
from db import (
    create_budget,
    create_user_session,
    delete_budget,
    disable_totp_for_user,
    enable_totp_for_user,
    filter_budgets,
    get_budget,
    get_monthly_expense_summary,
    get_notifications,
    get_unread_notification_count,
    get_expense_summary,
    get_summary_stats,
    get_transactions,
    get_totp_credential,
    get_totp_status,
    get_user_by_id,
    get_user_preferences,
    is_user_session_active,
    ensure_user_preferences,
    init_db,
    list_preference_currencies,
    list_preference_languages,
    list_active_user_sessions,
    login_user,
    mark_all_notifications_read,
    mark_notification_read,
    register_user,
    revoke_all_user_sessions,
    revoke_current_user_session,
    revoke_user_session,
    save_pending_totp_secret,
    update_user_preferences,
    update_user_password_and_revoke_other_sessions,
    verify_user_password,
    update_budget,
)
from investment_repository import InvestmentRepository
from investment_service import ASSET_TYPES, InvestmentService
from goal_repository import GoalRepository
from goal_service import GOAL_CATEGORIES, GoalService
from financial_health_service import calculate_financial_health
from report_service import ReportValidationError, build_reporting_data

app = Flask(__name__)


def _is_production_environment():
    production_values = {"production", "prod"}
    environment_names = ("FLASK_ENV", "APP_ENV", "ENVIRONMENT", "VERCEL_ENV", "ENV")
    return any(
        os.getenv(name, "").strip().lower() in production_values
        for name in environment_names
    )


def _get_secret_key():
    if Config.SECRET_KEY:
        return Config.SECRET_KEY
    if _is_production_environment():
        raise RuntimeError("SECRET_KEY must be set in production.")
    return secrets.token_urlsafe(32)


def _debug_enabled():
    return os.getenv("FLASK_DEBUG", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


app.config["SECRET_KEY"] = _get_secret_key()


def _secure_session_cookie_enabled():
    if _is_production_environment():
        return True
    return os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _configure_security_settings():
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_secure_session_cookie_enabled(),
    )


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    ),
}


@app.after_request
def add_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


_configure_security_settings()


LOGIN_MAX_FAILURES = 5
LOGIN_RATE_WINDOW_SECONDS = 300
_login_failures = {}


def _login_rate_limit_key():
    return request.remote_addr or "unknown"


def _active_login_failures(key, now=None):
    now = time.monotonic() if now is None else now
    timestamps = [
        timestamp
        for timestamp in _login_failures.get(key, [])
        if now - timestamp < LOGIN_RATE_WINDOW_SECONDS
    ]
    if timestamps:
        _login_failures[key] = timestamps
    else:
        _login_failures.pop(key, None)
    return timestamps


def _login_rate_limited():
    return len(_active_login_failures(_login_rate_limit_key())) >= LOGIN_MAX_FAILURES


def _record_login_failure():
    key = _login_rate_limit_key()
    timestamps = _active_login_failures(key)
    timestamps.append(time.monotonic())
    _login_failures[key] = timestamps


def _clear_login_failures():
    _login_failures.pop(_login_rate_limit_key(), None)

init_db()
investment_service = InvestmentService(InvestmentRepository())
goal_service = GoalService(GoalRepository())


BUDGET_HEALTHY_LIMIT = Decimal("80")
BUDGET_APPROACHING_LIMIT = Decimal("100")
CATEGORY_CONCENTRATION_THRESHOLD = Decimal("0.50")
LARGE_EXPENSE_MULTIPLIER = Decimal("2")
APPROACHING_BUDGET_THRESHOLD = Decimal("80")
OVER_BUDGET_THRESHOLD = Decimal("100")
PREFERENCE_THEME_OPTIONS = ("default", "light", "dark")
PREFERENCE_THEME_DISPLAY_OPTIONS = ("light", "dark")
PREFERENCE_BOOLEAN_FIELDS = (
    "budget_overspending_alerts",
    "weekly_savings_digest_enabled",
    "sip_due_date_reminders_enabled",
    "bill_due_date_reminders_enabled",
)
PREFERENCE_DEFAULTS = {
    "theme": "default",
    "currency": "USD",
    "language": "en",
    "budget_overspending_alerts": False,
    "weekly_savings_digest_enabled": False,
    "sip_due_date_reminders_enabled": False,
    "bill_due_date_reminders_enabled": False,
}


def normalize_theme(theme):
    """Map persisted theme values to the themes supported by the UI."""
    return "dark" if str(theme or "").strip().lower() == "dark" else "light"


def sync_theme_session(preferences):
    session["theme"] = normalize_theme((preferences or {}).get("theme"))


def login_required_redirect():
    if not session.get("uid"):
        return redirect(url_for("login"))

    session_token_hash = current_session_token_hash()
    if session_token_hash and not is_user_session_active(
        current_user_id(), session_token_hash
    ):
        session.clear()
        flash("Your session is no longer active. Please sign in again.", "danger")
        return redirect(url_for("login"))

    return None


def current_user_id():
    return session["uid"]


def current_session_token_hash():
    session_token = session.get("auth_session_token")
    if not isinstance(session_token, str) or not session_token:
        return None
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def request_device_info():
    return (request.headers.get("User-Agent") or "Unknown device").strip()[:255]


def request_ip_address():
    remote_addr = request.remote_addr or ""
    return remote_addr[:45] or None


def _totp_cipher():
    key_material = hashlib.sha256(
        app.config["SECRET_KEY"].encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_totp_secret(secret):
    return _totp_cipher().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(secret_encrypted):
    return _totp_cipher().decrypt(secret_encrypted.encode("utf-8")).decode("utf-8")


def establish_authenticated_session(user):
    """Create the Flask and tracked-device session after all auth checks pass."""
    session_token = secrets.token_urlsafe(32)
    try:
        create_user_session(
            user["id"],
            hashlib.sha256(session_token.encode("utf-8")).hexdigest(),
            request_device_info(),
            request_ip_address(),
        )
    except Exception:
        app.logger.exception("Authenticated session registration failed")
        return False

    session.clear()
    session["uid"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]
    session["auth_session_token"] = session_token
    try:
        preferences = get_user_preferences(user["id"])
    except Exception:
        app.logger.exception("Unable to load the user's theme preference")
        preferences = None
    sync_theme_session(preferences)
    return True


def _safe_non_negative_decimal(value):
    try:
        return max(Decimal(str(value or 0)), Decimal("0"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def calculate_budget_utilization(budget_amount, spent_amount):
    budget = _safe_non_negative_decimal(budget_amount)
    spent = _safe_non_negative_decimal(spent_amount)
    if budget <= 0:
        return None
    return spent / budget * Decimal("100")


def classify_budget_status(utilization_percentage):
    if utilization_percentage is None:
        return "Unavailable"
    if utilization_percentage < BUDGET_HEALTHY_LIMIT:
        return "Healthy"
    if utilization_percentage <= BUDGET_APPROACHING_LIMIT:
        return "Approaching Limit"
    return "Over Budget"


def build_budget_spending_analysis(budgets, stats):
    analysis_rows = []
    for budget in budgets:
        budget_amount = _safe_non_negative_decimal(budget.get("budget_amount"))
        spent_amount = _safe_non_negative_decimal(budget.get("spent_amount"))
        remaining_value = budget.get("remaining_amount")
        if remaining_value in (None, ""):
            remaining_amount = budget_amount - spent_amount
        else:
            try:
                remaining_amount = Decimal(str(remaining_value))
            except (InvalidOperation, ValueError, TypeError):
                remaining_amount = budget_amount - spent_amount

        utilization = calculate_budget_utilization(budget_amount, spent_amount)
        analysis_rows.append(
            {
                "budget_name": budget.get("budget_name") or "Budget",
                "category": budget.get("category") or "Uncategorized",
                "budget_amount": budget_amount,
                "spent_amount": spent_amount,
                "remaining_amount": remaining_amount,
                "utilization_percentage": utilization,
                "progress_percentage": min(utilization or Decimal("0"), Decimal("100")),
                "status": classify_budget_status(utilization),
            }
        )

    total_budget = _safe_non_negative_decimal(stats.get("total_allocated"))
    total_spent = _safe_non_negative_decimal(stats.get("total_spent"))
    total_remaining = stats.get("total_remaining")
    if total_remaining in (None, ""):
        total_remaining = total_budget - total_spent
    else:
        try:
            total_remaining = Decimal(str(total_remaining))
        except (InvalidOperation, ValueError, TypeError):
            total_remaining = total_budget - total_spent

    overall_utilization = calculate_budget_utilization(total_budget, total_spent)
    return analysis_rows, {
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_remaining,
        "utilization_percentage": overall_utilization,
        "status": classify_budget_status(overall_utilization),
    }


def _finite_decimal(value):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def build_spending_recommendations(
    budget_spending_analysis,
    expense_breakdown,
    monthly_expenses,
    expense_stats,
):
    recommendations = []

    for budget in budget_spending_analysis or []:
        budget_name = budget.get("budget_name") or "Budget"
        utilization = _finite_decimal(budget.get("utilization_percentage"))
        status = budget.get("status")

        if status == "Over Budget" or (
            utilization is not None and utilization > OVER_BUDGET_THRESHOLD
        ):
            recommendations.append(
                {
                    "priority": "High",
                    "style": "danger",
                    "icon": "bi bi-exclamation-octagon-fill",
                    "title": "Budget Over Limit",
                    "message": (
                        f"Your {budget_name} budget is over its stored limit. "
                        "Review spending in this budget."
                    ),
                }
            )
        elif (
            utilization is not None
            and APPROACHING_BUDGET_THRESHOLD <= utilization <= OVER_BUDGET_THRESHOLD
        ):
            recommendations.append(
                {
                    "priority": "Medium",
                    "style": "warning",
                    "icon": "bi bi-exclamation-triangle-fill",
                    "title": "Budget Near Limit",
                    "message": (
                        f"Your {budget_name} budget is approaching its stored limit. "
                        "Review remaining spending."
                    ),
                }
            )

    category_totals = []
    for item in expense_breakdown or []:
        amount = _finite_decimal(item.get("amount"))
        if amount is not None and amount > 0:
            category_totals.append((item.get("category") or "Other", amount))

    total_category_expenses = sum(
        (amount for _, amount in category_totals), Decimal("0")
    )
    if category_totals and total_category_expenses > 0:
        largest_category, largest_category_amount = max(
            category_totals, key=lambda item: item[1]
        )
        if (
            largest_category_amount / total_category_expenses
            >= CATEGORY_CONCENTRATION_THRESHOLD
        ):
            recommendations.append(
                {
                    "priority": "Medium",
                    "style": "info",
                    "icon": "bi bi-pie-chart-fill",
                    "title": "Expense Concentration",
                    "message": (
                        "A large share of your recorded expenses is concentrated in "
                        f"{largest_category}. Review this category for possible reductions."
                    ),
                }
            )

    if len(monthly_expenses or []) >= 2:
        previous_amount = _finite_decimal(monthly_expenses[-2].get("amount"))
        latest_amount = _finite_decimal(monthly_expenses[-1].get("amount"))
        if (
            previous_amount is not None
            and latest_amount is not None
            and latest_amount > previous_amount
        ):
            recommendations.append(
                {
                    "priority": "Medium",
                    "style": "warning",
                    "icon": "bi bi-graph-up-arrow",
                    "title": "Spending Increased",
                    "message": (
                        "Recorded spending increased compared with the previous "
                        "recorded month. Review recent expenses."
                    ),
                }
            )

    total_expenses = _finite_decimal((expense_stats or {}).get("total_expenses"))
    average_expense = _finite_decimal((expense_stats or {}).get("average_expense"))
    largest_expense = _finite_decimal((expense_stats or {}).get("largest_expense"))
    if (
        total_expenses is not None
        and total_expenses > 0
        and average_expense is not None
        and average_expense > 0
        and largest_expense is not None
        and largest_expense >= LARGE_EXPENSE_MULTIPLIER * average_expense
    ):
        recommendations.append(
            {
                "priority": "Low",
                "style": "info",
                "icon": "bi bi-receipt-cutoff",
                "title": "Large Expense",
                "message": (
                    "One recorded expense is substantially larger than your average "
                    "expense. Review that transaction."
                ),
            }
        )

    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    recommendations.sort(key=lambda item: priority_order[item["priority"]])
    return recommendations


def investment_csrf_token():
    token = session.get("investment_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["investment_csrf_token"] = token
    return token


def investment_csrf_valid():
    expected = session.get("investment_csrf_token")
    supplied = request.form.get("_investment_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def goal_csrf_token():
    token = session.get("goal_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["goal_csrf_token"] = token
    return token


def goal_csrf_valid():
    expected = session.get("goal_csrf_token")
    supplied = request.form.get("_goal_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def budget_csrf_token():
    token = session.get("budget_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["budget_csrf_token"] = token
    return token


def budget_csrf_valid():
    expected = session.get("budget_csrf_token")
    supplied = request.form.get("_budget_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def expense_csrf_token():
    token = session.get("expense_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["expense_csrf_token"] = token
    return token


def expense_csrf_valid():
    expected = session.get("expense_csrf_token")
    supplied = request.form.get("_expense_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def preferences_csrf_token():
    token = session.get("preferences_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["preferences_csrf_token"] = token
    return token


def preferences_csrf_valid():
    expected = session.get("preferences_csrf_token")
    supplied = request.form.get("_preferences_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def notifications_csrf_token():
    token = session.get("notifications_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["notifications_csrf_token"] = token
    return token


def notifications_csrf_valid():
    expected = session.get("notifications_csrf_token")
    supplied = request.form.get("_notifications_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def notification_redirect_target():
    target = request.form.get("next", "")
    return target if target.startswith("/") and not target.startswith("//") else url_for("notifications")


@app.context_processor
def inject_notification_header_data():
    if not session.get("uid"):
        return {
            "notification_preview": [],
            "notification_unread_count": 0,
            "notification_csrf_token": "",
            "notification_theme_preferences": {},
            "notification_preferences_csrf_token": "",
        }
    try:
        user_id = current_user_id()
        preferences = get_user_preferences(user_id) or PREFERENCE_DEFAULTS
        return {
            "notification_preview": get_notifications(user_id, "all", 5),
            "notification_unread_count": get_unread_notification_count(user_id),
            "notification_csrf_token": notifications_csrf_token(),
            "notification_theme_preferences": preferences,
            "notification_preferences_csrf_token": preferences_csrf_token(),
        }
    except Exception:
        app.logger.exception("Unable to load notification header data")
        return {
            "notification_preview": [],
            "notification_unread_count": 0,
            "notification_csrf_token": "",
            "notification_theme_preferences": {},
            "notification_preferences_csrf_token": "",
        }


def security_sessions_csrf_token():
    token = session.get("security_sessions_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["security_sessions_csrf_token"] = token
    return token


def security_sessions_csrf_valid():
    expected = session.get("security_sessions_csrf_token")
    supplied = request.form.get("_security_sessions_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def two_factor_login_csrf_token():
    token = session.get("two_factor_login_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["two_factor_login_csrf_token"] = token
    return token


def two_factor_login_csrf_valid():
    expected = session.get("two_factor_login_csrf_token")
    supplied = request.form.get("_two_factor_login_csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


@app.route("/")
def home():
    if session.get("uid"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid"):
        session_token_hash = current_session_token_hash()
        if not session_token_hash or is_user_session_active(
            current_user_id(), session_token_hash
        ):
            return redirect(url_for("dashboard"))
        session.clear()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if _login_rate_limited():
            return render_template(
                "login.html",
                error="Too many failed login attempts. Please try again later.",
            ), 429

        success, user = login_user(email, password)
        if success:
            _clear_login_failures()
            session.clear()
            if get_totp_status(user["id"])["is_enabled"]:
                session["pending_2fa_user_id"] = user["id"]
                return redirect(url_for("login_two_factor"))

            if not establish_authenticated_session(user):
                return render_template(
                    "login.html",
                    error="Unable to start a secure session. Please try again.",
                ), 503
            return redirect(url_for("dashboard"))

        _record_login_failure()
        return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html", error=None)


@app.route("/login/2fa", methods=["GET", "POST"])
def login_two_factor():
    pending_user_id = session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "two_factor_login.html",
            two_factor_login_csrf_token=two_factor_login_csrf_token(),
            error=None,
        )

    if not two_factor_login_csrf_valid():
        return render_template(
            "two_factor_login.html",
            two_factor_login_csrf_token=two_factor_login_csrf_token(),
            error="The form security token is missing or invalid.",
        ), 400
    if _login_rate_limited():
        return render_template(
            "two_factor_login.html",
            two_factor_login_csrf_token=two_factor_login_csrf_token(),
            error="Too many failed verification attempts. Please try again later.",
        ), 429

    credential = get_totp_credential(pending_user_id)
    if not credential or credential["enabled_at"] is None:
        session.clear()
        return redirect(url_for("login"))

    try:
        is_valid = pyotp.TOTP(
            decrypt_totp_secret(credential["secret_encrypted"])
        ).verify(request.form.get("totp_code", ""), valid_window=0)
    except (InvalidToken, ValueError):
        is_valid = False

    if not is_valid:
        _record_login_failure()
        return render_template(
            "two_factor_login.html",
            two_factor_login_csrf_token=two_factor_login_csrf_token(),
            error="Invalid verification code.",
        )

    user = get_user_by_id(pending_user_id)
    if not user or not establish_authenticated_session(user):
        session.clear()
        return render_template(
            "login.html",
            error="Unable to start a secure session. Please try again.",
        ), 503

    _clear_login_failures()
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("uid"):
        return redirect(url_for("dashboard"))

    if request.method == "GET":
        return redirect(url_for("login"))

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not username or not email or not password:
        return render_template("login.html", error="All fields are required.")
    if len(password) < 6:
        return render_template(
            "login.html", error="Password must contain at least 6 characters."
        )

    success, result = register_user(username, email, password)
    if success:
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("login.html", error=result)


@app.route("/logout")
def logout():
    user_id = session.get("uid")
    session_token_hash = current_session_token_hash()
    if user_id and session_token_hash:
        try:
            revoke_current_user_session(user_id, session_token_hash)
        except Exception:
            app.logger.exception("Authenticated session revocation failed during logout")
    session.clear()
    return redirect(url_for("login"))


@app.get("/profile")
def profile():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user = get_user_by_id(current_user_id())
    if not user:
        flash("Profile not found.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("profile/dashboard.html", user=user)


def security_page_data(user_id):
    return (
        list_active_user_sessions(user_id, current_session_token_hash() or ""),
        get_totp_status(user_id),
    )


def render_security_sessions(
    active_sessions, totp_status, status=200, setup_secret=None
):
    return render_template(
        "profile/security.html",
        active_sessions=active_sessions,
        totp_status=totp_status,
        setup_secret=setup_secret,
        security_sessions_csrf_token=security_sessions_csrf_token(),
    ), status


@app.get("/profile/security")
def profile_security():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    active_sessions, totp_status = security_page_data(current_user_id())
    return render_security_sessions(active_sessions, totp_status)


@app.post("/profile/security/password")
def change_password():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    active_sessions, totp_status = security_page_data(user_id)
    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if not verify_user_password(user_id, current_password):
        flash("Current password is incorrect.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if verify_user_password(user_id, new_password):
        flash("New password must be different from the current password.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if len(new_password) < 6:
        flash("Password must contain at least 6 characters.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    try:
        changed = update_user_password_and_revoke_other_sessions(
            user_id, new_password, current_session_token_hash() or ""
        )
    except Exception:
        app.logger.exception("Password change failed")
        flash("Unable to change password. Please try again.", "danger")
        return render_security_sessions(active_sessions, totp_status, 503)

    if not changed:
        flash("Unable to change password. Please try again.", "danger")
        return render_security_sessions(active_sessions, totp_status, 503)

    flash("Password changed successfully. Other active devices were signed out.", "success")
    return redirect(url_for("profile_security"))


@app.post("/profile/security/totp/setup")
def setup_totp():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    active_sessions, totp_status = security_page_data(user_id)
    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if totp_status["is_enabled"]:
        flash("Two-factor authentication is already enabled.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    secret = pyotp.random_base32()
    try:
        save_pending_totp_secret(user_id, encrypt_totp_secret(secret))
    except Exception:
        app.logger.exception("Two-factor setup could not be saved")
        flash("Unable to start two-factor setup. Please try again.", "danger")
        return render_security_sessions(active_sessions, totp_status, 503)

    active_sessions, totp_status = security_page_data(user_id)
    return render_security_sessions(
        active_sessions, totp_status, setup_secret=secret
    )


@app.post("/profile/security/totp/verify")
def verify_totp_setup():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    active_sessions, totp_status = security_page_data(user_id)
    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    credential = get_totp_credential(user_id)
    if not credential or credential["enabled_at"] is not None:
        flash("No pending two-factor setup was found.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    try:
        is_valid = pyotp.TOTP(
            decrypt_totp_secret(credential["secret_encrypted"])
        ).verify(request.form.get("totp_code", ""), valid_window=0)
    except (InvalidToken, ValueError):
        is_valid = False

    if not is_valid or not enable_totp_for_user(user_id):
        flash("Invalid verification code.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    flash("Two-factor authentication is enabled.", "success")
    return redirect(url_for("profile_security"))


@app.post("/profile/security/totp/disable")
def disable_totp():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    active_sessions, totp_status = security_page_data(user_id)
    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if not totp_status["is_enabled"]:
        flash("Two-factor authentication is not enabled.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if not verify_user_password(user_id, request.form.get("current_password", "")):
        flash("Current password is incorrect.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)

    credential = get_totp_credential(user_id)
    try:
        is_valid = credential and pyotp.TOTP(
            decrypt_totp_secret(credential["secret_encrypted"])
        ).verify(request.form.get("totp_code", ""), valid_window=0)
    except (InvalidToken, ValueError):
        is_valid = False

    if not is_valid:
        flash("Invalid verification code.", "danger")
        return render_security_sessions(active_sessions, totp_status, 400)
    if not disable_totp_for_user(user_id):
        flash("Unable to disable two-factor authentication.", "danger")
        return render_security_sessions(active_sessions, totp_status, 503)

    flash("Two-factor authentication is disabled.", "success")
    return redirect(url_for("profile_security"))


@app.post("/profile/security/sessions/<int:session_id>/logout")
def logout_device_session(session_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    session_token_hash = current_session_token_hash() or ""
    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        active_sessions, totp_status = security_page_data(user_id)
        return render_security_sessions(active_sessions, totp_status, 400)

    if revoke_user_session(session_id, user_id, session_token_hash):
        flash("Device signed out successfully.", "success")
    else:
        flash("Active device not found.", "danger")
    return redirect(url_for("profile_security"))


@app.post("/profile/security/sessions/logout-all")
def logout_all_device_sessions():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if not security_sessions_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        active_sessions, totp_status = security_page_data(current_user_id())
        return render_security_sessions(active_sessions, totp_status, 400)

    revoke_all_user_sessions(current_user_id())
    session.clear()
    flash("You have been signed out from all devices.", "success")
    return redirect(url_for("login"))


def preference_reference_options():
    return list_preference_currencies(), list_preference_languages()


def validate_preferences_form(form, currency_options, language_options):
    preferences = {
        "theme": form.get("theme", "").strip().lower(),
        "currency": form.get("currency", "").strip().upper(),
        "language": form.get("language", "").strip().lower(),
    }
    errors = []

    if preferences["theme"] not in PREFERENCE_THEME_OPTIONS:
        errors.append("Select a supported theme.")
    currency_codes = {option["code"] for option in currency_options}
    language_codes = {option["code"] for option in language_options}
    if preferences["currency"] not in currency_codes:
        errors.append("Select a supported currency.")
    if preferences["language"] not in language_codes:
        errors.append("Select a supported language.")

    for field in PREFERENCE_BOOLEAN_FIELDS:
        preferences[field] = field in form

    return preferences, errors


def render_preferences(preferences, currency_options, language_options, status=200):
    sync_theme_session(preferences)
    return render_template(
        "profile/preferences.html",
        preferences=preferences or PREFERENCE_DEFAULTS,
        theme_options=PREFERENCE_THEME_DISPLAY_OPTIONS,
        currency_options=currency_options,
        language_options=language_options,
        preferences_csrf_token=preferences_csrf_token(),
    ), status


@app.route("/profile/preferences", methods=["GET", "POST"])
def profile_preferences():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    currency_options, language_options = preference_reference_options()

    if request.method == "GET":
        return render_preferences(
            ensure_user_preferences(user_id), currency_options, language_options
        )

    if not preferences_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_preferences(
            get_user_preferences(user_id), currency_options, language_options, 400
        )

    updated_preferences, errors = validate_preferences_form(
        request.form, currency_options, language_options
    )
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_preferences(
            get_user_preferences(user_id), currency_options, language_options, 400
        )

    preferences = ensure_user_preferences(user_id)

    try:
        saved_preferences = update_user_preferences(user_id, updated_preferences)
    except Exception:
        app.logger.exception("Preference update failed")
        flash("Unable to save preferences. Please try again.", "danger")
        return render_preferences(preferences, currency_options, language_options, 503)

    if not saved_preferences:
        flash("Unable to save preferences. Please try again.", "danger")
        return render_preferences(preferences, currency_options, language_options, 503)

    flash("Preferences saved successfully.", "success")
    return redirect(url_for("profile_preferences"))


@app.route("/dashboard")
def dashboard():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    # Existing M1/M2 dashboard data
    stats = get_summary_stats(user_id)

    expense_stats = get_expense_summary(user_id)
    expense_transactions = get_transactions(user_id)
    monthly_expenses = get_monthly_expense_summary(user_id)
    budget_rows = filter_budgets(user_id)
    budget_spending_analysis, budget_spending_summary = build_budget_spending_analysis(
        budget_rows, stats
    )

    expense_total = float(expense_stats.get("total_spent") or 0)
    category_totals = {}
    for transaction in expense_transactions:
        category = transaction.get("category") or "Other"
        category_totals[category] = category_totals.get(category, 0) + float(
            transaction.get("amount") or 0
        )

    expense_colors = [
        "#2563EB",
        "#22C55E",
        "#F59E0B",
        "#EF4444",
        "#8B5CF6",
        "#06B6D4",
    ]
    expense_breakdown = [
        {
            "category": category,
            "amount": amount,
            "percentage": (amount / expense_total * 100) if expense_total else 0,
            "color": expense_colors[index % len(expense_colors)],
        }
        for index, (category, amount) in enumerate(
            sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        )
    ]
    spending_recommendations = build_spending_recommendations(
        budget_spending_analysis,
        expense_breakdown,
        monthly_expenses,
        expense_stats,
    )

    budget_progress = []
    for budget in budget_rows:
        budget_amount = float(budget.get("budget_amount") or 0)
        spent_amount = float(budget.get("spent_amount") or 0)
        budget_progress.append(
            {
                "budget_name": budget.get("budget_name") or "Budget",
                "budget_amount": budget_amount,
                "spent_amount": spent_amount,
                "remaining_amount": float(budget.get("remaining_amount") or 0),
                "percentage": min(
                    100,
                    (spent_amount / budget_amount * 100) if budget_amount else 0,
                ),
            }
        )
    # Existing M2 goal data
    goals = goal_service.list_for_user(user_id)

    # Existing M2 investment analytics
    _, investment_stats = investment_service.list_for_user(user_id)

    # Aggregate goal progress using existing goal values
    goal_total_current = sum(
        Decimal(str(goal.get("current_amount") or 0))
        for goal in goals
    )
    goal_total_target = sum(
        Decimal(str(goal.get("target_amount") or 0))
        for goal in goals
    )

    # Calculate M3 Financial Health Score
    financial_health = calculate_financial_health(
        budget_data={
            "total_allocated": stats.get("total_allocated"),
            "total_spent": stats.get("total_spent"),
        },
        spending_data={
            "total_spent": expense_stats.get("total_spent"),
            "average_expense": expense_stats.get("average_expense"),
            "largest_expense": expense_stats.get("largest_expense"),
            "expense_count": expense_stats.get("total_expenses"),
            "month_spent": expense_stats.get("month_spent"),
            "month_expenses": expense_stats.get("month_expenses"),
        },
        goal_data={
            "total_current": goal_total_current,
            "total_target": goal_total_target,
        },
        investment_data={
            "return_percentage": investment_stats.get("return_percentage"),
        },
    )
    return render_template(
        "dashboard.html",
        stats=stats,
        financial_health=financial_health,
        dashboard_month_spent=float(expense_stats.get("month_spent") or 0),
        dashboard_budget_left=float(stats.get("total_remaining") or 0),
        expense_breakdown=expense_breakdown,
        monthly_expenses=monthly_expenses,
        budget_spending_analysis=budget_spending_analysis,
        budget_spending_summary=budget_spending_summary,
        spending_recommendations=spending_recommendations,
        budget_progress=budget_progress,
        recent_transactions=expense_transactions[:5],
        current_username=session["username"],
    )


@app.get("/notifications")
def notifications():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    selected_filter = request.args.get("filter", "all").strip().lower()
    if selected_filter not in {"all", "unread", "alert", "milestone"}:
        selected_filter = "all"
    return render_template(
        "notifications/dashboard.html",
        notifications=get_notifications(current_user_id(), selected_filter),
        selected_filter=selected_filter,
        notifications_csrf_token=notifications_csrf_token(),
    )


@app.post("/notifications/<int:notification_id>/read")
def notification_read(notification_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not notifications_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("notifications")), 400
    mark_notification_read(current_user_id(), notification_id)
    return redirect(notification_redirect_target())


@app.post("/notifications/read-all")
def notifications_read_all():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not notifications_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("notifications")), 400
    mark_all_notifications_read(current_user_id())
    return redirect(notification_redirect_target())


@app.get("/reports")
def reports_data():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    accepts = request.headers.get("Accept", "").lower()
    wants_json = (
        request.args.get("format") == "json"
        or not accepts
        or ("application/json" in accepts and "text/html" not in accepts)
    )

    try:
        report_data = build_reporting_data(
            current_user_id(),
            request.args.get("start_date"),
            request.args.get("end_date"),
            investment_service=investment_service,
            goal_service=goal_service,
        )
    except ReportValidationError as error:
        if wants_json:
            return jsonify({"error": str(error)}), 400
        return render_template(
            "reports/dashboard.html",
            report=None,
            error=str(error),
            start_date=request.args.get("start_date", ""),
            end_date=request.args.get("end_date", ""),
        ), 400

    if wants_json:
        return jsonify(report_data)
    return render_template(
        "reports/dashboard.html",
        report=report_data,
        start_date=request.args.get("start_date", ""),
        end_date=request.args.get("end_date", ""),
    )


def _pdf_decimal(value):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _pdf_amount(value):
    number = _pdf_decimal(value)
    return "Unavailable" if number is None else f"INR {number:,.2f}"


def _pdf_percent(value):
    number = _pdf_decimal(value)
    return "Unavailable" if number is None else f"{number:,.2f}%"


def _pdf_number(value):
    number = _pdf_decimal(value)
    if number is None:
        return "Unavailable"
    if number == number.to_integral_value():
        return str(int(number))
    return f"{number:,.2f}"


def _pdf_count(value):
    number = _pdf_decimal(value)
    return "0" if number is None else str(int(number))


def _pdf_date(value):
    if not value:
        return "Unavailable"
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%B %d, %Y").replace(
            " 0", " "
        )
    except (TypeError, ValueError):
        return str(value)


def _pdf_period(report_data):
    date_range = report_data.get("date_range") or {}
    start_date = date_range.get("start_date")
    end_date = date_range.get("end_date")
    if start_date and end_date:
        return f"{_pdf_date(start_date)} - {_pdf_date(end_date)}"
    return "All Available Expense History"


def _pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PDFTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#091A2B"),
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "PDFSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#138A70"),
            spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "PDFSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#138A70"),
            spaceBefore=14,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "PDFBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#122333"),
            spaceAfter=5,
        ),
        "muted": ParagraphStyle(
            "PDFMuted",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#71808D"),
            spaceAfter=5,
        ),
        "table_header": ParagraphStyle(
            "PDFTableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
        "table_body": ParagraphStyle(
            "PDFTableBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#122333"),
        ),
        "summary_label": ParagraphStyle(
            "PDFSummaryLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#71808D"),
            alignment=TA_CENTER,
        ),
        "summary_value": ParagraphStyle(
            "PDFSummaryValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#091A2B"),
            alignment=TA_CENTER,
        ),
    }


def _pdf_cell(value, style):
    text = "" if value is None else str(value)
    return Paragraph(escape(text), style)


def _pdf_table(rows, widths, styles):
    formatted_rows = []
    for index, row in enumerate(rows):
        style = styles["table_header"] if index == 0 else styles["table_body"]
        formatted_rows.append([_pdf_cell(value, style) for value in row])

    table = Table(formatted_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#091A2B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DFE6E9")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F6F9F9")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#F6F9F9"),
                ]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _pdf_summary_table(items, styles):
    return _pdf_table(
        [
            [item[0] for item in items],
            [item[1] for item in items],
        ],
        [540 / len(items)] * len(items),
        {
            **styles,
            "table_header": styles["summary_label"],
            "table_body": styles["summary_value"],
        },
    )


def _draw_pdf_header_footer(canvas, document):
    width, height = letter
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#091A2B"))
    canvas.rect(0, height - 36, width, 36, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(document.leftMargin, height - 23, "FinSight")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - document.rightMargin, height - 23, "Financial Report")
    canvas.setFillColor(colors.HexColor("#71808D"))
    canvas.drawRightString(width - document.rightMargin, 20, f"Page {document.page}")
    canvas.restoreState()


def _build_pdf_report(report_data):
    styles = _pdf_styles()
    expenses = report_data.get("expenses") or {}
    expense_summary = expenses.get("expense_summary") or {}
    budgets = report_data.get("budgets") or {}
    investments = report_data.get("investments") or {}
    investment_stats = investments.get("stats") or {}
    goals = report_data.get("goals") or {}
    health = report_data.get("financial_health") or {}
    story = [
        Paragraph("FinSight", styles["title"]),
        Paragraph("Financial Report", styles["subtitle"]),
        Paragraph(
            f"<b>Reporting Period:</b> {escape(_pdf_period(report_data))}",
            styles["body"],
        ),
        Paragraph(
            f"<b>Generated:</b> {escape(datetime.now().strftime('%B %d, %Y %H:%M'))}",
            styles["muted"],
        ),
    ]

    story.append(Paragraph("1. Expense Summary", styles["section"]))
    story.append(
        _pdf_summary_table(
            [
                ("Total Expenses", _pdf_amount(expense_summary.get("total_expenses"))),
                ("Transaction Count", _pdf_count(expense_summary.get("transaction_count"))),
                ("Average Expense", _pdf_amount(expense_summary.get("average_expense"))),
                ("Largest Expense", _pdf_amount(expense_summary.get("largest_expense"))),
            ],
            styles,
        )
    )

    story.append(Paragraph("2. Expense by Category", styles["section"]))
    category_totals = expenses.get("category_totals") or []
    if category_totals:
        story.append(
            _pdf_table(
                [["Category", "Amount"]]
                + [
                    [item.get("category") or "Uncategorized", _pdf_amount(item.get("amount"))]
                    for item in category_totals
                ],
                [360, 180],
                styles,
            )
        )
    else:
        story.append(Paragraph("No expense data available for the selected period.", styles["muted"]))

    story.append(Paragraph("3. Monthly Spending", styles["section"]))
    monthly_totals = expenses.get("monthly_totals") or []
    if monthly_totals:
        story.append(
            _pdf_table(
                [["Month", "Amount"]]
                + [[item.get("month") or "Unknown", _pdf_amount(item.get("amount"))] for item in monthly_totals],
                [360, 180],
                styles,
            )
        )
    else:
        story.append(Paragraph("No monthly expense data available.", styles["muted"]))

    story.append(Paragraph("4. Budget Snapshot - Current Snapshot", styles["section"]))
    story.append(Paragraph("Budget data represents the current stored budget snapshot.", styles["muted"]))
    story.append(
        _pdf_summary_table(
            [
                ("Total Budget", _pdf_amount(budgets.get("total_budget"))),
                ("Total Spent", _pdf_amount(budgets.get("total_spent"))),
                ("Total Remaining", _pdf_amount(budgets.get("total_remaining"))),
                ("Utilization", _pdf_percent(budgets.get("overall_utilization"))),
                ("Budget Count", _pdf_count(budgets.get("budget_count"))),
            ],
            styles,
        )
    )
    budget_rows = budgets.get("budgets") or []
    if budget_rows:
        story.append(Spacer(1, 8))
        story.append(
            _pdf_table(
                [["Budget", "Category", "Budget Amount", "Spent", "Remaining", "Status"]]
                + [
                    [
                        item.get("budget_name") or "Budget",
                        item.get("category") or "Uncategorized",
                        _pdf_amount(item.get("budget_amount")),
                        _pdf_amount(item.get("spent_amount")),
                        _pdf_amount(item.get("remaining_amount")),
                        item.get("status") or "Unavailable",
                    ]
                    for item in budget_rows
                ],
                [120, 80, 90, 80, 90, 80],
                styles,
            )
        )

    story.append(Paragraph("5. Investment Snapshot - Current Snapshot", styles["section"]))
    story.append(Paragraph("Investment data represents the current portfolio snapshot.", styles["muted"]))
    story.append(
        _pdf_summary_table(
            [
                ("Invested Value", _pdf_amount(investment_stats.get("total_invested"))),
                ("Current Value", _pdf_amount(investment_stats.get("current_value"))),
                ("Absolute Return", _pdf_amount(investment_stats.get("absolute_return"))),
                ("Return Percentage", _pdf_percent(investment_stats.get("return_percentage"))),
                ("Holding Count", _pdf_count(investments.get("holding_count"))),
            ],
            styles,
        )
    )
    allocation = investment_stats.get("allocation") or []
    if allocation:
        story.append(Spacer(1, 8))
        story.append(
            _pdf_table(
                [["Asset Type", "Allocation"]]
                + [[item.get("asset_type") or "Unknown", _pdf_percent(item.get("percentage"))] for item in allocation],
                [360, 180],
                styles,
            )
        )

    story.append(Paragraph("6. Goal Progress - Current Snapshot", styles["section"]))
    story.append(Paragraph("Goal values represent current saved progress; historical contributions are not available.", styles["muted"]))
    goal_rows = goals.get("goals") or []
    if goal_rows:
        story.append(
            _pdf_table(
                [["Goal", "Target", "Current", "Progress", "Remaining", "Status", "Target Date"]]
                + [
                    [
                        item.get("goal_name") or "Goal",
                        _pdf_amount(item.get("target_amount")),
                        _pdf_amount(item.get("current_amount")),
                        _pdf_percent(item.get("progress_percentage")),
                        _pdf_amount(item.get("remaining_amount")),
                        item.get("status") or "Unavailable",
                        _pdf_date(item.get("target_date")),
                    ]
                    for item in goal_rows
                ],
                [110, 75, 75, 65, 75, 80, 60],
                styles,
            )
        )
    else:
        story.append(Paragraph("No financial goals available.", styles["muted"]))

    story.append(Paragraph("7. Financial Health", styles["section"]))
    if health.get("available"):
        story.append(
            _pdf_summary_table(
                [
                    ("Score", f"{_pdf_number(health.get('score'))}/100"),
                    ("Grade", health.get("grade") or "Unavailable"),
                    ("Coverage", _pdf_percent(health.get("coverage"))),
                    ("Earned Points", _pdf_number(health.get("earned_points"))),
                    ("Available Weight", _pdf_number(health.get("available_weight"))),
                ],
                styles,
            )
        )
        components = health.get("components") or {}
        if components:
            story.append(Spacer(1, 8))
            story.append(
                _pdf_table(
                    [["Component", "Status", "Score", "Details"]]
                    + [
                        [
                            name.replace("_", " ").title(),
                            "Available" if component.get("available") else "Unavailable",
                            _pdf_number(component.get("score")),
                            component.get("message") or "",
                        ]
                        for name, component in components.items()
                    ],
                    [110, 80, 70, 280],
                    styles,
                )
            )
    else:
        story.append(Paragraph("Financial Health: Unavailable with the current data.", styles["muted"]))

    story.append(Paragraph("8. Unavailable Metrics", styles["section"]))
    unavailable = report_data.get("unavailable_metrics") or {}
    unavailable_rows = [["Metric", "Status", "Reason"]]
    for name, metric in unavailable.items():
        if isinstance(metric, dict) and not metric.get("available", False):
            unavailable_rows.append(
                [
                    name.replace("_", " ").title(),
                    "Unavailable",
                    metric.get("reason") or "No reliable data source exists.",
                ]
            )
    if len(unavailable_rows) > 1:
        story.append(_pdf_table(unavailable_rows, [150, 80, 310], styles))
    else:
        story.append(Paragraph("No additional unavailable metrics were reported.", styles["muted"]))

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=34,
        title="FinSight Financial Report",
        author="FinSight",
        pageCompression=0,
    )
    document.build(story, onFirstPage=_draw_pdf_header_footer, onLaterPages=_draw_pdf_header_footer)
    return buffer.getvalue()


@app.get("/reports/export/pdf")
def export_pdf_report():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    try:
        report_data = build_reporting_data(
            current_user_id(),
            request.args.get("start_date"),
            request.args.get("end_date"),
            investment_service=investment_service,
            goal_service=goal_service,
        )
    except ReportValidationError as error:
        return jsonify({"error": str(error)}), 400

    return Response(
        _build_pdf_report(report_data),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; filename=\"finsight_financial_report.pdf\""
            )
        },
    )


EXCEL_CURRENCY_FORMAT = '"INR" #,##0.00'
EXCEL_PERCENT_FORMAT = "0.00%"


def _excel_amount(value):
    number = _pdf_decimal(value)
    return "Unavailable" if number is None else float(number)


def _excel_percent(value):
    number = _pdf_decimal(value)
    return "Unavailable" if number is None else float(number) / 100


def _excel_number(value):
    number = _pdf_decimal(value)
    if number is None:
        return "Unavailable"
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _excel_count(value):
    number = _pdf_decimal(value)
    return 0 if number is None else int(number)


def _excel_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _excel_setup_sheet(workbook, name, title, report_data):
    worksheet = workbook.create_sheet(name)
    worksheet.sheet_view.showGridLines = False
    worksheet.merge_cells("A1:H1")
    worksheet["A1"] = "FinSight"
    worksheet["A1"].font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    worksheet["A1"].fill = PatternFill("solid", fgColor="091A2B")
    worksheet["A1"].alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 26

    worksheet.merge_cells("A2:H2")
    worksheet["A2"] = title
    worksheet["A2"].font = Font(name="Calibri", size=14, bold=True, color="138A70")
    worksheet["A2"].alignment = Alignment(vertical="center")
    worksheet.row_dimensions[2].height = 23

    worksheet["A3"] = "Reporting Period"
    worksheet["B3"] = _pdf_period(report_data)
    worksheet["A4"] = "Generated"
    worksheet["B4"] = datetime.now()
    worksheet["B4"].number_format = "mmmm d, yyyy h:mm AM/PM"
    for cell in (worksheet["A3"], worksheet["A4"]):
        cell.font = Font(bold=True, color="71808D")
    worksheet["B3"].alignment = Alignment(wrap_text=True)
    worksheet["B4"].alignment = Alignment(wrap_text=True)
    return worksheet


def _excel_section(worksheet, row, title, end_column):
    worksheet.merge_cells(
        start_row=row,
        start_column=1,
        end_row=row,
        end_column=end_column,
    )
    cell = worksheet.cell(row=row, column=1, value=title)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="138A70")
    cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[row].height = 20


def _excel_table(worksheet, row, headers, rows, number_formats=None):
    number_formats = number_formats or {}
    header_fill = PatternFill("solid", fgColor="091A2B")
    border = Border(
        left=Side(style="thin", color="DFE6E9"),
        right=Side(style="thin", color="DFE6E9"),
        top=Side(style="thin", color="DFE6E9"),
        bottom=Side(style="thin", color="DFE6E9"),
    )

    for column, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=row, column=column, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row_offset, values in enumerate(rows, start=1):
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(
                row=row + row_offset,
                column=column,
                value=_excel_value(value),
            )
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            if column in number_formats:
                cell.number_format = number_formats[column]

    return row + len(rows) + 1


def _excel_empty(worksheet, row, message, end_column):
    worksheet.merge_cells(
        start_row=row,
        start_column=1,
        end_row=row,
        end_column=end_column,
    )
    cell = worksheet.cell(row=row, column=1, value=message)
    cell.font = Font(italic=True, color="71808D")
    cell.alignment = Alignment(wrap_text=True)


def _excel_set_widths(worksheet, widths):
    for column, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(column)].width = width


def _excel_finalize(worksheet, freeze_panes):
    worksheet.freeze_panes = freeze_panes
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.page_setup.orientation = "landscape"


def _build_excel_report(report_data):
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.title = "FinSight Financial Report"
    workbook.properties.creator = "FinSight"

    expenses = report_data.get("expenses") or {}
    expense_summary = expenses.get("expense_summary") or {}
    budgets = report_data.get("budgets") or {}
    investments = report_data.get("investments") or {}
    investment_stats = investments.get("stats") or {}
    goals = report_data.get("goals") or {}
    health = report_data.get("financial_health") or {}

    summary = _excel_setup_sheet(workbook, "Summary", "Financial Report", report_data)
    _excel_section(summary, 6, "Expense Summary", 4)
    _excel_table(
        summary,
        7,
        ["Total Expenses", "Transaction Count", "Average Expense", "Largest Expense"],
        [[
            _excel_amount(expense_summary.get("total_expenses")),
            _excel_count(expense_summary.get("transaction_count")),
            _excel_amount(expense_summary.get("average_expense")),
            _excel_amount(expense_summary.get("largest_expense")),
        ]],
        {1: EXCEL_CURRENCY_FORMAT, 3: EXCEL_CURRENCY_FORMAT, 4: EXCEL_CURRENCY_FORMAT},
    )
    _excel_section(summary, 10, "Financial Health", 3)
    _excel_table(
        summary,
        11,
        ["Overall Score", "Grade", "Coverage"],
        [[
            _excel_number(health.get("score")),
            health.get("grade") or "Unavailable",
            _excel_percent(health.get("coverage")),
        ]],
        {3: EXCEL_PERCENT_FORMAT},
    )
    unavailable_rows = []
    for name, metric in (report_data.get("unavailable_metrics") or {}).items():
        if isinstance(metric, dict) and not metric.get("available", False):
            unavailable_rows.append([
                name.replace("_", " ").title(),
                "Unavailable",
                metric.get("reason") or "No reliable data source exists.",
            ])
    _excel_section(summary, 14, "Unavailable Metrics", 3)
    if unavailable_rows:
        _excel_table(summary, 15, ["Metric", "Status", "Reason"], unavailable_rows)
    else:
        _excel_empty(summary, 15, "No additional unavailable metrics were reported.", 3)
    _excel_set_widths(summary, [24, 32, 24, 24, 14, 14, 14, 14])
    _excel_finalize(summary, None)

    expense_sheet = _excel_setup_sheet(workbook, "Expense Analysis", "Expense Analysis", report_data)
    _excel_section(expense_sheet, 6, "Expense Summary", 4)
    _excel_table(
        expense_sheet,
        7,
        ["Total Expenses", "Transaction Count", "Average Expense", "Largest Expense"],
        [[
            _excel_amount(expense_summary.get("total_expenses")),
            _excel_count(expense_summary.get("transaction_count")),
            _excel_amount(expense_summary.get("average_expense")),
            _excel_amount(expense_summary.get("largest_expense")),
        ]],
        {1: EXCEL_CURRENCY_FORMAT, 3: EXCEL_CURRENCY_FORMAT, 4: EXCEL_CURRENCY_FORMAT},
    )
    _excel_section(expense_sheet, 10, "Category Analysis", 2)
    category_rows = [
        [item.get("category") or "Uncategorized", _excel_amount(item.get("amount"))]
        for item in (expenses.get("category_totals") or [])
    ]
    if category_rows:
        _excel_table(expense_sheet, 11, ["Category", "Amount"], category_rows, {2: EXCEL_CURRENCY_FORMAT})
    else:
        _excel_empty(expense_sheet, 11, "No expense data available for the selected period.", 2)
    monthly_start = 12 + len(category_rows)
    _excel_section(expense_sheet, monthly_start, "Monthly Analysis", 2)
    monthly_rows = [
        [item.get("month") or "Unknown", _excel_amount(item.get("amount"))]
        for item in (expenses.get("monthly_totals") or [])
    ]
    if monthly_rows:
        _excel_table(expense_sheet, monthly_start + 1, ["Month", "Amount"], monthly_rows, {2: EXCEL_CURRENCY_FORMAT})
    else:
        _excel_empty(expense_sheet, monthly_start + 1, "No monthly expense data available.", 2)
    _excel_set_widths(expense_sheet, [30, 22, 24, 24, 14, 14, 14, 14])
    _excel_finalize(expense_sheet, "A8")

    budget_sheet = _excel_setup_sheet(workbook, "Budget Summary", "Budget Summary - Current Snapshot", report_data)
    _excel_section(budget_sheet, 6, "Current Budget Snapshot", 5)
    _excel_table(
        budget_sheet,
        7,
        ["Total Budget", "Total Spent", "Total Remaining", "Overall Utilization", "Budget Count"],
        [[
            _excel_amount(budgets.get("total_budget")),
            _excel_amount(budgets.get("total_spent")),
            _excel_amount(budgets.get("total_remaining")),
            _excel_percent(budgets.get("overall_utilization")),
            _excel_count(budgets.get("budget_count")),
        ]],
        {
            1: EXCEL_CURRENCY_FORMAT,
            2: EXCEL_CURRENCY_FORMAT,
            3: EXCEL_CURRENCY_FORMAT,
            4: EXCEL_PERCENT_FORMAT,
        },
    )
    _excel_empty(budget_sheet, 10, "Budget data represents the current stored budget snapshot.", 6)
    _excel_section(budget_sheet, 12, "Budgets", 6)
    budget_rows = [
        [
            item.get("budget_name") or "Budget",
            item.get("category") or "Uncategorized",
            _excel_amount(item.get("budget_amount")),
            _excel_amount(item.get("spent_amount")),
            _excel_amount(item.get("remaining_amount")),
            item.get("status") or "Unavailable",
        ]
        for item in (budgets.get("budgets") or [])
    ]
    if budget_rows:
        _excel_table(
            budget_sheet,
            13,
            ["Budget Name", "Category", "Budget Amount", "Spent Amount", "Remaining Amount", "Status"],
            budget_rows,
            {3: EXCEL_CURRENCY_FORMAT, 4: EXCEL_CURRENCY_FORMAT, 5: EXCEL_CURRENCY_FORMAT},
        )
    else:
        _excel_empty(budget_sheet, 13, "No current budget data available.", 6)
    _excel_set_widths(budget_sheet, [26, 20, 18, 18, 20, 18, 14, 14])
    _excel_finalize(budget_sheet, "A8")

    investment_sheet = _excel_setup_sheet(workbook, "Investments", "Investments - Current Snapshot", report_data)
    _excel_section(investment_sheet, 6, "Current Portfolio Snapshot", 5)
    _excel_table(
        investment_sheet,
        7,
        ["Invested Value", "Current Value", "Absolute Return", "Return Percentage", "Holding Count"],
        [[
            _excel_amount(investment_stats.get("total_invested")),
            _excel_amount(investment_stats.get("current_value")),
            _excel_amount(investment_stats.get("absolute_return")),
            _excel_percent(investment_stats.get("return_percentage")),
            _excel_count(investments.get("holding_count")),
        ]],
        {
            1: EXCEL_CURRENCY_FORMAT,
            2: EXCEL_CURRENCY_FORMAT,
            3: EXCEL_CURRENCY_FORMAT,
            4: EXCEL_PERCENT_FORMAT,
        },
    )
    _excel_empty(investment_sheet, 10, "Investment data represents the current portfolio snapshot.", 7)
    _excel_section(investment_sheet, 12, "Holdings", 7)
    holding_rows = [
        [
            item.get("asset_name") or "Asset",
            item.get("asset_type") or "Unknown",
            item.get("quantity"),
            _excel_amount(item.get("purchase_price")),
            _excel_amount(item.get("current_value")),
            _excel_amount(item.get("invested_value")),
            item.get("purchase_date") or "Unavailable",
        ]
        for item in (investments.get("holdings") or [])
    ]
    if holding_rows:
        _excel_table(
            investment_sheet,
            13,
            ["Asset Name", "Asset Type", "Quantity", "Purchase Price", "Current Value", "Invested Value", "Purchase Date"],
            holding_rows,
            {4: EXCEL_CURRENCY_FORMAT, 5: EXCEL_CURRENCY_FORMAT, 6: EXCEL_CURRENCY_FORMAT},
        )
    else:
        _excel_empty(investment_sheet, 13, "No investment holdings available.", 7)
    allocation_start = 14 + len(holding_rows)
    _excel_section(investment_sheet, allocation_start, "Asset Allocation", 2)
    allocation_rows = [
        [item.get("asset_type") or "Unknown", _excel_percent(item.get("percentage"))]
        for item in (investment_stats.get("allocation") or [])
    ]
    if allocation_rows:
        _excel_table(investment_sheet, allocation_start + 1, ["Asset Type", "Allocation"], allocation_rows, {2: EXCEL_PERCENT_FORMAT})
    else:
        _excel_empty(investment_sheet, allocation_start + 1, "No asset allocation data available.", 2)
    _excel_set_widths(investment_sheet, [25, 18, 14, 18, 18, 18, 18, 14])
    _excel_finalize(investment_sheet, "A8")

    goal_sheet = _excel_setup_sheet(workbook, "Goals", "Goals - Current Progress", report_data)
    _excel_section(goal_sheet, 6, "Current Goal Progress", 7)
    goal_rows = [
        [
            item.get("goal_name") or "Goal",
            item.get("goal_category") or "Uncategorized",
            _excel_amount(item.get("target_amount")),
            _excel_amount(item.get("current_amount")),
            _excel_percent(item.get("progress_percentage")),
            _excel_amount(item.get("remaining_amount")),
            item.get("status") or "Unavailable",
        ]
        for item in (goals.get("goals") or [])
    ]
    if goal_rows:
        _excel_table(
            goal_sheet,
            7,
            ["Goal Name", "Category", "Target Amount", "Current Amount", "Progress Percentage", "Remaining Amount", "Status"],
            goal_rows,
            {
                3: EXCEL_CURRENCY_FORMAT,
                4: EXCEL_CURRENCY_FORMAT,
                5: EXCEL_PERCENT_FORMAT,
                6: EXCEL_CURRENCY_FORMAT,
            },
        )
    else:
        _excel_empty(goal_sheet, 7, "No financial goals available.", 7)
    _excel_set_widths(goal_sheet, [25, 18, 18, 18, 20, 20, 18, 14])
    _excel_finalize(goal_sheet, "A8")

    health_sheet = _excel_setup_sheet(workbook, "Financial Health", "Financial Health", report_data)
    _excel_section(health_sheet, 6, "Existing Financial Health Score", 5)
    if health.get("available"):
        _excel_table(
            health_sheet,
            7,
            ["Overall Score", "Grade", "Coverage", "Earned Points", "Available Weight"],
            [[
                _excel_number(health.get("score")),
                health.get("grade") or "Unavailable",
                _excel_percent(health.get("coverage")),
                _excel_number(health.get("earned_points")),
                _excel_number(health.get("available_weight")),
            ]],
            {3: EXCEL_PERCENT_FORMAT},
        )
        component_rows = [
            [
                name.replace("_", " ").title(),
                "Available" if component.get("available") else "Unavailable",
                _excel_number(component.get("score")),
                component.get("message") or "",
            ]
            for name, component in (health.get("components") or {}).items()
        ]
        _excel_section(health_sheet, 10, "Components", 4)
        if component_rows:
            _excel_table(health_sheet, 11, ["Component", "Status", "Score", "Message"], component_rows)
        else:
            _excel_empty(health_sheet, 11, "No Financial Health component details available.", 4)
    else:
        _excel_empty(health_sheet, 7, "Financial Health is unavailable with the current data.", 5)
    _excel_set_widths(health_sheet, [24, 18, 16, 70, 14, 14, 14, 14])
    _excel_finalize(health_sheet, "A8")

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@app.get("/reports/export/excel")
def export_excel_report():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    try:
        report_data = build_reporting_data(
            current_user_id(),
            request.args.get("start_date"),
            request.args.get("end_date"),
            investment_service=investment_service,
            goal_service=goal_service,
        )
    except ReportValidationError as error:
        return jsonify({"error": str(error)}), 400

    return Response(
        _build_excel_report(report_data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                "attachment; filename=\"finsight_financial_report.xlsx\""
            )
        },
    )


@app.route("/expense")
def expense():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    stats = get_summary_stats(current_user_id())
    return render_template(
        "expenses/dashboard.html",
        stats=stats,
        current_username=session["username"],
    )

@app.route("/budget")
@app.route("/budgets")
def budgets():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    search_query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "All")
    status_filter = request.args.get("status", "All")
    priority_filter = request.args.get("priority", "All")
    sort_by = request.args.get("sort", "newest")

    budget_rows = filter_budgets(
        current_user_id(),
        search_query=search_query,
        category_filter=category_filter,
        status_filter=status_filter,
        priority_filter=priority_filter,
        sort_by=sort_by,
    )
    stats = get_summary_stats(current_user_id())

    return render_template(
        "budgets/dashboard.html",
        budgets=budget_rows,
        stats=stats,
        search_query=search_query,
        category_filter=category_filter,
        status_filter=status_filter,
        priority_filter=priority_filter,
        sort_by=sort_by,
        current_username=session["username"],
        budget_csrf_token=budget_csrf_token(),
    )
@app.context_processor
def inject_template_globals():
    return {
        "today_date": datetime.now().strftime("%B %d, %Y"),
        "current_username": session.get("username", ""),
    }


def validate_budget_form(form):
    errors = []
    budget_name = form.get("budget_name", "").strip()
    category = form.get("category", "").strip()
    start_date = form.get("start_date", "").strip()
    end_date = form.get("end_date", "").strip()

    if not budget_name:
        errors.append("Budget name is required.")
    if not category:
        errors.append("Category is required.")

    try:
        if float(form.get("budget_amount", 0) or 0) < 0:
            errors.append("Budget amount cannot be negative.")
    except ValueError:
        errors.append("Budget amount must be a valid number.")

    try:
        if float(form.get("spent_amount", 0) or 0) < 0:
            errors.append("Spent amount cannot be negative.")
    except ValueError:
        errors.append("Spent amount must be a valid number.")

    if not start_date or not end_date:
        errors.append("Start date and end date are required.")
    elif start_date > end_date:
        errors.append("Start date cannot be later than end date.")

    return errors


def render_budget_form(budget=None, is_edit=False, budget_id=None):
    return render_template(
        "budgets/form.html",
        budget=budget or {},
        is_edit=is_edit,
        budget_id=budget_id,
        budget_csrf_token=budget_csrf_token(),
    )

@app.route("/budget/create", methods=["GET", "POST"])
def create_budget_route():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        if not budget_csrf_valid():
            flash("The form security token is missing or invalid.", "danger")
            return render_budget_form(request.form, is_edit=False), 400
        errors = validate_budget_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_budget_form(request.form, is_edit=False)

        try:
            create_budget(current_user_id(), request.form)
            flash("Budget created successfully.", "success")
            return redirect(url_for("budgets"))
        except Exception:
            app.logger.exception("Budget creation failed")
            flash(
                "Unable to create budget. Please check the form and try again.",
                "danger",
            )
            return render_budget_form(request.form, is_edit=False)

    return render_budget_form(is_edit=False)


@app.route("/budget/edit/<int:budget_id>", methods=["GET", "POST"])
def edit_budget(budget_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    budget = get_budget(budget_id, current_user_id())
    if not budget:
        flash("Budget not found.", "danger")
        return redirect(url_for("budgets"))

    if request.method == "POST":
        if not budget_csrf_valid():
            flash("The form security token is missing or invalid.", "danger")
            return render_budget_form(request.form, is_edit=True, budget_id=budget_id), 400
        errors = validate_budget_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_budget_form(request.form, is_edit=True, budget_id=budget_id)

        try:
            if update_budget(budget_id, current_user_id(), request.form):
                flash("Budget updated successfully.", "success")
                return redirect(url_for("budgets"))
            flash("Unable to update budget.", "danger")
        except Exception:
            app.logger.exception("Budget update failed")
            flash(
                "Unable to update budget. Please check the form and try again.",
                "danger",
            )

    return render_budget_form(budget=budget, is_edit=True, budget_id=budget_id)


@app.route("/budget/view/<int:budget_id>")
def view_budget(budget_id):
    if login_required_redirect():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    budget = get_budget(budget_id, current_user_id())
    if not budget:
        return jsonify({"success": False, "message": "Budget not found"}), 404

    return jsonify({"success": True, "budget": budget})


@app.post("/budget/delete/<int:budget_id>")
def remove_budget(budget_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not budget_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("budgets"))

    result = delete_budget(budget_id, current_user_id())

    if result:
        flash("Budget deleted successfully.", "success")
    else:
        flash("Budget not found.", "danger")

    return redirect(url_for("budgets"))


EXPENSE_CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Transportation",
    "Utilities",
    "Housing & Rent",
    "Healthcare",
    "Shopping",
    "Entertainment",
    "Travel",
    "Personal Care",
    "Education",
    "Subscriptions",
    "Other",
]

PAYMENT_MODES = [
    "Cash",
    "Credit Card",
    "Debit Card",
    "UPI",
    "Bank Transfer",
    "Wallet",
]


def validate_expense_form(form):
    errors = []
    category = form.get("category", "").strip()
    payment_mode = form.get("payment_mode", "").strip()
    expense_date = form.get("date", "").strip()

    try:
        amount = float(form.get("amount", 0) or 0)
        if amount <= 0:
            errors.append("Amount must be greater than zero.")
    except ValueError:
        errors.append("Amount must be a valid number.")

    if category not in EXPENSE_CATEGORIES:
        errors.append("Please select a valid category.")

    if payment_mode not in PAYMENT_MODES:
        errors.append("Please select a valid payment mode.")

    if not expense_date:
        errors.append("Date is required.")
    else:
        try:
            parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
            if parsed_date > datetime.now().date():
                errors.append("Date cannot be in the future.")
        except ValueError:
            errors.append("Date must be valid.")

    return errors


def render_expense_form(expense_row=None, is_edit=False, transaction_id=None):
    return render_template(
        "expenses/form.html",
        expense=expense_row or {},
        is_edit=is_edit,
        transaction_id=transaction_id,
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        expense_csrf_token=expense_csrf_token(),
    )


@app.route("/expenses")
def expenses():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    from db import get_expense_summary, get_transactions

    search_query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "All")
    payment_filter = request.args.get("payment", "All")
    sort_by = request.args.get("sort", "newest")

    expense_rows = get_transactions(
        current_user_id(),
        search_query=search_query,
        category_filter=category_filter,
        payment_filter=payment_filter,
        sort_by=sort_by,
    )
    stats = get_expense_summary(current_user_id())

    return render_template(
        "expenses/dashboard.html",
        expenses=expense_rows,
        stats=stats,
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        search_query=search_query,
        category_filter=category_filter,
        payment_filter=payment_filter,
        sort_by=sort_by,
        current_username=session["username"],
        expense_csrf_token=expense_csrf_token(),
    )


CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _csv_safe_text(value):
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return "'" + value
    return value


@app.get("/expenses/export")
def export_expenses():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    expense_rows = get_transactions(current_user_id())
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Description", "Payment Mode", "Type", "Amount"])

    for expense in expense_rows:
        writer.writerow(
            [
                _csv_safe_text(expense.get("date", "")),
                _csv_safe_text(expense.get("category", "")),
                _csv_safe_text(expense.get("description") or ""),
                _csv_safe_text(expense.get("payment_mode", "")),
                _csv_safe_text(expense.get("type", "")),
                expense.get("amount", ""),
            ]
        )

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        "attachment; filename=finsight_expenses.csv"
    )
    return response


@app.route("/expense/create", methods=["GET", "POST"])
def create_expense():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        if not expense_csrf_valid():
            flash("The form security token is missing or invalid.", "danger")
            return render_expense_form(request.form, is_edit=False), 400
        errors = validate_expense_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_expense_form(request.form, is_edit=False)

        try:
            from db import create_transaction

            create_transaction(current_user_id(), request.form)
            flash("Expense added successfully.", "success")
            return redirect(url_for("expenses"))
        except Exception:
            app.logger.exception("Expense creation failed")
            flash("Unable to add expense. Please check the form and try again.", "danger")
            return render_expense_form(request.form, is_edit=False)

    return render_expense_form(is_edit=False)


@app.route("/expense/edit/<int:transaction_id>", methods=["GET", "POST"])
def edit_expense(transaction_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    from db import get_transaction

    expense_row = get_transaction(transaction_id, current_user_id())
    if not expense_row:
        flash("Expense not found.", "danger")
        return redirect(url_for("expenses"))

    if request.method == "POST":
        if not expense_csrf_valid():
            flash("The form security token is missing or invalid.", "danger")
            return render_expense_form(
                request.form,
                is_edit=True,
                transaction_id=transaction_id,
            ), 400
        errors = validate_expense_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_expense_form(
                request.form,
                is_edit=True,
                transaction_id=transaction_id,
            )

        try:
            from db import update_transaction

            if update_transaction(transaction_id, current_user_id(), request.form):
                flash("Expense updated successfully.", "success")
                return redirect(url_for("expenses"))
            flash("Unable to update expense.", "danger")
        except Exception:
            app.logger.exception("Expense update failed")
            flash("Unable to update expense. Please check the form and try again.", "danger")

    return render_expense_form(
        expense_row=expense_row,
        is_edit=True,
        transaction_id=transaction_id,
    )


@app.route("/expense/view/<int:transaction_id>")
def view_expense(transaction_id):
    if login_required_redirect():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    from db import get_transaction

    expense_row = get_transaction(transaction_id, current_user_id())
    if not expense_row:
        return jsonify({"success": False, "message": "Expense not found"}), 404

    return jsonify({"success": True, "expense": expense_row})


@app.post("/expense/delete/<int:transaction_id>")
def delete_expense_route(transaction_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not expense_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("expenses"))

    from db import delete_transaction

    result = delete_transaction(transaction_id, current_user_id())
    if result:
        flash("Expense deleted successfully.", "success")
    else:
        flash("Expense not found.", "danger")

    return redirect(url_for("expenses"))


def render_investment_form(investment=None, is_edit=False, investment_id=None, errors=None):
    return render_template(
        "investments/form.html",
        investment=investment or {},
        is_edit=is_edit,
        investment_id=investment_id,
        asset_types=ASSET_TYPES,
        investment_errors=errors or [],
        investment_csrf_token=investment_csrf_token(),
    )


@app.route("/investments")
def investments():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    user_id = current_user_id()
    rows, stats = investment_service.list_for_user(user_id)
    goals = goal_service.list_for_user(user_id)
    return render_template(
        "investments/dashboard.html",
        investments=rows,
        stats=stats,
        goals=goals,
    )


@app.route("/investments/create", methods=["GET", "POST"])
def create_investment():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if request.method == "GET":
        return render_investment_form()
    if not investment_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_investment_form(request.form, errors=["Invalid form security token."]), 400

    try:
        created, errors = investment_service.create(current_user_id(), request.form)
    except Exception:
        app.logger.exception("Investment creation failed")
        flash("Unable to create investment. Please try again.", "danger")
        return render_investment_form(request.form), 503
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_investment_form(request.form, errors=errors), 400

    flash("Investment added successfully.", "success")
    return redirect(url_for("investments"))


@app.route("/investments/<int:investment_id>")
def view_investment(investment_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    investment = investment_service.get_for_user(investment_id, current_user_id())
    if not investment:
        flash("Investment not found.", "danger")
        return redirect(url_for("investments"))
    return render_template("investments/detail.html", investment=investment)


@app.route("/investments/<int:investment_id>/edit", methods=["GET", "POST"])
def edit_investment(investment_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    investment = investment_service.get_for_user(investment_id, current_user_id())
    if not investment:
        flash("Investment not found.", "danger")
        return redirect(url_for("investments"))
    if request.method == "GET":
        return render_investment_form(investment, True, investment_id)
    if not investment_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return render_investment_form(request.form, True, investment_id, ["Invalid form security token."]), 400

    try:
        updated, errors = investment_service.update(investment_id, current_user_id(), request.form)
    except Exception:
        app.logger.exception("Investment update failed")
        flash("Unable to update investment. Please try again.", "danger")
        return render_investment_form(request.form, True, investment_id), 503
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_investment_form(request.form, True, investment_id, errors), 400
    if not updated:
        flash("Investment not found.", "danger")
        return redirect(url_for("investments"))

    flash("Investment updated successfully.", "success")
    return redirect(url_for("investments"))


@app.post("/investments/<int:investment_id>/delete")
def delete_investment(investment_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not investment_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("investments"))

    deleted = investment_service.delete(investment_id, current_user_id())
    flash("Investment deleted successfully." if deleted else "Investment not found.",
          "success" if deleted else "danger")
    return redirect(url_for("investments"))


def render_goal_form(goal=None, is_edit=False, goal_id=None, errors=None):
    return render_template(
        "goals/form.html",
        goal=goal or {},
        is_edit=is_edit,
        goal_id=goal_id,
        goal_categories=GOAL_CATEGORIES,
        goal_errors=errors or [],
        goal_csrf_token=goal_csrf_token(),
    )


@app.route("/goals")
def goals():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    return render_template("goals/dashboard.html", goals=goal_service.list_for_user(current_user_id()))


@app.route("/goals/create", methods=["GET", "POST"])
def create_goal():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if request.method == "GET":
        return render_goal_form()
    if not goal_csrf_valid():
        return render_goal_form(request.form, errors=["Invalid form security token."]), 400

    created, errors = goal_service.create(current_user_id(), request.form)
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_goal_form(request.form, errors=errors), 400
    flash("Financial goal created successfully.", "success")
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>")
def view_goal(goal_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    goal = goal_service.get_for_user(goal_id, current_user_id())
    if not goal:
        flash("Goal not found.", "danger")
        return redirect(url_for("goals"))
    return render_template("goals/detail.html", goal=goal)


@app.route("/goals/<int:goal_id>/edit", methods=["GET", "POST"])
def edit_goal(goal_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    goal = goal_service.get_for_user(goal_id, current_user_id())
    if not goal:
        flash("Goal not found.", "danger")
        return redirect(url_for("goals"))
    if request.method == "GET":
        return render_goal_form(goal, True, goal_id)
    if not goal_csrf_valid():
        return render_goal_form(request.form, True, goal_id, ["Invalid form security token."]), 400

    updated, errors = goal_service.update(goal_id, current_user_id(), request.form)
    if errors:
        for error in errors:
            flash(error, "danger")
        return render_goal_form(request.form, True, goal_id, errors), 400
    if not updated:
        flash("Goal not found.", "danger")
        return redirect(url_for("goals"))
    flash("Financial goal updated successfully.", "success")
    return redirect(url_for("goals"))


@app.post("/goals/<int:goal_id>/delete")
def delete_goal(goal_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response
    if not goal_csrf_valid():
        flash("The form security token is missing or invalid.", "danger")
        return redirect(url_for("goals"))
    deleted = goal_service.delete(goal_id, current_user_id())
    flash("Goal deleted successfully." if deleted else "Goal not found.",
          "success" if deleted else "danger")
    return redirect(url_for("goals"))


if __name__ == "__main__":
    app.run(debug=_debug_enabled())
