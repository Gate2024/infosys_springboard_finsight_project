"""Apply the investment migration explicitly; never run this from a request."""

from pathlib import Path

from db import get_connection


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def apply_investment_migration():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cursor.execute(migration.read_text(encoding="utf-8"))


if __name__ == "__main__":
    apply_investment_migration()
    print("Investment migration applied successfully.")
