import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parents[3] / "migrations"


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a connection that may cross threads.

    `check_same_thread=False` is required, not a shortcut: FastAPI resolves a sync `Depends`
    and runs a sync endpoint as two separate `run_in_threadpool` hops, and anyio may place
    them on different worker threads — so a request-scoped connection is opened in one thread
    and queried in another. It stays safe because every holder of a connection here is
    single-threaded in effect: the API opens one per request and the event loop serialises
    that request's dependency, endpoint and teardown; the CLI entrypoints and scripts open
    their own. Never share one connection between threads that run concurrently.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
