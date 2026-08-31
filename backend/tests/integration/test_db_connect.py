"""The threading contract of `connect()` — see the docstring on the test."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from beacon.adapters.persistence.db import connect


def test_connection_is_usable_from_another_thread(tmp_path: Path) -> None:
    """FastAPI resolves a sync `Depends` and runs the sync endpoint as two separate
    `run_in_threadpool` hops, which anyio is free to place on different worker threads.
    A request-scoped connection is therefore opened in one thread and queried in another.
    """
    conn = connect(tmp_path / "beacon.db")
    conn.execute("CREATE TABLE t (n INTEGER)")
    conn.execute("INSERT INTO t (n) VALUES (1)")

    with ThreadPoolExecutor(max_workers=1) as pool:
        n = pool.submit(lambda: conn.execute("SELECT n FROM t").fetchone()["n"]).result()

    assert n == 1


def test_reader_works_while_another_connection_holds_a_write_transaction(tmp_path: Path) -> None:
    """run.sh serves the API from beacon.db while an ingest poll writes to the same file.
    Under the default rollback journal a writer's lock shuts readers out; WAL lets the
    cached rows keep being served for the whole poll.
    """
    db_path = tmp_path / "beacon.db"
    setup = connect(db_path)
    setup.execute("CREATE TABLE t (n INTEGER)")
    setup.execute("INSERT INTO t (n) VALUES (1)")
    setup.commit()

    writer = connect(db_path)
    writer.execute("BEGIN EXCLUSIVE")
    writer.execute("INSERT INTO t (n) VALUES (2)")

    reader = connect(db_path)
    assert reader.execute("SELECT count(*) AS c FROM t").fetchone()["c"] == 1


def test_connection_waits_for_a_contended_lock_instead_of_failing(tmp_path: Path) -> None:
    """Two writers do overlap: the ingest poll commits while an API write (a saved search,
    a settings change) lands. A busy timeout turns that race into a short wait, not a 500.
    """
    conn = connect(tmp_path / "beacon.db")

    timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert timeout_ms > 0
