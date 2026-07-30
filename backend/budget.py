"""
app.py - Main Flask Application & Controller Routes
Manages routes for Page 1 (Budget Dashboard) and Page 2 (Create/Edit Budget),
form processing, server-side validation, session handling, and API endpoints.
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import budget_db as db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "luxury_fintech_secret_key_2026_super_secure")

# Initialize DB tables on application start
with app.app_context():
    db.init_db()

def get_current_user_id():
    """
    Helper function to ensure seamless integration with pre-existing Flask session authentication.
    If session['user_id'] is set, returns it. Otherwise defaults to user_id=1 (alex_fintech demo user).
    """
    if 'user_id' not in session:
        session['user_id'] = 1
        session['username'] = 'alex_fintech'
    return session['user_id']

@app.context_processor
def inject_global_vars():
    """Injects current date and user session metadata to all Jinja templates."""
    today_formatted = datetime.now().strftime("%B %d, %Y")
    return dict(
        today_date=today_formatted,
        current_username=session.get('username', 'alex_fintech')
    )

@app.route('/')
def index():
    """Root route redirecting directly to the Budget Dashboard."""
    return redirect(url_for('budget_dashboard'))

@app.route('/budget', methods=['GET'])
def budget_dashboard():
    """
    PAGE 1: Budget Dashboard
    Displays welcome header, financial motivational quote, today's date,
    glass summary metric cards, previously created budgets list, search/filter inputs, and empty state.
    """
    user_id = get_current_user_id()
    
    # Fetch filter parameters from query string (if provided)
    search_q = request.args.get('q', '').strip()
    cat_filter = request.args.get('category', 'All')
    status_filter = request.args.get('status', 'All')
    priority_filter = request.args.get('priority', 'All')
    sort_by = request.args.get('sort', 'newest')

    if search_q or cat_filter != 'All' or status_filter != 'All' or priority_filter != 'All' or sort_by != 'newest':
        budgets = db.filter_budget(
            user_id=user_id,
            category=cat_filter,
            status=status_filter,
            priority=priority_filter,
            search_term=search_q,
            sort_by=sort_by
        )
    else:
        budgets = db.get_all_budgets(user_id)

    stats = db.get_summary_stats(user_id)

    return render_template(
        'dashboard.html',
        budgets=budgets,
        stats=stats,
        search_query=search_q,
        category_filter=cat_filter,
        status_filter=status_filter,
        priority_filter=priority_filter,
        sort_by=sort_by
    )

@app.route('/budget/create', methods=['GET', 'POST'])
def create_budget():
    """
    PAGE 2: Create Budget
    Renders the luxury budget creation form (GET) and processes input insertion (POST).
    Includes complete server-side input validation.
    """
    user_id = get_current_user_id()

    if request.method == 'POST':
        # Retrieve form data
        budget_name = request.form.get('budget_name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        budget_amount = request.form.get('budget_amount', '').strip()
        spent_amount = request.form.get('spent_amount', '0').strip()
        currency = request.form.get('currency', 'USD').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        priority = request.form.get('priority', 'Medium').strip()
        status = request.form.get('status', 'Active').strip()
        expected_income = request.form.get('expected_income', '0').strip()
        expected_expenses = request.form.get('expected_expenses', '0').strip()
        savings_goal = request.form.get('savings_goal', '0').strip()
        alert_percentage = request.form.get('alert_percentage', '80').strip()
        color_label = request.form.get('color_label', '#0E5A4E').strip()
        budget_icon = request.form.get('budget_icon', 'fa-wallet').strip()
        is_recurring = request.form.get('is_recurring')
        notes = request.form.get('notes', '').strip()

        # Server-Side Validation Errors Collection
        errors = []
        if not budget_name:
            errors.append("Budget Name is required.")
        if not category:
            errors.append("Please select a valid Category.")
        
        try:
            b_amt = float(budget_amount)
            if b_amt < 0:
                errors.append("Budget Amount must be greater than or equal to 0.")
        except (ValueError, TypeError):
            errors.append("Budget Amount must be a valid number.")

        try:
            s_amt = float(spent_amount) if spent_amount else 0.0
            if s_amt < 0:
                errors.append("Spent Amount cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Spent Amount must be a valid number.")

        if not start_date or not end_date:
            errors.append("Both Start Date and End Date are required.")
        elif start_date > end_date:
            errors.append("Start Date cannot be after End Date.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('form.html', budget=request.form, is_edit=False)

        # Form data dict for DB insertion
        form_payload = {
            "budget_name": budget_name,
            "description": description,
            "category": category,
            "budget_amount": b_amt,
            "spent_amount": s_amt,
            "currency": currency,
            "start_date": start_date,
            "end_date": end_date,
            "priority": priority,
            "status": status,
            "expected_income": expected_income,
            "expected_expenses": expected_expenses,
            "savings_goal": savings_goal,
            "alert_percentage": alert_percentage,
            "color_label": color_label,
            "budget_icon": budget_icon,
            "is_recurring": is_recurring,
            "notes": notes
        }

        try:
            db.create_budget(user_id, form_payload)
            flash("Budget created successfully!", "success")
            return redirect(url_for('budget_dashboard'))
        except Exception as e:
            flash(f"Error saving budget: {str(e)}", "danger")
            return render_template('form.html', budget=request.form, is_edit=False)

    # GET Request: Render empty form
    return render_template('form.html', budget={}, is_edit=False)

@app.route('/budget/edit/<int:budget_id>', methods=['GET', 'POST'])
def edit_budget(budget_id):
    """
    PAGE 2: Edit Budget
    Loads pre-filled values of an existing budget (GET) and updates PostgreSQL record (POST).
    """
    user_id = get_current_user_id()
    existing_budget = db.get_budget(budget_id, user_id)

    if not existing_budget:
        flash("Budget not found or unauthorized access.", "danger")
        return redirect(url_for('budget_dashboard'))

    if request.method == 'POST':
        budget_name = request.form.get('budget_name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        budget_amount = request.form.get('budget_amount', '').strip()
        spent_amount = request.form.get('spent_amount', '0').strip()
        currency = request.form.get('currency', 'USD').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        priority = request.form.get('priority', 'Medium').strip()
        status = request.form.get('status', 'Active').strip()
        expected_income = request.form.get('expected_income', '0').strip()
        expected_expenses = request.form.get('expected_expenses', '0').strip()
        savings_goal = request.form.get('savings_goal', '0').strip()
        alert_percentage = request.form.get('alert_percentage', '80').strip()
        color_label = request.form.get('color_label', '#0E5A4E').strip()
        budget_icon = request.form.get('budget_icon', 'fa-wallet').strip()
        is_recurring = request.form.get('is_recurring')
        notes = request.form.get('notes', '').strip()

        errors = []
        if not budget_name:
            errors.append("Budget Name is required.")
        if not category:
            errors.append("Category is required.")
        try:
            b_amt = float(budget_amount)
            s_amt = float(spent_amount) if spent_amount else 0.0
        except ValueError:
            errors.append("Amounts must be valid numeric values.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('form.html', budget=request.form, is_edit=True, budget_id=budget_id)

        form_payload = {
            "budget_name": budget_name,
            "description": description,
            "category": category,
            "budget_amount": b_amt,
            "spent_amount": s_amt,
            "currency": currency,
            "start_date": start_date,
            "end_date": end_date,
            "priority": priority,
            "status": status,
            "expected_income": expected_income,
            "expected_expenses": expected_expenses,
            "savings_goal": savings_goal,
            "alert_percentage": alert_percentage,
            "color_label": color_label,
            "budget_icon": budget_icon,
            "is_recurring": is_recurring,
            "notes": notes
        }

        success = db.update_budget(budget_id, user_id, form_payload)
        if success:
            flash("Budget updated successfully!", "success")
            return redirect(url_for('budget_dashboard'))
        else:
            flash("Failed to update budget. Please try again.", "danger")
            return render_template('form.html', budget=request.form, is_edit=True, budget_id=budget_id)

    # GET Request: Pre-fill form with existing budget values
    return render_template('form.html', budget=existing_budget, is_edit=True, budget_id=budget_id)

@app.route('/budget/view/<int:budget_id>', methods=['GET'])
def view_budget(budget_id):
    """
    API Endpoint for Page 1 View Modal.
    Returns JSON format of specified budget details.
    """
    user_id = get_current_user_id()
    budget = db.get_budget(budget_id, user_id)
    if not budget:
        return jsonify({"success": False, "message": "Budget not found"}), 404
    return jsonify({"success": True, "budget": budget})

@app.route('/budget/delete/<int:budget_id>', methods=['POST', 'GET'])
def delete_budget(budget_id):
    """
    Deletes specified budget record and redirects to dashboard.
    """
    user_id = get_current_user_id()
    success = db.delete_budget(budget_id, user_id)
    if success:
        flash("Budget deleted successfully.", "success")
    else:
        flash("Unable to delete budget.", "danger")
    return redirect(url_for('budget_dashboard'))

@app.route('/budget/duplicate/<int:budget_id>', methods=['POST', 'GET'])
def duplicate_budget(budget_id):
    """
    Duplicates specified budget record.
    """
    user_id = get_current_user_id()
    new_id = db.duplicate_budget(budget_id, user_id)
    if new_id:
        flash("Budget duplicated successfully!", "success")
    else:
        flash("Failed to duplicate budget.", "danger")
    return redirect(url_for('budget_dashboard'))

@app.route('/budget/archive/<int:budget_id>', methods=['POST', 'GET'])
def archive_budget(budget_id):
    """
    Archives specified budget record.
    """
    user_id = get_current_user_id()
    success = db.archive_budget(budget_id, user_id)
    if success:
        flash("Budget moved to archive.", "info")
    else:
        flash("Failed to archive budget.", "danger")
    return redirect(url_for('budget_dashboard'))

@app.route('/budget/search', methods=['GET'])
def search_budget_api():
    """
    Real-time AJAX Search API Endpoint.
    Returns filtered JSON list of budgets.
    """
    user_id = get_current_user_id()
    q = request.args.get('q', '').strip()
    cat = request.args.get('category', 'All')
    status = request.args.get('status', 'All')
    priority = request.args.get('priority', 'All')
    sort_by = request.args.get('sort', 'newest')

    filtered = db.filter_budget(
        user_id=user_id,
        category=cat,
        status=status,
        priority=priority,
        search_term=q,
        sort_by=sort_by
    )
    return jsonify({"success": True, "budgets": filtered})

if __name__ == '__main__':
    # Run development server on port 5000
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
