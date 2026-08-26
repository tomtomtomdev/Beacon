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
