from datetime import date
from decimal import Decimal, InvalidOperation

from db import (
    filter_budgets,
    get_connection,
    get_expense_summary,
    get_summary_stats,
    serialize_row,
    serialize_rows,
)
from financial_health_service import calculate_financial_health


class ReportValidationError(ValueError):
    """Raised when a reporting date range is not valid."""


def parse_report_date_range(start_date=None, end_date=None):
    """Return an optional inclusive date range for reporting queries."""
    start = _parse_report_date(start_date, "start_date")
    end = _parse_report_date(end_date, "end_date")

    if (start is None) != (end is None):
        raise ReportValidationError(
            "Both start_date and end_date are required together."
        )
    if start is not None and start > end:
        raise ReportValidationError("start_date cannot be later than end_date.")

    return start, end


def _parse_report_date(value, field_name):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ReportValidationError(
            f"{field_name} must use YYYY-MM-DD format."
        ) from None


def _expense_filter(user_id, start_date, end_date):
    clauses = ["user_id = %s", "type = 'Expense'"]
    params = [user_id]
    if start_date is not None:
        clauses.append("date >= %s")
        params.append(start_date)
    if end_date is not None:
        clauses.append("date <= %s")
        params.append(end_date)
    return " AND ".join(clauses), tuple(params)


def get_expense_report(user_id, start_date=None, end_date=None):
    """Return SQL-aggregated, user-scoped expense data for an optional range."""
    start_date, end_date = parse_report_date_range(start_date, end_date)
    where_sql, params = _expense_filter(user_id, start_date, end_date)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    COUNT(*) AS transaction_count,
                    COALESCE(SUM(amount), 0) AS total_expenses,
                    COALESCE(AVG(amount), 0) AS average_expense,
                    COALESCE(MAX(amount), 0) AS largest_expense,
                    COUNT(*) FILTER (
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                        AND date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    ) AS month_expenses,
                    COALESCE(SUM(amount) FILTER (
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                        AND date < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    ), 0) AS month_spent
                FROM transactions
                WHERE {where_sql}
                """,
                params,
            )
            summary = serialize_row(cursor.fetchone()) or {}

            cursor.execute(
                f"""
                SELECT category, COALESCE(SUM(amount), 0) AS amount
                FROM transactions
                WHERE {where_sql}
                GROUP BY category
                ORDER BY amount DESC, category ASC
                """,
                params,
            )
            category_rows = serialize_rows(cursor.fetchall())

            cursor.execute(
                f"""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
                    COALESCE(SUM(amount), 0) AS amount
                FROM transactions
                WHERE {where_sql}
                GROUP BY DATE_TRUNC('month', date)
                ORDER BY DATE_TRUNC('month', date) ASC
                """,
                params,
            )
            monthly_rows = serialize_rows(cursor.fetchall())

    return {
        "date_range": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "expense_summary": {
            "total_expenses": _number(summary.get("total_expenses")),
            "transaction_count": int(summary.get("transaction_count") or 0),
            "average_expense": _number(summary.get("average_expense")),
            "largest_expense": _number(summary.get("largest_expense")),
            "month_expenses": int(summary.get("month_expenses") or 0),
            "month_spent": _number(summary.get("month_spent")),
        },
        "category_totals": [
            {
                "category": row.get("category") or "Uncategorized",
                "amount": _number(row.get("amount")),
            }
            for row in category_rows
        ],
        "monthly_totals": [
            {
                "month": row.get("month"),
                "amount": _number(row.get("amount")),
            }
            for row in monthly_rows
        ],
    }


def get_budget_snapshot(user_id):
    """Return the current stored budget state; no date-range reinterpretation."""
    stats = get_summary_stats(user_id) or {}
    rows = filter_budgets(user_id) or []
    total_budget = _number(stats.get("total_allocated"))
    total_spent = _number(stats.get("total_spent"))
    overall_utilization = (
        (total_spent / total_budget * 100) if total_budget > 0 else None
    )

    budgets = []
    for row in rows:
        budgets.append(
            {
                "budget_name": row.get("budget_name"),
                "category": row.get("category"),
                "budget_amount": _number(row.get("budget_amount")),
                "spent_amount": _number(row.get("spent_amount")),
                "remaining_amount": _number(row.get("remaining_amount")),
                "status": row.get("status"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
            }
        )

    return {
        "scope": "current",
        "date_range_applied": False,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": _number(stats.get("total_remaining")),
        "overall_utilization": overall_utilization,
        "budget_count": int(stats.get("total_budgets") or len(budgets)),
        "budgets": budgets,
    }


def get_investment_snapshot(user_id, investment_service):
    """Reuse the existing investment service for a current portfolio snapshot."""
    holdings, stats = investment_service.list_for_user(user_id)
    return {
        "scope": "current",
        "date_range_applied": False,
        "holding_count": len(holdings),
        "holdings": _json_safe(holdings),
        "stats": _json_safe(stats),
    }


def get_goal_snapshot(user_id, goal_service):
    """Reuse the existing goal service for current progress values."""
    goals = goal_service.list_for_user(user_id)
    return {
        "scope": "current",
        "date_range_applied": False,
        "goal_count": len(goals),
        "goals": _json_safe(goals),
    }


def get_financial_health_snapshot(
    budget_snapshot,
    expense_summary,
    goal_snapshot,
    investment_snapshot,
):
    """Reuse the existing Financial Health formula for a current snapshot."""
    goals = goal_snapshot.get("goals", [])
    total_current = sum(
        (Decimal(str(goal.get("current_amount") or 0)) for goal in goals),
        Decimal("0"),
    )
    total_target = sum(
        (Decimal(str(goal.get("target_amount") or 0)) for goal in goals),
        Decimal("0"),
    )
    result = calculate_financial_health(
        budget_data={
            "total_allocated": budget_snapshot.get("total_budget"),
            "total_spent": budget_snapshot.get("total_spent"),
        },
        spending_data={
            "total_spent": expense_summary.get("total_expenses"),
            "average_expense": expense_summary.get("average_expense"),
            "largest_expense": expense_summary.get("largest_expense"),
            "expense_count": expense_summary.get("transaction_count"),
            "month_spent": expense_summary.get("month_spent"),
            "month_expenses": expense_summary.get("month_expenses"),
        },
        goal_data={
            "total_current": total_current,
            "total_target": total_target,
        },
        investment_data={
            "return_percentage": investment_snapshot.get("stats", {}).get(
                "return_percentage"
            ),
        },
    )
    return _json_safe(result)


def unavailable_metrics():
    return {
        "total_income": _unavailable("No reliable actual income data source exists."),
        "total_savings": _unavailable("No reliable actual savings balance exists."),
        "net_worth": _unavailable(
            "No reliable net worth source with complete cash, liability, debt, and asset balances exists."
        ),
        "income_vs_expenses": _unavailable(
            "Actual income data is required for an income-versus-expenses comparison."
        ),
        "historical_investment_performance": _unavailable(
            "Historical investment valuation records do not exist."
        ),
        "historical_goal_progress": _unavailable(
            "Historical goal contribution records do not exist."
        ),
        "recent_alerts": _unavailable(
            "No persisted notification or alert data source exists."
        ),
    }


def build_reporting_data(
    user_id,
    start_date=None,
    end_date=None,
    *,
    investment_service,
    goal_service,
):
    """Assemble the reusable, read-only reporting data contract."""
    start_date, end_date = parse_report_date_range(start_date, end_date)
    expense_report = get_expense_report(user_id, start_date, end_date)
    budget_snapshot = get_budget_snapshot(user_id)
    investment_snapshot = get_investment_snapshot(user_id, investment_service)
    goal_snapshot = get_goal_snapshot(user_id, goal_service)

    if start_date is None and end_date is None:
        health_expenses = expense_report["expense_summary"]
    else:
        current_expenses = get_expense_summary(user_id)
        health_expenses = {
            "total_expenses": current_expenses.get("total_spent"),
            "transaction_count": current_expenses.get("total_expenses"),
            "average_expense": current_expenses.get("average_expense"),
            "largest_expense": current_expenses.get("largest_expense"),
            "month_expenses": current_expenses.get("month_expenses"),
            "month_spent": current_expenses.get("month_spent"),
        }

    return {
        "date_range": expense_report["date_range"],
        "expenses": expense_report,
        "budgets": budget_snapshot,
        "investments": investment_snapshot,
        "goals": goal_snapshot,
        "financial_health": get_financial_health_snapshot(
            budget_snapshot,
            health_expenses,
            goal_snapshot,
            investment_snapshot,
        ),
        "unavailable_metrics": unavailable_metrics(),
    }


def _number(value):
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0
    return float(number)


def _unavailable(reason):
    return {"available": False, "value": None, "reason": reason}


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
