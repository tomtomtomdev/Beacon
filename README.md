# Beacon

**Personal tech-job scanner with visa-sponsorship awareness.**

Beacon polls public ATS APIs and API/RSS-friendly job boards on a schedule, normalizes every posting into a single local SQLite database, classifies them (category, level, sponsorship signal), cross-references official sponsor registries, and surfaces the result through a filterable web UI with new-match alerting.

It exists to answer one question that no job board answers directly: *which senior iOS / backend / AI-ML roles, in my target countries, come from employers likely to sponsor a work visa?*

> **Scope:** personal tool — single user, self-hosted, no auth, no multi-tenancy, no cloud. This is deliberate and permanent; see `SPEC.md` §2 Non-Goals.

---

## Status

Early build, shipped in vertical slices. Current: **slices 0–1 done, slice 2 next.**

| # | Slice | Status |
|---|---|---|
| 0 | Skeleton & verify gate | ✅ |
| 1 | Greenhouse → SQLite → `/jobs` → JobTable | ✅ |
| 2 | Sponsor registries → `registry_inferred` | ⬜ next |
| 3–11 | Classifier, more adapters, dedup, user status, digests, LLM fallback, countries UI, source health | ⬜ |

`PROGRESS.md` is the live source of truth for what's built; `PLAN.md` is the slice order.

## Architecture

Clean Architecture is the primary principle. Dependencies point inward; the domain and application layers never touch IO. Every external system (each ATS, the registries, the LLM, the notifier, SQLite) sits behind a port defined in `application/ports.py`.

```
domain/        pure — models, sponsorship precedence, location/name parsing. No IO.
application/   use cases + port protocols. Imports domain only. No concrete adapters.
adapters/      the only layer that touches network, disk, LLM (sources, persistence, seeds).
api/           thin FastAPI routers: parse → use case → serialize.
scheduler/     wiring only.
```

Adding a job source = a new adapter + fixture tests + one seed row, with **zero** changes to `application/` or `domain/`. If a new source forces a use-case change, the port is wrong.

**Stack:** FastAPI + plain `sqlite3` (no ORM, numbered forward-only `.sql` migrations) on Python 3.12; React 19 + TypeScript + Vite on the frontend, TanStack Query for server state, filter state in URL params.

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 18+ and npm

## Setup

```bash
make setup          # uv sync (backend) + npm install (frontend)
make verify         # full gate: ruff + mypy + pytest, then eslint + tsc + vitest
```

`make verify` must be green before every commit — it's the quality gate. If it fails to spawn `mypy`/`ruff` after moving or cloning the repo, recreate the venv (stale script shebangs): `cd backend && rm -rf .venv && uv sync`.

## Running

**1. Ingest jobs** (polls seeded companies, upserts into `beacon.db`):

```bash
cd backend
uv run python -m beacon.ingest                    # all active seeded companies
uv run python -m beacon.ingest --company tines     # just one, by ats_slug
```

**2. Serve the API** (port 8000):

```bash
cd backend
uv run uvicorn beacon.api.app:create_app --factory --port 8000
# GET /healthz  → {"status":"ok"}
# GET /jobs?q=&country=&posted_since=&limit=&offset=
```

**3. Run the frontend** (Vite dev server; proxies `/jobs` and `/healthz` to `localhost:8000`):

```bash
cd frontend
npm run dev
```

### Configuration

All env reads live in one place (`beacon/config.py`). Defaults work out of the box:

| Env var | Default | Purpose |
|---|---|---|
| `BEACON_DB_PATH` | `./beacon.db` | SQLite database file |
| `BEACON_SEEDS_PATH` | `./seeds/companies.csv` | Curated company seed list |

## Development

Every slice is built **TDD, strictly**: RED (one failing test) → GREEN (smallest change) → **REFACTOR** (mandatory smell-check after each green). One slice at a time; don't start slice N+1 while N has unchecked acceptance boxes.

- **Fixtures over live calls.** Adapter tests run against recorded fixtures in `backend/tests/fixtures/{source}/`; live network only in manual acceptance checks.
- **The pipeline never dies on one bad item** — per-posting try/except, log, continue.
- **Sponsorship is a soft signal**, never a default filter. Tier drives `sort_rank` and default ordering (`sort_rank DESC, posted_at DESC`); `explicit_no` sorts last but stays visible.

Working conventions for contributors (and Claude Code) live in `CLAUDE.md`.

## Project layout

```
backend/
  beacon/
    domain/           pure models + logic (job, company, sponsorship, location, descriptions, countries)
    application/      ingest use case, port protocols, queries
    adapters/         sources/ (greenhouse, factory), persistence/ (db, jobs, companies), seeds
    api/              app factory, routers, deps
    scheduler/        wiring
  migrations/         001_companies_jobs.sql (+ forward-only)
  tests/              unit / adapters / api / integration, with fixtures/
frontend/
  src/                jobs/ (JobsPage, FilterBar, JobTable), api/ (client + types), tokens.css
seeds/companies.csv   53 verified companies (name,ats_type,ats_slug,country_hq,priority)
deploy/               launchd plist stub for the scheduler
```

## Documentation map

| File | What it holds |
|---|---|
| `SPEC.md` | The *what* — problem, goals/non-goals, data sources, schema, country/visa reference |
| `PLAN.md` | The *order* — vertical slices and the TDD loop |
| `PROGRESS.md` | Live state — slice tracker, decisions log, open items (update every session) |
| `DESIGN.md` | Visual source of truth — "Nordic Slate & Teal" tokens and views |
| `CLAUDE.md` | Working conventions and architecture-boundary enforcement |
| `VERIFY-COUNTRIES.md` | Checklist for re-verifying country/visa reference data |
