from decimal import Decimal

from financial_health_service import (
    calculate_budget_score,
    calculate_financial_health,
    calculate_final_score,
    calculate_goal_score,
    calculate_investment_score,
    calculate_spending_score,
    get_health_grade,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(
            f"{message}: expected {expected!r}, got {actual!r}"
        )


def test_budget_score():
    result = calculate_budget_score(
        total_allocated=10000,
        total_spent=7000,
    )

    assert_equal(result["available"], True, "Budget availability")
    assert_equal(result["score"], Decimal("35"), "Budget score")
    assert_equal(result["percentage"], Decimal("70"), "Budget utilization")


def test_budget_over_limit():
    result = calculate_budget_score(
        total_allocated=10000,
        total_spent=12000,
    )

    assert_equal(result["score"], Decimal("0"), "Over-budget score")


def test_spending_score_with_sufficient_history():
    result = calculate_spending_score(
        total_spending=7000,
        average_expense=700,
        largest_expense=1500,
        expense_count=10,
        month_spent=3000,
        month_expenses=5,
    )

    assert_equal(result["available"], True, "Spending availability")

    if not Decimal("0") <= result["score"] <= Decimal("20"):
        raise AssertionError("Spending score must remain between 0 and 20.")


def test_spending_score_with_limited_history():
    result = calculate_spending_score(
        total_spending=1000,
        average_expense=500,
        largest_expense=600,
        expense_count=2,
        month_spent=1000,
        month_expenses=2,
    )

    assert_equal(result["available"], True, "Limited spending availability")

    if result["score"] > Decimal("12"):
        raise AssertionError(
            "Limited transaction history should be scored conservatively."
        )


def test_spending_unavailable():
    result = calculate_spending_score()

    assert_equal(result["available"], False, "Spending unavailable")


def test_goal_score():
    result = calculate_goal_score(
        total_current=50000,
        total_target=100000,
    )

    assert_equal(result["available"], True, "Goal availability")
    assert_equal(result["percentage"], Decimal("50"), "Goal progress")
    assert_equal(result["score"], Decimal("12.5"), "Goal score")


def test_goal_progress_clamped():
    result = calculate_goal_score(
        total_current=120000,
        total_target=100000,
    )

    assert_equal(result["percentage"], Decimal("100"), "Clamped goal progress")
    assert_equal(result["score"], Decimal("25"), "Maximum goal score")


def test_investment_score():
    result = calculate_investment_score(7)

    assert_equal(result["available"], True, "Investment availability")
    assert_equal(result["score"], Decimal("15"), "Investment score")


def test_investment_unavailable():
    result = calculate_investment_score(None)

    assert_equal(result["available"], False, "Investment unavailable")


def test_final_score_normalization():
    components = {
        "budget": {
            "available": True,
            "score": Decimal("35"),
            "weight": Decimal("35"),
        },
        "spending": {
            "available": True,
            "score": Decimal("16"),
            "weight": Decimal("20"),
        },
        "goals": {
            "available": True,
            "score": Decimal("12.5"),
            "weight": Decimal("25"),
        },
        "investments": {
            "available": True,
            "score": Decimal("15"),
            "weight": Decimal("20"),
        },
    }

    result = calculate_final_score(components)

    # 78.5 / 100 => 79
    assert_equal(result["score"], Decimal("79"), "Final normalized score")
    assert_equal(result["grade"], "Good", "Final grade")
    assert_equal(result["coverage"], Decimal("100"), "Full coverage")


def test_final_score_without_investments():
    components = {
        "budget": {
            "available": True,
            "score": Decimal("35"),
            "weight": Decimal("35"),
        },
        "spending": {
            "available": True,
            "score": Decimal("16"),
            "weight": Decimal("20"),
        },
        "goals": {
            "available": True,
            "score": Decimal("12.5"),
            "weight": Decimal("25"),
        },
        "investments": {
            "available": False,
            "score": Decimal("0"),
            "weight": Decimal("20"),
        },
    }

    result = calculate_final_score(components)

    # 63.5 / 80 * 100 = 79.375 => 79
    assert_equal(result["score"], Decimal("79"), "Score without investments")
    assert_equal(result["coverage"], Decimal("80"), "Coverage without investments")


def test_no_available_components():
    components = {
        "budget": {
            "available": False,
            "score": Decimal("0"),
            "weight": Decimal("35"),
        },
        "spending": {
            "available": False,
            "score": Decimal("0"),
            "weight": Decimal("20"),
        },
        "goals": {
            "available": False,
            "score": Decimal("0"),
            "weight": Decimal("25"),
        },
        "investments": {
            "available": False,
            "score": Decimal("0"),
            "weight": Decimal("20"),
        },
    }

    result = calculate_final_score(components)

    assert_equal(result["available"], False, "No-data availability")
    assert_equal(result["score"], None, "No-data score")
    assert_equal(result["grade"], "Insufficient Data", "No-data grade")


def test_complete_financial_health():
    result = calculate_financial_health(
        budget_data={
            "total_allocated": 10000,
            "total_spent": 7000,
        },
        spending_data={
            "total_spent": 7000,
            "average_expense": 700,
            "largest_expense": 1500,
            "expense_count": 10,
            "month_spent": 3000,
            "month_expenses": 5,
        },
        goal_data={
            "total_current": 50000,
            "total_target": 100000,
        },
        investment_data={
            "return_percentage": 7,
        },
    )

    assert_equal(result["available"], True, "Complete health availability")
    assert_equal(result["coverage"], Decimal("100"), "Complete health coverage")

    if not Decimal("0") <= result["score"] <= Decimal("100"):
        raise AssertionError("Final score must remain between 0 and 100.")

    if result["grade"] not in {
        "Excellent",
        "Good",
        "Fair",
        "Needs Improvement",
    }:
        raise AssertionError("Invalid health grade.")


def test_health_grades():
    assert_equal(get_health_grade(90), "Excellent", "Excellent grade")
    assert_equal(get_health_grade(70), "Good", "Good grade")
    assert_equal(get_health_grade(50), "Fair", "Fair grade")
    assert_equal(get_health_grade(20), "Needs Improvement", "Needs improvement grade")
    assert_equal(
        get_health_grade(None),
        "Insufficient Data",
        "Insufficient data grade",
    )


if __name__ == "__main__":
    test_budget_score()
    test_budget_over_limit()
    test_spending_score_with_sufficient_history()
    test_spending_score_with_limited_history()
    test_spending_unavailable()
    test_goal_score()
    test_goal_progress_clamped()
    test_investment_score()
    test_investment_unavailable()
    test_final_score_normalization()
    test_final_score_without_investments()
    test_no_available_components()
    test_complete_financial_health()
    test_health_grades()

    print("All Financial Health Service tests passed.")
