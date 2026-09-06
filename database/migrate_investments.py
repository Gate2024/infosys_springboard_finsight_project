"""Apply numbered PostgreSQL migrations with durable version tracking."""

import re
from pathlib import Path

from db import get_connection


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_VERSION_PATTERN = re.compile(r"^(\d+)_.*\.sql$")
ADVISORY_LOCK_KEY = 76483621


def _migration_files():
    migrations = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = MIGRATION_VERSION_PATTERN.match(path.name)
        if match:
            migrations.append((int(match.group(1)), path))
    return sorted(migrations, key=lambda item: item[0])


def apply_investment_migration():
    """Apply each unapplied migration exactly once.

    Existing databases require a one-time baseline adoption: after verifying
    their schema matches the repository, insert the already-applied versions
    into schema_migrations before running this function.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
            try:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(32) PRIMARY KEY,
                        applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
                cursor.execute("SELECT version FROM schema_migrations")
                applied = {
                    row["version"] if isinstance(row, dict) else row[0]
                    for row in cursor.fetchall()
                }
                for version, migration in _migration_files():
                    version_text = f"{version:03d}"
                    if version_text in applied:
                        continue
                    try:
                        cursor.execute(migration.read_text(encoding="utf-8"))
                        cursor.execute(
                            "INSERT INTO schema_migrations (version) VALUES (%s)",
                            (version_text,),
                        )
                        conn.commit()
                        applied.add(version_text)
                    except Exception:
                        conn.rollback()
                        raise
            finally:
                conn.rollback()
                cursor.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))


if __name__ == "__main__":
    apply_investment_migration()
    print("Migrations applied successfully.")
