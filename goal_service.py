from datetime import date
from decimal import Decimal, InvalidOperation


GOAL_CATEGORIES = (
    "Savings",
    "Education",
    "Travel",
    "Retirement",
    "Major purchases",
)


class GoalService:
    def __init__(self, repository):
        self.repository = repository

    def validate(self, data):
        errors = []
        goal_name = data.get("goal_name", "").strip()
        goal_category = data.get("goal_category", "").strip()
        target_date = data.get("target_date", "").strip()
        target_amount = self._decimal(data.get("target_amount"), "Target amount", errors)
        current_amount = self._decimal(data.get("current_amount"), "Current amount", errors)

        if not 1 <= len(goal_name) <= 150:
            errors.append("Goal name must contain between 1 and 150 characters.")
        if goal_category not in GOAL_CATEGORIES:
            errors.append("Please select a valid goal category.")
        if target_amount <= 0:
            errors.append("Target amount must be greater than zero.")
        if current_amount < 0:
            errors.append("Current amount cannot be negative.")

        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            errors.append("Target date must be valid.")
            parsed_date = None

        if errors:
            return errors, None

        return [], {
            "goal_name": goal_name,
            "goal_category": goal_category,
            "target_amount": target_amount,
            "current_amount": current_amount,
            "target_date": parsed_date,
            "status": self.status_for(current_amount, target_amount),
        }

    @staticmethod
    def _decimal(value, label, errors):
        try:
            number = Decimal(str(value or ""))
        except (InvalidOperation, ValueError):
            errors.append(f"{label} must be a valid number.")
            return Decimal("0")
        return number

    @staticmethod
    def status_for(current_amount, target_amount):
        return "Completed" if current_amount >= target_amount else "Active"

    @staticmethod
    def progress_for(goal):
        target = Decimal(str(goal["target_amount"]))
        current = Decimal(str(goal["current_amount"]))
        percentage = (current / target * Decimal("100")) if target > 0 else Decimal("0")
        percentage = min(Decimal("100"), max(Decimal("0"), percentage))
        return {
            "progress_percentage": percentage,
            "remaining_amount": max(Decimal("0"), target - current),
            "status": GoalService.status_for(current, target),
        }

    def list_for_user(self, user_id):
        goals = self.repository.list_for_user(user_id)
        return [self.with_progress(goal) for goal in goals]

    def get_for_user(self, goal_id, user_id):
        goal = self.repository.get_for_user(goal_id, user_id)
        return self.with_progress(goal) if goal else None

    def with_progress(self, goal):
        return {**goal, **self.progress_for(goal)}

    def create(self, user_id, data):
        errors, payload = self.validate(data)
        if errors:
            return None, errors
        return self.repository.create(user_id, payload), []

    def update(self, goal_id, user_id, data):
        errors, payload = self.validate(data)
        if errors:
            return False, errors
        return self.repository.update(goal_id, user_id, payload), []

    def delete(self, goal_id, user_id):
        return self.repository.delete(goal_id, user_id)
