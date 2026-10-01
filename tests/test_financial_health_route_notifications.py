import db
import pytest

import app as application


def authenticated_client(tracked_session_store):
    tracked_session_store(7)
    client = application.app.test_client()
    with client.session_transaction() as session:
        session.update(
            uid=7,
            auth_session_token="fixture-session-7",
            username="Health Route Tester",
            budget_csrf_token="budget-token",
            expense_csrf_token="expense-token",
            goal_csrf_token="goal-token",
            investment_csrf_token="investment-token",
        )
    return client


def route_data(route):
    return {
        "budget": {
            "_budget_csrf_token": "budget-token",
            "budget_name": "Food",
            "category": "Food & Dining",
            "status": "Active",
            "budget_amount": "1000",
            "spent_amount": "100",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        "expense": {
            "_expense_csrf_token": "expense-token",
            "description": "Lunch",
            "amount": "25",
            "date": "2026-08-01",
            "category": "Food & Dining",
            "payment_mode": "Cash",
        },
        "goal": {
            "_goal_csrf_token": "goal-token",
            "goal_name": "Emergency Fund",
            "goal_category": "Savings",
            "target_amount": "10000",
            "current_amount": "1000",
            "target_date": "2030-01-01",
        },
        "investment": {
            "_investment_csrf_token": "investment-token",
            "asset_name": "Index Fund",
            "asset_type": "ETFs",
            "quantity": "2",
            "purchase_price": "100",
            "current_value": "210",
            "purchase_date": "2026-01-01",
            "notes": "Long term",
        },
    }[route]


def owned_budget():
    return {
        "budget_id": 1,
        "user_id": 7,
        "budget_name": "Food",
        "category": "Food & Dining",
        "budget_amount": "1000",
        "spent_amount": "100",
        "alert_percentage": "80",
    }


def owned_goal():
    return {
        "goal_id": 1,
        "user_id": 7,
        "goal_name": "Emergency Fund",
        "goal_category": "Savings",
        "target_amount": "10000",
        "current_amount": "1000",
        "status": "Active",
        "target_date": "2030-01-01",
    }


def owned_investment():
    return {
        "investment_id": 1,
        "user_id": 7,
        "asset_name": "Index Fund",
        "asset_type": "ETFs",
        "quantity": "2",
        "purchase_price": "100",
        "current_value": "210",
        "purchase_date": "2026-01-01",
        "notes": "Long term",
    }


def configure_route(monkeypatch, route, success):
    if route == "budget_create":
        if success:
            monkeypatch.setattr(application, "create_budget", lambda *_args: {"budget_id": 1})
        else:
            monkeypatch.setattr(
                application,
                "create_budget",
                lambda *_args: (_ for _ in ()).throw(RuntimeError("write failed")),
            )
        monkeypatch.setattr(application, "get_budget", lambda *_args: owned_budget())
        return "/budget/create", route_data("budget")
    if route == "budget_edit":
        monkeypatch.setattr(application, "get_budget", lambda *_args: owned_budget())
        monkeypatch.setattr(application, "update_budget", lambda *_args: success)
        return "/budget/edit/1", route_data("budget")
    if route == "expense_create":
        monkeypatch.setattr(db, "create_transaction", lambda *_args: True if success else (_ for _ in ()).throw(RuntimeError("write failed")))
        return "/expense/create", route_data("expense")
    if route == "expense_edit":
        monkeypatch.setattr(db, "get_transaction", lambda *_args: {"id": 1, "user_id": 7, **route_data("expense")})
        monkeypatch.setattr(db, "update_transaction", lambda *_args: success)
        return "/expense/edit/1", route_data("expense")
    if route == "expense_delete":
        monkeypatch.setattr(db, "delete_transaction", lambda *_args: success)
        return "/expense/delete/1", {"_expense_csrf_token": "expense-token"}
    if route == "goal_create":
        monkeypatch.setattr(application.goal_service, "create", lambda *_args: (({"goal_id": 1}, []) if success else (None, ["failed"])))
        monkeypatch.setattr(application.goal_service, "get_for_user", lambda *_args: None)
        return "/goals/create", route_data("goal")
    if route == "goal_edit":
        monkeypatch.setattr(application.goal_service, "get_for_user", lambda *_args: owned_goal())
        monkeypatch.setattr(application.goal_service, "update", lambda *_args: (success, []))
        return "/goals/1/edit", route_data("goal")
    if route == "goal_delete":
        monkeypatch.setattr(application.goal_service, "delete", lambda *_args: success)
        return "/goals/1/delete", {"_goal_csrf_token": "goal-token"}
    if route == "investment_create":
        monkeypatch.setattr(application.investment_service, "create", lambda *_args: (({"investment_id": 1}, []) if success else (None, ["failed"])))
        return "/investments/create", route_data("investment")
    if route == "investment_edit":
        monkeypatch.setattr(application.investment_service, "get_for_user", lambda *_args: owned_investment())
        monkeypatch.setattr(application.investment_service, "update", lambda *_args: (success, []))
        return "/investments/1/edit", route_data("investment")
    if route == "investment_delete":
        monkeypatch.setattr(application.investment_service, "delete", lambda *_args: success)
        return "/investments/1/delete", {"_investment_csrf_token": "investment-token"}
    raise AssertionError(route)


ROUTES = (
    "budget_create", "budget_edit", "expense_create", "expense_edit", "expense_delete",
    "goal_create", "goal_edit", "goal_delete", "investment_create", "investment_edit",
    "investment_delete",
)


@pytest.mark.parametrize("route", ROUTES)
def test_successful_mutations_evaluate_health_and_isolate_evaluator_failure(
    monkeypatch, tracked_session_store, route
):
    client = authenticated_client(tracked_session_store)
    endpoint, data = configure_route(monkeypatch, route, True)
    evaluations = []

    monkeypatch.setattr(application, "get_summary_stats", lambda *_args: {})
    monkeypatch.setattr(application, "get_expense_summary", lambda *_args: {})
    monkeypatch.setattr(application.goal_service, "list_for_user", lambda *_args: [])
    monkeypatch.setattr(application.investment_service, "list_for_user", lambda *_args: ([], {}))
    monkeypatch.setattr(
        application,
        "calculate_financial_health",
        lambda **_kwargs: {"available": True, "grade": "Good", "score": 80},
    )

    def failing_state_persistence(user_id, _grade, _score):
        evaluations.append(user_id)
        raise RuntimeError("health processing failed")

    monkeypatch.setattr(application, "record_financial_health_evaluation", failing_state_persistence)
    monkeypatch.setattr(application, "_notify_for_budget_transition", lambda *_args: None)
    monkeypatch.setattr(application, "_notify_for_goal_transition", lambda *_args: None)

    response = client.post(endpoint, data=data)

    assert response.status_code == 302
    assert evaluations == [7]


@pytest.mark.parametrize("route", ROUTES)
def test_unsuccessful_mutations_do_not_evaluate_health(
    monkeypatch, tracked_session_store, route
):
    client = authenticated_client(tracked_session_store)
    endpoint, data = configure_route(monkeypatch, route, False)
    evaluations = []
    monkeypatch.setattr(
        application,
        "_evaluate_financial_health_after_operation",
        lambda user_id: evaluations.append(user_id),
    )

    response = client.post(endpoint, data=data)

    assert response.status_code in {200, 302, 400, 503}
    assert evaluations == []
