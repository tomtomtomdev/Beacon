from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Beacon")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
