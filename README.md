# Beacon

**Personal tech-job scanner with visa-sponsorship awareness.**

Beacon polls public ATS APIs and API/RSS-friendly job boards on a schedule, normalizes every posting into a single local SQLite database, classifies them (category, level, sponsorship signal), cross-references official sponsor registries, and surfaces the result through a filterable web UI with new-match alerting.

It exists to answer one question that no job board answers directly: *which senior iOS / backend / AI-ML roles, in my target countries, come from employers likely to sponsor a work visa?*

> **Scope:** personal tool — single user, self-hosted, no auth, no multi-tenancy, no cloud. This is deliberate and permanent; see `SPEC.md` §2 Non-Goals.

---

## Status

Shipped in vertical slices. Current: **slices 0–22 done.** Running against a live
corpus — **24,478 postings, of which 8,918 are open and canonical**, from 70 seeded companies plus
the company-less boards, across 16 source adapters (15 of which have landed jobs; NAV has none).
All five sponsor registries (UK, US H-1B, NL IND, IE, CA) have been ingested since 2026-09-18.
Figures measured 2026-10-10.

| # | Slice | Status |
|---|---|---|
| 0–7 | Skeleton, Greenhouse/Lever/Ashby/HN/JobTech adapters, registries → `registry_inferred`, classifier, dedup, user status, explicit sponsorship tiers | ✅ |
| 8 | Saved searches + Telegram digest | 🟨 built; live send needs your bot token |
| 9 | LLM fallback classifier | 🟨 built and suite-verified; **parked, key-gated off** |
| 10–11 | CountryPanel, RemoteOK/WWR, launchd scheduling, source health & recovery | ✅ |
| 12 | Resume upload + fit scoring | 🟨 built and suite-verified; browser sign-off pending |
| 13–17 | Six more sources, IE/CA registries, home market (`not_required`), iOS supply widening, country attribution | ✅ |
| 18 | SPEC §4 widening (GB/NZ/TW/HK) + one country list | ✅ |
| 19 | Make coverage visible: live source health, `/registries`, no literal counts on screen | ✅ |
| 20 | Other markets — the 47 countries with jobs and no way to ask for them; closed postings finally greyed | ✅ |
| 21 | The panel stops being a gate: all jobs by default, `?focus=` becomes a filter | ✅ |
| 22 | Closed postings leave the default listing, behind a "Show closed" toggle | ✅ |

`PROGRESS.md` is the live source of truth for what's built; `PLAN.md` is the slice order.

## Architecture

Clean Architecture is the primary principle. Dependencies point inward; the domain and application layers never touch IO. Every external system (each ATS, the registries, the LLM, the notifier, SQLite) sits behind a port defined in `application/ports.py`.

```
domain/        pure — models, sponsorship precedence, location/name parsing. No IO.
application/   use cases + port protocols. Imports domain only. No concrete adapters.
adapters/      the only layer that touches network, disk, LLM (sources, persistence, seeds).
api/           thin FastAPI routers: parse → use case → serialize.
maintenance.py wiring only — launchd-fired one-shots, no always-on scheduler process.
```

Adding a job source = a new adapter + fixture tests + one seed row, with **zero** changes to `application/` or `domain/`. If a new source forces a use-case change, the port is wrong.

**Stack:** FastAPI + plain `sqlite3` (no ORM, numbered forward-only `.sql` migrations) on Python 3.12; React 19 + TypeScript + Vite on the frontend, TanStack Query for server state, filter state in URL params.

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 20.19+ (or 22.12+) and npm — Vite 8's floor. nvm works; `scripts/node-path.sh` puts it on PATH for `make` and `run.sh`

## Setup

```bash
make setup          # uv sync (backend) + npm install (frontend)
make verify         # full gate: ruff + mypy + pytest, then eslint + tsc + vitest
```

`make verify` must be green before every commit — it's the quality gate. If it fails to spawn `mypy`/`ruff` after moving or cloning the repo, recreate the venv (stale script shebangs): `cd backend && rm -rf .venv && uv sync`.

## Running

**One step:** `./run.sh` (or `make run`). It serves the cached `beacon.db` right away and polls
the sources in the background (log in `.ingest.log`). Before serving it:

- ingests any registry snapshot in `data/registries/` that is new or stale
  (`maintenance refresh-registries-if-needed`), and names any snapshot that is missing, with
  its download URL;
- sends a launch digest.

A closing digest goes out on Ctrl-C. On the very first run, with no `beacon.db` yet, the poll
blocks until it finishes. Flags: `--no-ingest`, `--wait-ingest`, `--setup`, `--help`.

The same pieces, by hand:

**1. Ingest jobs** (polls the seeded companies and company-less boards, upserts into `beacon.db`, then sends the digest):

```bash
cd backend
uv run python -m beacon.ingest                    # everything active
uv run python -m beacon.ingest --company tines     # just one ATS company, by ats_slug
uv run python -m beacon.ingest --source hn         # just one company-less source
                                                   # (hn/jobtech/remoteok/weworkremotely/himalayas/mycareersfuture/nav)
```

**2. Serve the API** (port 8000):

```bash
cd backend
uv run uvicorn beacon.api.app:create_app --factory --port 8000
```

| Route | What |
|---|---|
| `GET /healthz` | `{"status":"ok"}` |
| `GET /jobs` | filtered listing: `q`, `country`, `category`, `level`, `sponsor_tier`, `status`, `posted_since`, `include_closed`, `sort` (`tier`/`date`/`match`), `resume`, `limit` (≤200), `offset` |
| `GET /jobs/{id}` · `PATCH /jobs/{id}/status` · `POST /jobs/{id}/match` | one posting, its seen/hidden/starred status, an on-demand fit score |
| `GET/POST /searches` · `DELETE /searches/{id}` | saved searches that drive the digest |
| `GET /countries` · `GET /markets` | country visa reference; per-country open-job counts, target and other markets |
| `GET /companies/health` | source-health rollup + per-company rows |
| `GET /registries` | sponsor-registry coverage, including never-ingested registers |
| `GET/POST /resumes` · `PUT /resumes/{id}/active` · `DELETE /resumes/{id}` | resume upload for fit scoring |
| `GET/PUT /settings/telegram` · `POST /settings/telegram/test` | digest credentials, plus a test send |

**3. Run the frontend** (Vite dev server; proxies the API routes to `localhost:8000`):

```bash
cd frontend
npm run dev
```

**One-off CLIs** (all in `backend/`, all wiring only):

| Command | What |
|---|---|
| `python -m beacon.notify` | send the current digest without polling |
| `python -m beacon.refresh [--flag NAME --evidence TEXT]` | rematch seeds against the registry snapshots, or hand-flag one company as a manual sponsor |
| `python -m beacon.classify [--upgrade-residue]` | classify rows that have never been classified; with `--upgrade-residue`, re-run the LLM on rows left with no category (needs a key) |
| `python -m beacon.relocate` | re-parse the location of rows with no country (idempotent) |
| `python -m beacon.retier` | move home-market rows onto their current tier (idempotent) |
| `python -m beacon.maintenance {refresh-registries,refresh-registries-if-needed,backup,probe}` | the launchd jobs, run by hand |

Spot-check scripts for manual acceptance live in `backend/scripts/` (`spot_check_registry.py`,
`spot_check_health.py`, `spot_check_classifier.py`, …).

### Source health & recovery

Beacon treats a source failure as a first-class **state**, never as data (SPEC §7). Each poll
classifies failures — `gone` (404/410, the board moved/was removed), `unreachable` (5xx /
timeout / transport), `schema_drift` (fetched but nothing parsed, the API changed shape) — and
records them on the company. A source **quarantines** after 3 consecutive `gone`/`schema_drift`
failures or 10 `unreachable` ones; a quarantined source stops being polled and its jobs are
frozen (never closed), so a dead board can't corrupt the data. A weekly probe retries
quarantined sources and auto-restores any that recover. Health surfaces in the **source-health
widget on the globe** (`GET /companies/health` — live ok/degraded/quarantined/pending counts and
the age of the last poll) and in the Telegram digest.

Beside it, **registry coverage** (`GET /registries`) reports which sponsor registers actually
have a snapshot here, how old it is, how many rows it held and how many companies it matched —
and names the ones that have **never been ingested**. A missing snapshot is skipped silently by
`refresh.py`, so without this it is invisible: the UK register was named in the spec as ingested
for sixteen slices while no `uk_sponsors.csv` had ever been downloaded onto this box. (It, and
the US and NL snapshots, were downloaded and ingested on 2026-09-18.) Snapshots are hand
downloads into `data/registries/`; the US H-1B file has to be converted from XLSX to CSV, and the
NL register from the page's HTML to CSV. `PROGRESS.md` records both steps.

**Recovering a moved board is a data edit, no code:** a company that switched ATS provider or
renamed its slug just needs its row in `seeds/companies.csv` updated —

```bash
# edit seeds/companies.csv: change ats_type / ats_slug for the affected company, then:
cd backend && uv run python -m beacon.ingest
```

The next re-seed detects the changed `ats_type`/`ats_slug`, **resets that company's health**
(clears quarantine + counters), and the poll proceeds normally. An unchanged re-seed never
un-quarantines, so routine runs don't disturb a genuine quarantine. Live acceptance:
`uv run python scripts/spot_check_health.py`.

### Configuration

All env reads live in one place (`beacon/config.py`). Defaults work out of the box:

| Env var | Default | Purpose |
|---|---|---|
| `BEACON_DB_PATH` | `<repo>/beacon.db` | SQLite database file |
| `BEACON_SEEDS_PATH` | `<repo>/seeds/companies.csv` | Curated company seed list |
| `BEACON_BACKUPS_PATH` | `<repo>/backups` | Where `maintenance backup` writes timestamped copies |
| `BEACON_{UK,IND,H1B,IE,CA}_REGISTRY_PATH` | `<repo>/data/registries/{uk_sponsors,ind_sponsors,h1b_lca,ie_permits,ca_lmia}.csv` | Sponsor-registry snapshots |
| `BEACON_TELEGRAM_BOT_TOKEN` / `BEACON_TELEGRAM_CHAT_ID` | unset → digest prints to stdout | Fallback Telegram creds; the Settings UI's creds take precedence |
| `BEACON_ANTHROPIC_API_KEY` | unset → heuristic-only | Enables the LLM fallback classifier (slice 9, parked) |
| `BEACON_LLM_MODEL` | `claude-haiku-4-5-20251001` | Model for the LLM classifier |
| `BEACON_LLM_MONTHLY_BUDGET` | `500` | Hard cap on LLM calls per local month |
| `BEACON_NAV_API_TOKEN` | unset → NAV source not wired | NAV Norway feed token |

The scripts in `deploy/` also read `BEACON_UV`, `BEACON_HOURLY_TIMEOUT` (default 3000 s) and `BEACON_HOURLY_LOCK`.
Day and month boundaries use `Asia/Jakarta` (`config.LOCAL_TZ`); everything is stored in UTC.

### Scheduling

Four launchd agents, all installed from `deploy/`:

| Agent | When | What |
|---|---|---|
| `com.beacon.digest` | 08:45, 12:00, 16:30 local | One fire of `deploy/hourly-digest.sh`: poll → dedup → Telegram digest, then exit. Lock-guarded (a fire that finds the previous one still polling skips) and capped at 50 min, after which the digest still goes out via `python -m beacon.notify`. A full poll runs 30–45 min, which is why the gaps are hours and not one hour. |
| `com.beacon.refresh` | 1st of the month, 09:30 | `python -m beacon.maintenance refresh-registries` — rematch the seeds against the registry snapshots. |
| `com.beacon.backup` | daily, 10:00 | `python -m beacon.maintenance backup` — timestamped SQLite copy, pruned to the newest 14. |
| `com.beacon.probe` | Mondays, 10:30 | `python -m beacon.maintenance probe` — retry quarantined sources so a temporary outage self-heals. |

Every agent is a **one-shot**: no `RunAtLoad`, no `KeepAlive`, nothing running between fires.
The maintenance three ran as APScheduler crons inside an always-on `com.beacon.scheduler`
daemon until 2026-09-11. That daemon could never fire them here: a LaunchAgent lives in the
user's GUI domain, so it exists only while someone is logged in, and the Mac was asleep or
logged out at 03:00–05:00. Nine days of it running produced zero backups. On 2026-09-22 the box
was set to shut down at 06:00 and power on at 08:45 (`pmset repeat`), so the maintenance jobs
moved out of the night into the morning, after the 08:45 digest. If a fire is missed during
sleep, launchd runs it once at the next login/wake, so a late backup still happens. A fire
still needs someone logged in to run.

```bash
for agent in digest refresh backup probe; do
  cp deploy/com.beacon.$agent.plist ~/Library/LaunchAgents/
  launchctl bootout  gui/$UID/com.beacon.$agent 2>/dev/null
  launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.beacon.$agent.plist
done
```

The checkout must stay out of `~/Documents`, `~/Desktop` and `~/Downloads`: a launchd-started
job is TCC-denied there and exits 126 (`Operation not permitted`) before it runs a line, even
though the same command works by hand. This box keeps it at `~/Projects/beacon`.

Logs: `/tmp/beacon.digest.{out,err}.log` and `/tmp/com.beacon.{refresh,backup,probe}.{out,err}.log`.
A digest is sent only when a saved search has new matches, so quiet hours are genuinely quiet.

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
    domain/           pure models + logic (job, sponsorship, location, visa, vocabulary, matching, dedup)
    application/      use cases + port protocols (ingest, queries, scoring, health, coverage)
    adapters/         sources/ (16 boards + factory), persistence/, registries/ (UK, IND, H-1B, IE, CA),
                      classify/, notify/, resume/, http/
    api/              app factory, eight routers, deps
    ingest.py …       CLI entry points: ingest, notify, refresh, classify, relocate, retier
    maintenance.py    launchd one-shot entry points (refresh-registries[-if-needed], backup, probe)
  migrations/         001–010, numbered and forward-only
  scripts/            manual spot-check scripts (registry, health, classifier, locations, …) + backup_db.py
  tests/              unit / adapters / api / integration, with fixtures/
frontend/
  src/                jobs/, countries/, searches/, settings/, api/ (client + types), tokens.css
seeds/companies.csv   70 verified companies (name,ats_type,ats_slug,country_hq,priority)
data/registries/      hand-downloaded sponsor-registry snapshots (CSV)
deploy/               four launchd agents + hourly-digest.sh: digest window, registry refresh, backup, quarantine probe
scripts/node-path.sh  puts nvm's node/npm on PATH for make and run.sh
run.sh                one-step launcher (registry check → launch digest → API + background poll → Vite)
```

## Documentation map

| File | What it holds |
|---|---|
| `SPEC.md` | The *what* — problem, goals/non-goals, data sources, schema, country/visa reference |
| `PLAN.md` | The *order* — vertical slices and the TDD loop |
| `PROGRESS.md` | Live state — slice tracker, decisions log, open items (update every session) |
| `SOURCES.md` | Per-source operating reference — endpoint, auth, pagination, field normalization, quirks, for every polled source |
| `DESIGN.md` | Visual source of truth — "Nordic Slate & Teal" tokens and views |
| `CLAUDE.md` | Working conventions and architecture-boundary enforcement |
| `VERIFY-COUNTRIES.md` | Checklist for re-verifying country/visa reference data |
