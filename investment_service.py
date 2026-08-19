from datetime import date
from decimal import Decimal, InvalidOperation


ASSET_TYPES = (
    "Stocks",
    "Bonds",
    "Mutual Funds",
    "ETFs",
    "Cryptocurrency",
    "Real Estate",
    "Other",
)


class InvestmentService:
    def __init__(self, repository):
        self.repository = repository

    def validate(self, data):
        errors = []
        asset_name = data.get("asset_name", "").strip()
        asset_type = data.get("asset_type", "").strip()
        purchase_date = data.get("purchase_date", "").strip()
        notes = data.get("notes", "").strip()

        if not 1 <= len(asset_name) <= 150:
            errors.append("Asset name must contain between 1 and 150 characters.")
        if asset_type not in ASSET_TYPES:
            errors.append("Please select a valid asset type.")
        if len(notes) > 2000:
            errors.append("Notes cannot exceed 2000 characters.")

        quantity = self._decimal(data.get("quantity"), "Quantity", errors, positive=True)
        purchase_price = self._decimal(
            data.get("purchase_price"), "Purchase price", errors, positive=False
        )
        current_value = self._decimal(
            data.get("current_value"), "Current value", errors, positive=False
        )

        try:
            parsed_date = date.fromisoformat(purchase_date)
            if parsed_date > date.today():
                errors.append("Purchase date cannot be in the future.")
        except ValueError:
            errors.append("Purchase date must be valid.")

        if errors:
            return errors, None

        return [], {
            "asset_name": asset_name,
            "asset_type": asset_type,
            "quantity": quantity,
            "purchase_price": purchase_price,
            "current_value": current_value,
            "purchase_date": purchase_date,
            "notes": notes,
        }

    @staticmethod
    def _decimal(value, label, errors, positive):
        try:
            number = Decimal(str(value or ""))
        except (InvalidOperation, ValueError):
            errors.append(f"{label} must be a valid number.")
            return Decimal("0")
        if positive and number <= 0:
            errors.append(f"{label} must be greater than zero.")
        elif not positive and number < 0:
            errors.append(f"{label} cannot be negative.")
        return number

    def list_for_user(self, user_id):
        investments = self.repository.list_for_user(user_id)
        total_invested = sum(
            (Decimal(str(row.get("invested_value") or 0)) for row in investments),
            Decimal("0"),
        )
        allocation = {}
        for investment in investments:
            asset_type = investment["asset_type"]
            allocation[asset_type] = allocation.get(asset_type, Decimal("0")) + Decimal(
                str(investment.get("invested_value") or 0)
            )
        allocation_rows = [
            {
                "asset_type": asset_type,
                "value": value,
                "percentage": (value / total_invested * Decimal("100")) if total_invested else Decimal("0"),
            }
            for asset_type, value in sorted(allocation.items(), key=lambda item: item[1], reverse=True)
        ]
        valued_investments = [row for row in investments if row.get("current_value") is not None]
        current_value = sum(
            (Decimal(str(row["current_value"])) for row in valued_investments),
            Decimal("0"),
        )
        absolute_return = current_value - total_invested if len(valued_investments) == len(investments) else None
        return_percentage = (
            absolute_return / total_invested * Decimal("100")
            if absolute_return is not None and total_invested
            else None
        )
        return investments, {
            "total_investments": len(investments),
            "total_invested": total_invested,
            "current_value": current_value if valued_investments else None,
            "absolute_return": absolute_return,
            "return_percentage": return_percentage,
            "allocation": allocation_rows,
            "valuation_complete": len(valued_investments) == len(investments),
        }

    def get_for_user(self, investment_id, user_id):
        return self.repository.get_for_user(investment_id, user_id)

    def create(self, user_id, data):
        errors, payload = self.validate(data)
        if errors:
            return None, errors
        return self.repository.create(user_id, payload), []

    def update(self, investment_id, user_id, data):
        errors, payload = self.validate(data)
        if errors:
            return False, errors
        return self.repository.update(investment_id, user_id, payload), []

    def delete(self, investment_id, user_id):
        return self.repository.delete(investment_id, user_id)
