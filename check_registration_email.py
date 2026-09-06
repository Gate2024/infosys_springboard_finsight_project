from db import get_connection


email = input("Enter the registration email to check: ").strip().lower()

with get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE lower(email) = %s
               OR lower(username) = %s
            """,
            (email, email),
        )

        rows = cursor.fetchall()

        if rows:
            print("Matching account found:")
            for row in rows:
                print({
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                })
        else:
            print("No matching account found.")