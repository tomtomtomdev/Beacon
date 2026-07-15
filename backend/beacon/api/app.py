from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from beacon.adapters.persistence.countries import SqliteCountryRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.api.companies import router as companies_router
from beacon.api.countries import router as countries_router
from beacon.api.jobs import router as jobs_router
from beacon.api.resumes import router as resumes_router
from beacon.api.searches import router as searches_router
from beacon.api.settings import router as settings_router
from beacon.application.countries import seed_countries
from beacon.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(resolved.db_path)
        try:
            run_migrations(conn, MIGRATIONS_DIR)
            # Reference data (SPEC §4) is a projection of the domain constant — re-seed on
            # every startup so the table always matches it.
            seed_countries(SqliteCountryRepo(conn))
        finally:
            conn.close()
        yield

    app = FastAPI(title="Beacon", lifespan=lifespan)
    app.state.settings = resolved
    app.include_router(jobs_router)
    app.include_router(searches_router)
    app.include_router(settings_router)
    app.include_router(countries_router)
    app.include_router(companies_router)
    app.include_router(resumes_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
