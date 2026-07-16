"""Request-scoped wiring: settings → connection → repos. The test seam."""

import sqlite3
from collections.abc import AsyncIterator, Iterator
from typing import Annotated

import httpx
from fastapi import Depends, Request

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.countries import SqliteCountryRepo
from beacon.adapters.persistence.db import connect
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.match_scores import SqliteMatchScoreRepo
from beacon.adapters.persistence.resumes import SqliteResumeRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.adapters.persistence.settings import SqliteSettingsRepo
from beacon.adapters.resume.plaintext import PlainTextResumeParser
from beacon.application.ports import ResumeParser
from beacon.config import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


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


def get_settings_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteSettingsRepo:
    return SqliteSettingsRepo(db)


SettingsRepoDep = Annotated[SqliteSettingsRepo, Depends(get_settings_repo)]


def get_country_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteCountryRepo:
    return SqliteCountryRepo(db)


CountryRepoDep = Annotated[SqliteCountryRepo, Depends(get_country_repo)]


def get_company_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteCompanyRepo:
    return SqliteCompanyRepo(db)


CompanyRepoDep = Annotated[SqliteCompanyRepo, Depends(get_company_repo)]


def get_resume_repo(db: Annotated[sqlite3.Connection, Depends(get_db)]) -> SqliteResumeRepo:
    return SqliteResumeRepo(db)


ResumeRepoDep = Annotated[SqliteResumeRepo, Depends(get_resume_repo)]


def get_match_score_repo(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> SqliteMatchScoreRepo:
    return SqliteMatchScoreRepo(db)


MatchScoreRepoDep = Annotated[SqliteMatchScoreRepo, Depends(get_match_score_repo)]


def get_resume_parser() -> ResumeParser:
    """The zero-dep paste/.txt parser. PDF becomes a drop-in here behind the same port."""
    return PlainTextResumeParser()


ResumeParserDep = Annotated[ResumeParser, Depends(get_resume_parser)]


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """A short-lived HTTP client for outbound calls (the Telegram test send). Overridden
    in tests with a MockTransport client so the suite never hits the network."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
