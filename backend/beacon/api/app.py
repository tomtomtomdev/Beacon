from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.api.jobs import router as jobs_router
from beacon.api.searches import router as searches_router
from beacon.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(resolved.db_path)
        try:
            run_migrations(conn, MIGRATIONS_DIR)
        finally:
            conn.close()
        yield

    app = FastAPI(title="Beacon", lifespan=lifespan)
    app.state.settings = resolved
    app.include_router(jobs_router)
    app.include_router(searches_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
