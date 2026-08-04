from datetime import datetime

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import Config
from db import (
    create_budget,
    delete_budget,
    filter_budgets,
    get_budget,
    get_summary_stats,
    init_db,
    login_user,
    register_user,
    update_budget,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY or "finsight-dev-secret-key"

init_db()


def login_required_redirect():
    if not session.get("uid"):
        return redirect(url_for("login"))
    return None


def current_user_id():
    return session["uid"]


@app.route("/")
def home():
    if session.get("uid"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        success, user = login_user(email, password)
        if success:
            session.clear()
            session["uid"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html", error=None)


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
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    stats = get_summary_stats(current_user_id())
    return render_template(
        "main_dashboard.html",
        stats=stats,
        current_username=session["username"],
    )


@app.route("/expense")
def expense():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    stats = get_summary_stats(current_user_id())
    return render_template(
        "expense.jsx",
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
        "budget_dashboard.html",
        budgets=budget_rows,
        stats=stats,
        search_query=search_query,
        category_filter=category_filter,
        status_filter=status_filter,
        priority_filter=priority_filter,
        sort_by=sort_by,
        current_username=session["username"],
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
        "budget_form.html",
        budget=budget or {},
        is_edit=is_edit,
        budget_id=budget_id,
    )

@app.route("/budget/create", methods=["GET", "POST"])
def create_budget_route():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
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
    if not session.get("uid"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    budget = get_budget(budget_id, current_user_id())
    if not budget:
        return jsonify({"success": False, "message": "Budget not found"}), 404

    return jsonify({"success": True, "budget": budget})


@app.route("/budget/delete/<int:budget_id>", methods=["GET", "POST"])
def remove_budget(budget_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

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
        "expense_form.html",
        expense=expense_row or {},
        is_edit=is_edit,
        transaction_id=transaction_id,
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
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
        "expense_dashboard.html",
        expenses=expense_rows,
        stats=stats,
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        search_query=search_query,
        category_filter=category_filter,
        payment_filter=payment_filter,
        sort_by=sort_by,
        current_username=session["username"],
    )


@app.route("/expense/create", methods=["GET", "POST"])
def create_expense():
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    if request.method == "POST":
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
    if not session.get("uid"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    from db import get_transaction

    expense_row = get_transaction(transaction_id, current_user_id())
    if not expense_row:
        return jsonify({"success": False, "message": "Expense not found"}), 404

    return jsonify({"success": True, "expense": expense_row})


@app.route("/expense/delete/<int:transaction_id>", methods=["GET", "POST"])
def delete_expense_route(transaction_id):
    redirect_response = login_required_redirect()
    if redirect_response:
        return redirect_response

    from db import delete_transaction

    result = delete_transaction(transaction_id, current_user_id())
    if result:
        flash("Expense deleted successfully.", "success")
    else:
        flash("Expense not found.", "danger")

    return redirect(url_for("expenses"))


if __name__ == "__main__":
    app.run(debug=True)
