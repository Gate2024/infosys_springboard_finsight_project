from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import app as application


class FakeInvestmentRepository:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def list_for_user(self, user_id):
        rows = [deepcopy(row) for row in self.rows if row["user_id"] == user_id]
        for row in rows:
            row["invested_value"] = row["quantity"] * row["purchase_price"]
        return rows

    def get_for_user(self, investment_id, user_id):
        rows = [row for row in self.rows if row["investment_id"] == investment_id and row["user_id"] == user_id]
        if not rows:
            return None
        row = deepcopy(rows[0])
        row["invested_value"] = row["quantity"] * row["purchase_price"]
        return row

    def create(self, user_id, payload):
        row = dict(payload)
        row.update({"investment_id": self.next_id, "user_id": user_id, "created_at": date.today()})
        self.next_id += 1
        self.rows.append(row)
        return {"investment_id": row["investment_id"]}

    def update(self, investment_id, user_id, payload):
        for row in self.rows:
            if row["investment_id"] == investment_id and row["user_id"] == user_id:
                row.update(payload)
                return True
        return False

    def delete(self, investment_id, user_id):
        before = len(self.rows)
        self.rows = [row for row in self.rows if not (
            row["investment_id"] == investment_id and row["user_id"] == user_id
        )]
        return len(self.rows) < before


@pytest.fixture
def investment_repository(monkeypatch):
    repository = FakeInvestmentRepository()
    application.investment_service.repository = repository
    monkeypatch.setattr(application.goal_service.repository, "list_for_user", lambda user_id: [])
    return repository


@pytest.fixture
def client(investment_repository):
    client = application.app.test_client()
    with client.session_transaction() as session:
        session["uid"] = 7
        session["username"] = "Investment Tester"
        session["investment_csrf_token"] = "investment-test-token"
    return client


def investment_data(**overrides):
    data = {
        "asset_name": "Index Fund",
        "asset_type": "ETFs",
        "quantity": "3.5",
        "purchase_price": "125.50",
        "current_value": "480.00",
        "purchase_date": "2026-01-15",
        "notes": "Long-term holding",
        "_investment_csrf_token": "investment-test-token",
    }
    data.update(overrides)
    return data


def test_anonymous_user_cannot_access_investments():
    client = application.app.test_client()
    response = client.get("/investments")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_empty_portfolio(client):
    response = client.get("/investments")
    assert response.status_code == 200
    assert b"No investments yet" in response.data


def test_create_and_read_investment(client, investment_repository):
    response = client.post("/investments/create", data=investment_data())
    assert response.status_code == 302
    assert investment_repository.rows[0]["asset_name"] == "Index Fund"

    response = client.get("/investments")
    assert response.status_code == 200
    assert b"Index Fund" in response.data
    assert b"$439.25" in response.data
    assert b"$480.00" in response.data

    response = client.get("/investments/1")
    assert response.status_code == 200
    assert b"Long-term holding" in response.data


@pytest.mark.parametrize("field,value", [
    ("asset_name", ""),
    ("asset_type", "Invalid Type"),
    ("quantity", "0"),
    ("quantity", "not-a-number"),
    ("purchase_price", "-1"),
    ("purchase_date", "2099-01-01"),
])
def test_invalid_investment_is_rejected(client, field, value):
    response = client.post("/investments/create", data=investment_data(**{field: value}))
    assert response.status_code == 400
    assert b"danger" in response.data


def test_csrf_is_required_for_investment_mutations(client):
    data = investment_data()
    data.pop("_investment_csrf_token")
    response = client.post("/investments/create", data=data)
    assert response.status_code == 400


def test_update_investment(client, investment_repository):
    client.post("/investments/create", data=investment_data())
    response = client.post(
        "/investments/1/edit",
        data=investment_data(asset_name="Updated Fund", quantity="5"),
    )
    assert response.status_code == 302
    assert investment_repository.rows[0]["asset_name"] == "Updated Fund"
    assert investment_repository.rows[0]["quantity"] == Decimal("5")


def test_allocation_and_returns_use_saved_values(client, investment_repository):
    client.post("/investments/create", data=investment_data())
    client.post(
        "/investments/create",
        data=investment_data(
            asset_name="Bond Fund",
            asset_type="Bonds",
            quantity="2",
            purchase_price="100",
            current_value="180",
        ),
    )

    response = client.get("/investments")

    assert response.status_code == 200
    assert b"Portfolio Performance" in response.data
    assert b"$+20.75" in response.data
    assert b"+3.25%" in response.data
    assert b"ETFs" in response.data and b"Bonds" in response.data


def test_user_isolation_and_mutations_change_portfolio(client, investment_repository):
    investment_repository.create(99, {
        "asset_name": "Private Holding", "asset_type": "Stocks", "quantity": Decimal("1"),
        "purchase_price": Decimal("50"), "current_value": Decimal("60"),
        "purchase_date": "2026-01-01", "notes": "",
    })
    client.post("/investments/create", data=investment_data())

    response = client.get("/investments")
    assert b"Private Holding" not in response.data
    assert b"$439.25" in response.data

    client.post(
        "/investments/2/edit",
        data=investment_data(current_value="520"),
    )
    response = client.get("/investments")
    assert b"$+80.75" in response.data

    client.post("/investments/2/delete", data={"_investment_csrf_token": "investment-test-token"})
    response = client.get("/investments")
    assert b"No investments yet" in response.data


def test_investment_dashboard_shows_owned_financial_goals(client, investment_repository, monkeypatch):
    monkeypatch.setattr(
        application.goal_service.repository,
        "list_for_user",
        lambda user_id: [
            {
                "goal_id": 1,
                "user_id": user_id,
                "goal_name": "Emergency Fund",
                "goal_category": "Savings",
                "target_amount": Decimal("10000"),
                "current_amount": Decimal("2500"),
                "target_date": date(2030, 1, 1),
                "status": "Active",
            }
        ],
    )

    response = client.get("/investments")

    assert response.status_code == 200
    assert b"Financial Goals Overview" in response.data
    assert b"Emergency Fund" in response.data
    assert b"25.00% complete" in response.data
    assert b"$2,500.00 / $10,000.00" in response.data
    assert b"$7,500.00" in response.data
    assert b'href="/goals"' in response.data


def test_investment_dashboard_goal_empty_state(client, investment_repository):
    response = client.get("/investments")

    assert b"No financial goals yet." in response.data
    assert b'href="/goals/create"' in response.data


def test_delete_is_post_only_and_requires_ownership(client, investment_repository):
    investment_repository.create(99, {
        "asset_name": "Private Fund", "asset_type": "Stocks", "quantity": Decimal("1"),
        "purchase_price": Decimal("10"), "current_value": Decimal("12"),
        "purchase_date": "2026-01-01", "notes": "",
    })
    assert client.get("/investments/1/delete").status_code == 405
    assert client.post("/investments/1/delete", data={"_investment_csrf_token": "investment-test-token"}).status_code == 302
    assert investment_repository.get_for_user(1, 99) is not None

    client.post("/investments/create", data=investment_data())
    assert client.post("/investments/2/delete", data={"_investment_csrf_token": "investment-test-token"}).status_code == 302
    assert investment_repository.get_for_user(2, 7) is None


def test_route_methods(client):
    rules = {rule.rule: rule.methods for rule in application.app.url_map.iter_rules()}
    assert "POST" in rules["/investments/create"]
    assert "GET" not in rules["/investments/<int:investment_id>/delete"] if "/investments/<int:investment_id>/delete" in rules else True


def test_investment_migration_is_non_destructive_and_constrained():
    sql = (Path("database/migrations/001_create_investments.sql").read_text(encoding="utf-8")).upper()
    assert "CREATE TABLE IF NOT EXISTS INVESTMENTS" in sql
    assert "REFERENCES USERS(ID) ON DELETE CASCADE" in sql
    assert "QUANTITY NUMERIC(20, 8) NOT NULL CHECK (QUANTITY > 0)" in sql
    assert "PURCHASE_PRICE NUMERIC(14, 2) NOT NULL CHECK (PURCHASE_PRICE >= 0)" in sql
    assert "DROP TABLE" not in sql
    assert "DELETE FROM" not in sql

    current_value_sql = Path("database/migrations/002_add_investment_current_value.sql").read_text(encoding="utf-8").upper()
    assert "ADD COLUMN IF NOT EXISTS CURRENT_VALUE NUMERIC(14, 2)" in current_value_sql
    assert "CURRENT_VALUE IS NULL OR CURRENT_VALUE >= 0" in current_value_sql
