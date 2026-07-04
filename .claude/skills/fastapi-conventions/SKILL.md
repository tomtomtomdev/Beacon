---
name: fastapi-conventions
description: >-
  FastAPI conventions distilled from the official docs plus Clean Architecture
  practice: app factory, thin routers, Pydantic-at-the-boundary, dependency
  injection via Depends, lifespan resource management, async endpoint rules,
  background work, and httpx-based testing with dependency overrides. Use this
  skill whenever building, reviewing, or debugging a FastAPI service — new
  endpoints, DTO design, DI wiring, startup/shutdown, "sync or async def",
  testing routes, auth dependencies — even if the user just says "API",
  "backend", or "endpoint" in a Python project. Pairs with the
  modern-python-conventions skill (language layer beneath this).
---

# FastAPI Conventions

Assume FastAPI 0.100+ (Pydantic v2), Python 3.11+, mypy strict. This is the
framework layer; language rules live in modern-python-conventions.

## Core stance

1. **Routers are transport, nothing else.** A route handler parses input
   (via Pydantic/params), calls one use case, serializes output. If a handler
   contains an `if` about business rules or touches the DB directly, logic
   has leaked into the transport layer.
2. **Pydantic lives at the edge.** Request/response DTOs are Pydantic;
   everything inward is plain dataclasses/domain types. Never let ORM or
   Pydantic models cross into domain logic, and never return ORM objects
   from routes.
3. **`Depends` is constructor injection.** Dependencies wire adapters to use
   cases and hold cross-cutting concerns (auth, DB session, settings).
   `app.dependency_overrides` is the test seam — design dependencies so
   overriding one swaps a whole subsystem.
4. **Resources live in lifespan.** HTTP clients, DB pools, schedulers open in
   the lifespan context manager, close on shutdown, and reach handlers via
   dependencies — never module-level globals created at import.
5. **`async def` is a contract.** An async handler must never block (no
   sync DB calls, `requests`, `time.sleep`). If the work is sync, declare the
   handler `def` — FastAPI runs it in the threadpool automatically. Mixed
   teams get this wrong constantly; it's the #1 FastAPI performance bug.
6. **Errors are responses, designed once.** Domain exceptions map to HTTP in
   one exception-handler layer; routes don't hand-roll `HTTPException`
   scattering status codes everywhere.

## Fast rules

| Situation | Rule |
|---|---|
| App creation | `create_app() -> FastAPI` factory; module-level `app = create_app()` only in the entrypoint |
| Route return | `response_model` / return-type annotation set explicitly; never leak extra fields by accident |
| Create endpoints | `status_code=201`, return the created resource with its id |
| Partial update | `PATCH` + `model_dump(exclude_unset=True)` |
| Query params | Typed function params with defaults; `Annotated[int, Query(ge=0)]` for constraints |
| Path naming | Plural nouns, no verbs: `/jobs/{job_id}`, actions as sub-resources `/jobs/{id}/refresh` |
| Auth | One dependency (`CurrentUser = Annotated[User, Depends(get_current_user)]`), reused everywhere |
| Settings | pydantic-settings `Settings`, provided via a cached dependency — not `os.environ` reads |
| Sync library (sqlite3, pandas) in async handler | `await asyncio.to_thread(...)` or make the handler `def` |
| Long work after response | Real queue/scheduler; `BackgroundTasks` only for fire-and-forget-lite (email, log) |
| Testing | httpx `AsyncClient(transport=ASGITransport(app=app))` + dependency_overrides — no live server |

## When to open a reference file

- Designing endpoints, DTOs, validation, status codes, errors, pagination →
  **references/routing-and-dtos.md**
- `Depends` patterns, auth dependencies, settings, lifespan, wiring adapters
  to use cases → **references/dependencies-and-lifespan.md**
- sync-vs-async decisions, blocking bugs, BackgroundTasks, streaming/SSE,
  websockets → **references/async-and-background.md**
- Writing tests for routes, overrides, DB fixtures, auth in tests →
  **references/testing.md**

Read dependencies-and-lifespan.md before wiring any new project; read
testing.md before the first route test.
