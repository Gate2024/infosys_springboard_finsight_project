from pathlib import Path

from database.migrate_investments import _migration_files


MIGRATIONS_DIR = Path("database/migrations")


def test_migrations_are_discovered_in_numeric_order():
    versions = [version for version, _ in _migration_files()]

    assert versions == list(range(15))


def test_foundation_migration_precedes_investments_and_defines_required_tables():
    foundation = (MIGRATIONS_DIR / "000_create_foundation_schema.sql").read_text(
        encoding="utf-8"
    ).upper()

    assert foundation.index("CREATE TABLE IF NOT EXISTS USERS") < foundation.index(
        "CREATE TABLE IF NOT EXISTS BUDGETS"
    )
    assert foundation.index("CREATE TABLE IF NOT EXISTS BUDGETS") < foundation.index(
        "CREATE TABLE IF NOT EXISTS TRANSACTIONS"
    )
    assert "REFERENCES USERS(ID) ON DELETE CASCADE" in foundation


def test_existing_migration_sql_remains_unchanged():
    assert not any(
        path.name != "000_create_foundation_schema.sql"
        for path in MIGRATIONS_DIR.glob("*.sql")
        if path.name.startswith("000_")
    )
