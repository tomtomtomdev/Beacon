"""Request-scoped wiring: settings → connection → repos. The test seam."""

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from beacon.adapters.persistence.db import connect
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.config import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_job_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteJobRepo:
    return SqliteJobRepo(db)


JobRepoDep = Annotated[SqliteJobRepo, Depends(get_job_repo)]


def get_search_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteSearchRepo:
    return SqliteSearchRepo(db)


SearchRepoDep = Annotated[SqliteSearchRepo, Depends(get_search_repo)]
