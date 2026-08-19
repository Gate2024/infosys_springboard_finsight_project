from db import get_connection


class GoalRepository:
    """PostgreSQL persistence for user-owned financial goals."""

    def list_for_user(self, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT goal_id, user_id, goal_name, goal_category,
                           target_amount, current_amount, target_date, status,
                           created_at, updated_at
                    FROM goals
                    WHERE user_id = %s
                    ORDER BY target_date ASC, created_at DESC
                    """,
                    (user_id,),
                )
                return [dict(row) for row in cursor.fetchall()]

    def get_for_user(self, goal_id, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT goal_id, user_id, goal_name, goal_category,
                           target_amount, current_amount, target_date, status,
                           created_at, updated_at
                    FROM goals
                    WHERE goal_id = %s AND user_id = %s
                    """,
                    (goal_id, user_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def create(self, user_id, payload):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO goals (
                        user_id, goal_name, goal_category, target_amount,
                        current_amount, target_date, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING goal_id
                    """,
                    (
                        user_id,
                        payload["goal_name"],
                        payload["goal_category"],
                        payload["target_amount"],
                        payload["current_amount"],
                        payload["target_date"],
                        payload["status"],
                    ),
                )
                return dict(cursor.fetchone())

    def update(self, goal_id, user_id, payload):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE goals
                    SET goal_name = %s,
                        goal_category = %s,
                        target_amount = %s,
                        current_amount = %s,
                        target_date = %s,
                        status = %s,
                        updated_at = NOW()
                    WHERE goal_id = %s AND user_id = %s
                    """,
                    (
                        payload["goal_name"],
                        payload["goal_category"],
                        payload["target_amount"],
                        payload["current_amount"],
                        payload["target_date"],
                        payload["status"],
                        goal_id,
                        user_id,
                    ),
                )
                return cursor.rowcount > 0

    def delete(self, goal_id, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM goals
                    WHERE goal_id = %s AND user_id = %s
                    """,
                    (goal_id, user_id),
                )
                return cursor.rowcount > 0
