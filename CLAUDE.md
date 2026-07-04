# CLAUDE.md — Beacon

Working conventions for Claude Code on this repo. Read SPEC.md for the what, PLAN.md for the order, PROGRESS.md for current state. Update PROGRESS.md at the end of every session.

## Project shape

Personal tool, single user, self-hosted. FastAPI + SQLite backend (`backend/`), React + TS + Vite frontend (`frontend/`). Clean Architecture, vertical slices. No auth, no multi-tenancy, no cloud — do not add them.

## Golden rules

1. **Clean Architecture is the primary principle of this repo.** Everything else serves it. Dependency direction is inward; domain and application never touch IO; every external system (ATS, registry, LLM, Courier, SQLite) lives behind a port. When a shortcut conflicts with layer integrity, layer integrity wins — even at the cost of a slower slice. See "Architecture boundaries" below; violations are refactored immediately, never TODO'd.
2. **TDD, strictly — and the loop has three steps, not two.** RED (one failing test naming the behavior) → GREEN (smallest change; sins allowed) → **REFACTOR (mandatory checkpoint)**. After every green, run the refactor-trigger scan from PLAN.md ("TDD loop" table); if a trigger fires — duplication, layer leak, type-conditional outside its resolver, bloated function, heavy test setup, magic literal, lying name — refactor before writing the next red. Layer-leak triggers outrank all others. Refactors happen on green, change no behavior, and get their own commit when non-trivial.
3. **`make verify` before every commit.** Red verify never commits. No `--no-verify`, no skipped tests, no `# type: ignore` without an inline reason.
4. **One slice at a time.** Do not start slice N+1 work while N has unchecked acceptance boxes. Refactors triggered by the current slice's greens are in scope; speculative refactors of untouched code are not.
5. **Fixtures over live calls.** All adapter tests run against recorded JSON/CSV/XML fixtures in `backend/tests/fixtures/{source}/`. Live network calls only in manual acceptance checks, never in the test suite.
6. **The pipeline never dies on one bad item.** Per-posting try/except with structured log line, then continue. A single malformed job must not block a poll.

## Architecture boundaries (enforcement of rule 1)

```
domain/        ← pure. No imports from application/adapters/api. No IO, no httpx, no sqlite.
application/   ← use cases. Imports domain + protocols only. No concrete adapters.
adapters/      ← implements protocols. The ONLY layer that touches network, disk, LLM.
api/           ← FastAPI routers. Thin: parse → use case → serialize. No business logic.
scheduler/     ← wiring only.
```

Dependency direction is inward. If an import violates this, the fix is moving code, not adding an exception.

Key protocols (defined in `application/ports.py`):
- `JobSource`: `fetch() -> list[RawPosting]`, `normalize(raw) -> NormalizedJob`
- `RegistryIngester`: `fetch() -> list[RegistryCompany]`
- `Classifier`: `classify(job) -> Classification`
- `Notifier`: `send(digest) -> None`
- Repos: `JobRepo`, `CompanyRepo`, `SearchRepo`

New source = new adapter + fixture tests + one seed row. Zero changes to application/ or domain/. If adding a source requires touching a use case, the abstraction is wrong — stop and fix the port.

## Backend conventions

- Python 3.12, uv, ruff (line 100), mypy strict. Full type hints everywhere including tests.
- Plain `sqlite3` with thin repo classes (no ORM). Migrations are numbered `.sql` files in `backend/migrations/`, applied by `db.py` runner, forward-only.
- httpx async client, injected. Shared `polite_get()` wrapper: 1 rps per host, ETag/If-Modified-Since, exponential backoff (3 tries), 15s timeout.
- Datetimes: UTC, timezone-aware, ISO-8601 in API. `posted_at` may be null (some boards omit it) — never fabricate.
- Config via env with a single `Settings` dataclass; no config reads scattered in modules.
- Logging: structlog-style key=value single lines. Every poll logs `source= company= fetched= upserted= errors=`.
- Classifier keyword tables live in `adapters/classify/keywords.py` as data, not embedded in logic. Extending categories = editing the table + adding parametrized test rows.
- Sponsorship tier precedence is a single pure function: `explicit_no > explicit_yes > registry_inferred > unknown` — text beats registry, no beats yes. Never reimplement this logic elsewhere.
- **Sponsorship is a soft signal.** Tier drives `sort_rank` (yes=3, registry=2, unknown=1, no=0) and the default ordering `sort_rank DESC, posted_at DESC`. It must never act as a default filter: `/jobs` without params returns all tiers, and no UI state ships with tier chips pre-selected. `explicit_no` sorts last, greyed badge, still visible.

## Frontend conventions

- **DESIGN.md is the visual source of truth** — high-fidelity freeze ("Nordic Slate & Teal"). Match its tokens (hex/px/radius/shadow tables) exactly; wire described behaviors to real API/state, not the prototype's in-memory arrays. Token tables → CSS custom properties in one `tokens.css`. Icons via Lucide matching the described shapes; fonts Geist + Geist Mono.
- TS strict, no `any`. API types generated or hand-mirrored in `src/api/types.ts` — one place only.
- Server state via TanStack Query; no global client-state lib. Filter state lives in URL search params (shareable/bookmarkable filters, and it's the free undo).
- Components: function components, colocated `.test.tsx`. Test behavior (rendered rows, filter → refetch) not implementation.
- Styling: minimal, one CSS module per component or plain Tailwind if already configured — do not introduce a component library for this tool.
- Sponsorship tier badge colors and all other palette per DESIGN.md token tables (tier bg/fg/dot, source-health, status pills) — do not invent colors; consistent everywhere.

## Testing conventions

- Parametrized/table-driven tests for classifiers and name normalization — misclassifications found during spot-checks become new fixture rows (append, never delete).
- Property test (hypothesis) guards the invariant: `registry_inferred` ⇒ `company.registry_flags != 0`.
- Integration tests use a tmp SQLite file per test, real migrations applied.
- Frontend: mock fetch at the boundary (msw or vi.fn), never mock React Query internals.

## Data correctness notes

- Company name normalization is the highest-risk code in the repo. Any change to the normalizer requires running the full registry-match spot-check script (`scripts/spot_check_registry.py`) and eyeballing the diff.
- Country visa data (`countries` table) is reference material with `verified_at` dates — when updating rows, always update `verified_at` and `source_url`. Never present stale rows as current in UI copy; the "verified as of" date must render.
- `content_hash` = sha256 of normalized description; it gates re-classification and LLM spend. Do not change the normalization without a backfill plan.

## LLM usage (slice 9+)

- Haiku-class model, JSON-only prompt, one call per unseen content_hash, hard monthly counter. Heuristic result is the fallback on any LLM failure — the LLM is an upgrader, never a dependency.

## Session hygiene

- Start of session: read PROGRESS.md, run `make verify` to confirm clean baseline.
- End of session: update PROGRESS.md (slice status, decisions made, next action), commit with message `slice-N: <what>`.
- Decisions that deviate from SPEC/PLAN get a dated entry in PROGRESS.md "Decisions" — do not silently drift the spec.
