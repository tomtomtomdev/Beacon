import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parents[3] / "migrations"


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> list[str]:
    """Apply numbered .sql files not yet recorded in schema_migrations, in filename order."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations"
        " (filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    already_applied = {
        row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")
    }

    newly_applied: list[str] = []
    for migration in sorted(migrations_dir.glob("[0-9]*.sql")):
        if migration.name in already_applied:
            continue
        conn.executescript(migration.read_text())
        conn.execute(
            "INSERT INTO schema_migrations (filename, applied_at) VALUES (?, ?)",
            (migration.name, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        newly_applied.append(migration.name)
    return newly_applied
