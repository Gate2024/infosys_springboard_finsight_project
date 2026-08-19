from db import get_connection, serialize_row, serialize_rows


class InvestmentRepository:
    """PostgreSQL persistence for user-owned investment holdings."""

    def list_for_user(self, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT investment_id, asset_name, asset_type, quantity,
                           purchase_price, current_value, purchase_date, notes,
                           created_at, updated_at,
                           quantity * purchase_price AS invested_value
                    FROM investments
                    WHERE user_id = %s
                    ORDER BY purchase_date DESC, created_at DESC
                    """,
                    (user_id,),
                )
                return serialize_rows(cursor.fetchall())

    def get_for_user(self, investment_id, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT investment_id, asset_name, asset_type, quantity,
                           purchase_price, current_value, purchase_date, notes,
                           created_at, updated_at,
                           quantity * purchase_price AS invested_value
                    FROM investments
                    WHERE investment_id = %s AND user_id = %s
                    """,
                    (investment_id, user_id),
                )
                return serialize_row(cursor.fetchone())

    def create(self, user_id, payload):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO investments (
                        user_id, asset_name, asset_type, quantity,
                        purchase_price, current_value, purchase_date, notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING investment_id
                    """,
                    (
                        user_id,
                        payload["asset_name"],
                        payload["asset_type"],
                        payload["quantity"],
                        payload["purchase_price"],
                        payload["current_value"],
                        payload["purchase_date"],
                        payload["notes"],
                    ),
                )
                return serialize_row(cursor.fetchone())

    def update(self, investment_id, user_id, payload):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE investments
                    SET asset_name = %s,
                        asset_type = %s,
                        quantity = %s,
                        purchase_price = %s,
                        current_value = %s,
                        purchase_date = %s,
                        notes = %s,
                        updated_at = NOW()
                    WHERE investment_id = %s AND user_id = %s
                    """,
                    (
                        payload["asset_name"],
                        payload["asset_type"],
                        payload["quantity"],
                        payload["purchase_price"],
                        payload["current_value"],
                        payload["purchase_date"],
                        payload["notes"],
                        investment_id,
                        user_id,
                    ),
                )
                return cursor.rowcount > 0

    def delete(self, investment_id, user_id):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM investments
                    WHERE investment_id = %s AND user_id = %s
                    """,
                    (investment_id, user_id),
                )
                return cursor.rowcount > 0
