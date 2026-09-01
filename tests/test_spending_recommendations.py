from decimal import Decimal

from app import (
    APPROACHING_BUDGET_THRESHOLD,
    LARGE_EXPENSE_MULTIPLIER,
    OVER_BUDGET_THRESHOLD,
    build_spending_recommendations,
)


def budget(name, utilization, status):
    return {
        "budget_name": name,
        "utilization_percentage": utilization,
        "status": status,
    }


def stats(total_expenses=0, average_expense=0, largest_expense=0):
    return {
        "total_expenses": total_expenses,
        "average_expense": average_expense,
        "largest_expense": largest_expense,
    }


def recommendations(
    budgets=None,
    categories=None,
    months=None,
    expense_stats=None,
):
    return build_spending_recommendations(
        budgets or [],
        categories or [],
        months or [],
        expense_stats or stats(),
    )


def test_over_budget_recommendation_uses_status_and_message():
    result = recommendations(
        budgets=[budget("Travel", Decimal("100"), "Over Budget")]
    )

    assert result[0]["priority"] == "High"
    assert result[0]["message"] == (
        "Your Travel budget is over its stored limit. Review spending in this budget."
    )


def test_over_budget_recommendation_uses_utilization_when_status_is_missing():
    result = recommendations(
        budgets=[budget("Travel", OVER_BUDGET_THRESHOLD + 1, "Unavailable")]
    )

    assert len(result) == 1
    assert result[0]["priority"] == "High"


def test_approaching_limit_recommendation_includes_boundaries():
    result = recommendations(
        budgets=[
            budget("Housing", APPROACHING_BUDGET_THRESHOLD, "Approaching Limit"),
            budget("Food", OVER_BUDGET_THRESHOLD, "Approaching Limit"),
        ]
    )

    assert len(result) == 2
    assert all(item["priority"] == "Medium" for item in result)
    assert all("approaching its stored limit" in item["message"] for item in result)


def test_healthy_budget_and_empty_budgets_have_no_budget_warning():
    assert recommendations(budgets=[budget("Housing", 79, "Healthy")]) == []
    assert recommendations() == []


def test_high_category_concentration_recommendation():
    result = recommendations(
        categories=[
            {"category": "Housing", "amount": 500},
            {"category": "Food", "amount": 400},
        ]
    )

    assert len(result) == 1
    assert result[0]["priority"] == "Medium"
    assert "concentrated in Housing" in result[0]["message"]


def test_category_concentration_threshold_and_empty_expenses_are_safe():
    assert len(
        recommendations(
            categories=[
                {"category": "Housing", "amount": 500},
                {"category": "Food", "amount": 500},
            ]
        )
    ) == 1
    assert recommendations(categories=[]) == []


def test_spending_increase_recommendation():
    result = recommendations(
        months=[
            {"month": "2026-01", "amount": 100},
            {"month": "2026-02", "amount": 125},
        ]
    )

    assert len(result) == 1
    assert result[0]["priority"] == "Medium"
    assert "increased compared" in result[0]["message"]


def test_stable_decreasing_and_empty_monthly_data_have_no_increase_warning():
    assert recommendations(months=[{"amount": 100}, {"amount": 100}]) == []
    assert recommendations(months=[{"amount": 100}, {"amount": 90}]) == []
    assert recommendations(months=[]) == []


def test_unusually_large_expense_recommendation():
    result = recommendations(
        expense_stats=stats(
            total_expenses=3,
            average_expense=100,
            largest_expense=LARGE_EXPENSE_MULTIPLIER * 100,
        )
    )

    assert len(result) == 1
    assert result[0]["priority"] == "Low"
    assert "larger than your average expense" in result[0]["message"]


def test_multiple_recommendations_are_sorted_by_priority():
    result = recommendations(
        budgets=[budget("Travel", 125, "Over Budget")],
        categories=[{"category": "Housing", "amount": 600}, {"category": "Food", "amount": 400}],
        months=[{"amount": 100}, {"amount": 150}],
        expense_stats=stats(2, 100, 250),
    )

    assert [item["priority"] for item in result] == ["High", "Medium", "Medium", "Low"]


def test_no_recommendation_state_is_empty_for_normal_data():
    assert recommendations(
        budgets=[budget("Housing", 50, "Healthy")],
        categories=[
            {"category": "Housing", "amount": 333},
            {"category": "Food", "amount": 333},
            {"category": "Travel", "amount": 334},
        ],
        months=[{"amount": 100}, {"amount": 100}],
        expense_stats=stats(2, 100, 150),
    ) == []


def test_zero_values_do_not_generate_recommendations():
    assert recommendations(
        budgets=[budget("Housing", 0, "Unavailable")],
        categories=[{"category": "Housing", "amount": 0}],
        months=[{"amount": 0}, {"amount": 0}],
        expense_stats=stats(0, 0, 0),
    ) == []


def test_missing_or_malformed_values_do_not_generate_recommendations():
    assert recommendations(
        budgets=[budget("Housing", None, None)],
        categories=[{"category": "Housing", "amount": None}],
        months=[{"amount": None}, {}],
        expense_stats={"total_expenses": None, "average_expense": "invalid"},
    ) == []


def test_recommendations_do_not_assume_income_savings_or_balance():
    result = recommendations(
        categories=[{"category": "Food", "amount": 100}],
        expense_stats=stats(1, 50, 100),
    )

    assert result
    assert all(
        term not in item["message"].lower()
        for item in result
        for term in ("income", "savings", "balance")
    )
