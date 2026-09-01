from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


BUDGET_WEIGHT = Decimal("35")
SPENDING_WEIGHT = Decimal("20")
GOAL_WEIGHT = Decimal("25")
INVESTMENT_WEIGHT = Decimal("20")
TOTAL_WEIGHT = Decimal("100")


def _to_decimal(value):
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _clamp(value, minimum=Decimal("0"), maximum=Decimal("100")):
    return max(minimum, min(value, maximum))


def _round_score(value):
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def get_health_grade(score):
    if score is None:
        return "Insufficient Data"

    score = Decimal(str(score))

    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"

    return "Needs Improvement"


def calculate_budget_score(total_allocated, total_spent):
    """
    Calculate the Budget Management component.

    Weight: 35 points.

    Uses the existing budget module's allocated and spent values.
    """
    allocated = _to_decimal(total_allocated)
    spent = _to_decimal(total_spent)

    if allocated is None or spent is None or allocated <= 0:
        return {
            "available": False,
            "score": Decimal("0"),
            "weight": BUDGET_WEIGHT,
            "percentage": None,
            "message": "Budget data is not available.",
        }

    spent = max(spent, Decimal("0"))

    utilization = (spent / allocated) * Decimal("100")

    if utilization <= 80:
        score = BUDGET_WEIGHT
        message = "Budget usage is within a healthy range."
    elif utilization <= 90:
        score = BUDGET_WEIGHT * Decimal("0.80")
        message = "Budget usage is moderately high."
    elif utilization <= 100:
        score = BUDGET_WEIGHT * Decimal("0.50")
        message = "Budget usage is close to the allocated limit."
    else:
        score = Decimal("0")
        message = "Budget spending has exceeded the allocated amount."

    return {
        "available": True,
        "score": score,
        "weight": BUDGET_WEIGHT,
        "percentage": utilization,
        "message": message,
    }

# spending Score
def calculate_spending_score(
    total_spending=None,
    average_expense=None,
    largest_expense=None,
    expense_count=None,
    month_spent=None,
    month_expenses=None,
):
    """
    Calculate the Spending Discipline component.

    Weight: 20 points.

    This component intentionally does not use income assumptions.
    It evaluates the quality and consistency of available expense data.

    The score is conservative when only limited transaction history exists.
    """

    total = _to_decimal(total_spending)
    average = _to_decimal(average_expense)
    largest = _to_decimal(largest_expense)
    count = _to_decimal(expense_count)
    monthly_total = _to_decimal(month_spent)
    monthly_count = _to_decimal(month_expenses)

    if (
        total is None
        or average is None
        or largest is None
        or count is None
        or count <= 0
    ):
        return {
            "available": False,
            "score": Decimal("0"),
            "weight": SPENDING_WEIGHT,
            "percentage": None,
            "message": "Expense data is not sufficient to evaluate spending discipline.",
        }

    # Start with a neutral baseline.
    score = Decimal("10")

    # 1. Expense concentration.
    # A very large single expense relative to total spending can indicate
    # concentrated spending. This is only one indicator, not a judgment
    # about whether the purchase itself was necessary.
    if total > 0:
        largest_ratio = (largest / total) * Decimal("100")

        if largest_ratio <= 20:
            score += Decimal("4")
        elif largest_ratio <= 35:
            score += Decimal("3")
        elif largest_ratio <= 50:
            score += Decimal("2")
        else:
            score += Decimal("1")

    # 2. Average expense relative to the largest expense.
    # A very concentrated transaction pattern gets fewer points.
    if largest > 0:
        average_ratio = (average / largest) * Decimal("100")

        if average_ratio >= 40:
            score += Decimal("3")
        elif average_ratio >= 25:
            score += Decimal("2")
        else:
            score += Decimal("1")

    # 3. Recent transaction availability.
    # We don't judge a month as "good" or "bad" solely by its amount.
    # We only reward having enough recent data to make the analysis useful.
    if (
        monthly_total is not None
        and monthly_count is not None
        and monthly_count > 0
    ):
        score += Decimal("3")

    score = min(score, SPENDING_WEIGHT)

    # Data sufficiency safeguard.
    # With very little transaction history, avoid presenting a strong
    # spending-discipline conclusion.
    if count < 3:
        score = min(score, Decimal("12"))
        message = "Limited expense history; spending discipline is estimated conservatively."
    elif count < 5:
        score = min(score, Decimal("16"))
        message = "Spending discipline is based on a limited transaction history."
    else:
        message = "Spending discipline is based on available expense behaviour."

    return {
        "available": True,
        "score": score,
        "weight": SPENDING_WEIGHT,
        "percentage": (score / SPENDING_WEIGHT) * Decimal("100"),
        "message": message,
    }

# Goal Score 
def calculate_goal_score(total_current, total_target):
    """
    Calculate the Goal Progress component.

    Weight: 25 points.

    Uses weighted aggregate progress:

        SUM(current_amount) / SUM(target_amount) * 100
    """
    current = _to_decimal(total_current)
    target = _to_decimal(total_target)

    if current is None or target is None or target <= 0:
        return {
            "available": False,
            "score": Decimal("0"),
            "weight": GOAL_WEIGHT,
            "percentage": None,
            "message": "Goal data is not available.",
        }

    current = max(current, Decimal("0"))

    progress = _clamp((current / target) * Decimal("100"))

    score = GOAL_WEIGHT * (progress / Decimal("100"))

    return {
        "available": True,
        "score": score,
        "weight": GOAL_WEIGHT,
        "percentage": progress,
        "message": "Goal progress is based on the combined progress of available financial goals.",
    }

# Investment Score 
def calculate_investment_score(return_percentage):
    """
    Calculate the Investment Performance component.

    Weight: 20 points.

    This uses the existing M2 portfolio return calculation.
    """
    return_value = _to_decimal(return_percentage)

    if return_value is None:
        return {
            "available": False,
            "score": Decimal("0"),
            "weight": INVESTMENT_WEIGHT,
            "percentage": None,
            "message": "Investment performance is not available until portfolio valuation is complete.",
        }

    if return_value >= 10:
        score = Decimal("20")
    elif return_value >= 5:
        score = Decimal("15")
    elif return_value >= 0:
        score = Decimal("10")
    else:
        score = Decimal("0")

    return {
        "available": True,
        "score": score,
        "weight": INVESTMENT_WEIGHT,
        "percentage": return_value,
        "message": "Investment performance is based on the portfolio return currently available.",
    }


def calculate_final_score(components):
    """
    Combine only available components and normalize them to 100.

    This prevents an unavailable component from automatically contributing
    zero points to the user's score.
    """
    earned_points = Decimal("0")
    available_weight = Decimal("0")

    for component in components.values():
        if not component or not component.get("available"):
            continue

        earned_points += _to_decimal(component.get("score")) or Decimal("0")
        available_weight += _to_decimal(component.get("weight")) or Decimal("0")

    if available_weight <= 0:
        return {
            "available": False,
            "score": None,
            "grade": "Insufficient Data",
            "earned_points": Decimal("0"),
            "available_weight": Decimal("0"),
            "coverage": Decimal("0"),
        }

    normalized_score = (earned_points / available_weight) * Decimal("100")
    normalized_score = _clamp(normalized_score)
    rounded_score = _round_score(normalized_score)

    coverage = (available_weight / TOTAL_WEIGHT) * Decimal("100")

    return {
        "available": True,
        "score": rounded_score,
        "grade": get_health_grade(rounded_score),
        "earned_points": earned_points,
        "available_weight": available_weight,
        "coverage": coverage,
    }


def calculate_financial_health(
    *,
    budget_data,
    spending_data,
    goal_data,
    investment_data,
):
    """
    Calculate the complete Financial Health Score.

    Returns individual component results plus the final normalized score.
    """
# budget Score 
    budget = calculate_budget_score(
        budget_data.get("total_allocated"),
        budget_data.get("total_spent"),
    )

    spending = calculate_spending_score(
        total_spending=spending_data.get("total_spent"),
        average_expense=spending_data.get("average_expense"),
        largest_expense=spending_data.get("largest_expense"),
        expense_count=spending_data.get("expense_count"),
        month_spent=spending_data.get("month_spent"),
        month_expenses=spending_data.get("month_expenses"),
    )
    
   

    print("DEBUG SPENDING RESULT:", spending)
    goals = calculate_goal_score(
        goal_data.get("total_current"),
        goal_data.get("total_target"),
    )

    investments = calculate_investment_score(
        investment_data.get("return_percentage"),
    )

    components = {
        "budget": budget,
        "spending": spending,
        "goals": goals,
        "investments": investments,
    }

    final = calculate_final_score(components)

    return {
        "score": final["score"],
        "grade": final["grade"],
        "available": final["available"],
        "earned_points": final["earned_points"],
        "available_weight": final["available_weight"],
        "coverage": final["coverage"],
        "components": components,
    }