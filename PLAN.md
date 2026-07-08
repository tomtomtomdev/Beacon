# PLAN.md — Beacon

> Companion to SPEC.md. Each slice is a full vertical: domain → application → adapter → API → UI (where applicable), driven by tests, gated by `make verify`, ended with a commit.
> Convention: write the failing test first. A slice is DONE when its acceptance check passes and PROGRESS.md is updated.

## The TDD loop (applies to every task in every slice)

```
RED      → write one failing test that names the next behavior
GREEN    → smallest change that passes; committing sins is allowed here
REFACTOR → mandatory checkpoint, not optional polish (see triggers)
VERIFY   → make verify green
COMMIT   → slice-N: <behavior>
```

**Refactor triggers — after every green, scan for these; if any fires, refactor before the next red:**

| Trigger | Typical fix |
|---|---|
| Duplication introduced to get green (3rd occurrence = act) | Extract function / table-driven data |
| Layer leak (IO, httpx, sqlite, or adapter import crept toward domain/application) | Push behind a port — **this trigger outranks all others** |
| Conditional on source/registry/tier type outside its resolver | Move into the polymorphic adapter or the single pure function |
| Function grew past one intention (mixed fetch+parse, parse+store) | Split along pipeline stage |
| Test needed heavy setup/mocks to pass | Design smell in production code — invert dependency, not the test |
| Magic literal that will recur (threshold, interval, suffix) | Named constant / Settings / keyword table |
| Name lies about behavior after the change | Rename now, while context is loaded |

Refactor only on green, in its own commit when non-trivial (`slice-N: refactor <what>`). No behavior changes during refactor — tests stay untouched and passing.

## UI build note

The frontend is fully specified in **DESIGN.md** (Claude Design freeze, "Nordic Slate & Teal", high-fidelity — exact tokens, layout, interactions). The design freeze is now **done** (supersedes the earlier "deferred" decision). Every slice with a UI half builds toward DESIGN.md, not a throwaway table:

- Slices 1–5.5 build the **Jobs view** incrementally (table → badges → filter chips → status controls) — each slice adds only its own vertical's UI, but styled per DESIGN.md tokens from the start (cheaper than restyling later).
- The **drawer, Companies, Countries, and Saved-searches views** land with the slices that make their data real (drawer+CountryPanel with slice 10, Companies-health with slice 11, Saved-searches with slice 8).
- Use the `frontend-design`, `react-conventions`, and `typescript-conventions` skills; DESIGN.md's token tables map directly to CSS custom properties. Icons via Lucide (match the described shapes). Fonts: Geist + Geist Mono.
- DESIGN.md introduces two views not in the original slice list — **Companies (source health)** and **Countries (visa reference + world map)**. These are folded into slices 11 and 10 respectively (see those slices).

---

## Slice 0 — Skeleton & verify gate

**Goal:** Empty-but-wired monorepo; `make verify` green on both stacks.

Tasks:
- `backend/`: uv-managed Python 3.12 project; FastAPI app factory; pytest + pytest-asyncio; ruff + mypy (strict)
- `frontend/`: Vite + React + TS strict; vitest + testing-library; eslint
- SQLite bootstrap: `db.py` with migration runner (plain numbered .sql files)
- `Makefile`: pinned recipe —
  ```make
  verify: verify-backend verify-frontend
  verify-backend:  ; cd backend && ruff check . && ruff format --check . && mypy . && pytest
  verify-frontend: ; cd frontend && npx eslint . && npx tsc --noEmit && npx vitest run
  test:            ; cd backend && pytest ; cd ../frontend && npx vitest run
  ```
  Test runners are pytest and vitest (confirmed); lint/typecheck stay in the gate per CLAUDE.md.
- launchd plist stub (unloaded) for the scheduler

Acceptance:
- [x] `make verify` passes from clean clone
- [x] `GET /healthz` returns `{"status":"ok"}` (one integration test)

---

## Slice 1 — Greenhouse → SQLite → /jobs → JobTable

**Goal:** One real source flowing end-to-end with keyword + country filter.

Backend tests first:
- `test_greenhouse_normalize`: fixture JSON (recorded real response, anonymized) → `NormalizedJob` fields correct (title, url, location→country parse, posted_at, external_id, content_hash)
- `test_greenhouse_fetch_uses_slug`: adapter builds `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` (httpx MockTransport)
- `test_upsert_idempotent`: same posting polled twice → one row, `last_seen_at` bumped
- `test_jobs_api_filters`: `/jobs?q=swift&country=SE` returns only matching rows

Tasks:
0. **Verify seed slugs first (manual, before any code):** hit `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` in a browser for 2–3 greenhouse seed companies; confirm JSON returns. Record the confirmed-good slugs as slice-1 test targets. A 404 = wrong slug, not a code bug — never debug the adapter against an unverified slug.
1. Domain: `NormalizedJob`, `Company`, value objects for `Country` code
2. Migration 001: `companies`, `jobs` tables (full schema from SPEC §7 — create all columns now, classifiers fill them later)
3. `GreenhouseAdapter(JobSource)` + fixture-based tests
4. Use case `ingest_source(company)` : fetch → normalize → upsert (dedupe key 1 only: `(source_id, external_id)`)
5. Seed script: `seed_companies.py` reads `seeds/companies.csv` (pinned schema `name,ats_type,ats_slug,country_hq,priority`; the delivered 53-row file). Loads all rows; `ingest_all` filters to SUPPORTED_ATS = {greenhouse, lever, ashby} — unsupported types (smartrecruiters, workable, workday, gem, bendingspoons) sit dormant until their adapter exists. Test: `test_ingest_all_skips_unsupported_ats`.
6. `GET /jobs` with query params: `q`, `country`, `limit`, `offset`, `posted_since`
7. Frontend: `JobTable` (title, company, location, posted, link) + `FilterBar` (keyword input, country multi-select). vitest: renders rows from mocked fetch; filter change refetches.

Acceptance:
- [x] `python -m beacon.ingest --company <slug>` against one real Greenhouse board inserts rows
- [x] UI shows them, keyword+country filter works
- [x] Re-run ingest → row count unchanged

---

## Slice 2 — Sponsor registries → registry_inferred tier

**Goal:** The moat. Company-level registry flags feed job-level sponsorship tier.

**Real-data findings from the actual UK register (2026-07-03 snapshot, 142k rows) — the normalizer/matcher MUST handle all of these; each is a fixture row:**
- Leading/trailing whitespace in names and cities (122 rows start with a space; `CANVA UK OPERATIONS LIMITED ` has a trailing space)
- ~13,449 duplicate org names (one row per route) → dedupe by normalized name before matching
- Entity-suffix variants: `Spotify Limited`, `Airbnb UK Limited`, `Atlassian (UK) Operations Limited`, `ADYEN N.V. LONDON BRANCH`, `Miro EMEA UK Ltd.`, `AGODA INTERNATIONAL PTE LTD`
- Punctuation chaos: `Robinhood U.K Ltd.` (U.K with one dot)
- **Trading-as**: `AgileBits UK Ltd trading as 1Password` — legal name shares zero tokens with the brand; matcher must parse `trading as`/`T/A` segments
- **False-positive traps** (must NOT match): Stripe → `STRIPE CONSULTING LIMITED`/`Stripe Partners`/`Silverstripe Advisors` (real one is `Stripe Payments UK Ltd`); Notion → `Notion Capital Managers LLP` (a VC); Linear → `Linear Investments Limited`; Grab → `GRAB + GO LTD`; Miro → `CAFE MIRO LIMITED`; Canva → `Blank Canvas`; Cohere → `Coherence Neuro Limited`
- Substring traps: Reddit ⊂ Redditch — token-boundary matching, never substring
- Junk placeholder data: literal `County (optional)` appears as a county value
- Negative controls (absent from register): Discord, Coinbase, Duolingo, Wealthsimple, Truecaller
- CRLF line endings; parse with csv module, never line splitting

**Real-data findings from the actual NL IND register (2026-07-04 snapshot, 12,886 orgs) — additional hazards:**
- **Renamed company**: seed "Bird (MessageBird)" is registered as `Messagebird B.V.` — the register keeps the old legal name. Matcher must treat parentheticals in seed names as **aliases** (test: `test_parenthetical_alias_matching`); trap nearby: `Q*BIRD B.V.` must not match
- **Substring trap of the week**: Adyen ⊂ `Gradyent B.V.` — reconfirms token-boundary-only matching; also Grab ⊂ `Grabowsky B.V.`
- **Suffix chaos**: `Plaid, B.V.` (comma before suffix), `Databricks` (bare, no suffix at all), `180 Amsterdam BV` (BV without dots), `Wetransfer` (casing differs from brand "WeTransfer" → casefold, not lower)
- **Multi-entity companies**: Backbase ×3, Picnic ×2, Adyen ×2, Mollie ×2 — any entity match flags the company (registry match is company-level, count once)
- **KvK numbers present** — exact-match key; store matched KvK in match evidence now, enables exact matching if seed rows ever gain KvK (note in schema: `match_evidence` free text)
- NL negative controls: Miro, OpenAI, Anthropic, Notion, Figma, Cohere, Culture Amp, Canva, Intercom, Agoda
- All six NL seed companies confirmed present; plus NL entities found for Spotify, Stripe, Databricks, Plaid, Airwallex, Atlassian, Uber → their `registry_flags` gain the NL bit

**Real-data findings from the actual US H-1B LCA file (FY2026 Q2, 1.04M rows / ~210k real filings, 31,587 employers) — additional hazards:**
- **The Cohere problem** — hardest case in all four registries: `Cohere US, Inc.` (the LLM company) AND `Cohere Health, Inc.` (unrelated) both file. Token-boundary matching passes both. Rule: after stripping entity suffixes AND geo tokens (US/USA/Netherlands/International/Global), the remaining token sets must be **equal**, not merely overlapping — "Cohere" == "Cohere" ✓, "Cohere" ≠ "Cohere Health" ✗. Test: `test_extra_distinctive_tokens_block_match`
- **DBA column is load-bearing**: `RealTimeBoard, Inc. dba Miro` — legal name shares nothing with the brand; match against EMPLOYER_NAME's embedded `dba X` segment AND the separate TRADE_NAME_DBA column (test: `test_dba_matching`). Same class as UK's "trading as" and NL's Bird/Messagebird
- **Geo-entity stripping earns its keep**: `Stripe, LLC`, `Airwallex US, LLC`, `Atlassian US, Inc.`, `Canva US, Inc.`, `Cohere US, Inc.`, `Backbase U.S.A. Inc.` (U.S.A. with dots), `SPOTIFY USA, INC.` (all caps), `OpenAI OpCo, LLC` (OpCo token), `Anthropic, PBC` (PBC suffix), `Notion Labs`, `Robinhood Markets`, `Faire Wholesale`, `Scale AI` (trailing space in city!)
- **Adyen files US LCAs under `Adyen N.V.`** — the Dutch legal name in US data; suffix table must be jurisdiction-agnostic
- **Only count rows with CASE_STATUS in {Certified, Certified - Withdrawn}** — Denied/Withdrawn rows are not sponsorship evidence (fixture includes a Denied Figma row that must not count)
- **~829k empty padding rows** in the sheet (openpyxl max_row lies) — ingester skips rows with empty EMPLOYER_NAME; never trust max_row for progress
- Visa classes beyond H-1B are equally valid signals: E-3 Australian (Atlassian/Canva pattern), H-1B1 Singapore/Chile
- New traps: Grab → `Grab Minds`/`Grabit Interactive`; Canva → `Mental Canvas`/`CANVAS INFOTECH`; Miro → `Mirova US`; Linear → `Maxlinear`; Ninja Van → `NinjaTech AI`/`SharkNinja`/`Tek Ninjas Solutions,LLC.` (no space before LLC)
- US negative controls (zero FY26Q2 filings): Mollie, Picnic, Agoda, Wealthsimple, Truecaller, Epidemic Sound, Mentimeter, 1Password/AgileBits, Crypto.com, Ninja Van
- Aggregate per employer: store certified-filing count as match evidence (a 3,000-filing Google ≠ a 2-filing startup for sponsorship confidence)

Backend tests first:
- `test_uk_registry_parse`: fixture CSV rows → normalized company names (strips whitespace, dedupes multi-route rows, survives CRLF and junk county values)
- `test_trading_as_extraction`: "AgileBits UK Ltd trading as 1Password" matches seed company "1Password"
- `test_false_positive_traps`: parametrized over the trap table (Stripe Consulting, Notion Capital, Linear Investments, Grab + Go, Cafe Miro, Blank Canvas, Coherence Neuro) — none may match their similarly-named seed company
- `test_token_boundary_not_substring`: "Reddit" does not match "Redditch"; "Adyen" does not match "Gradyent"; "Grab" does not match "Grabowsky"
- `test_parenthetical_alias_matching`: seed "Bird (MessageBird)" matches register "Messagebird B.V."; "Q*BIRD B.V." matches neither
- `test_dba_matching`: "RealTimeBoard, Inc. dba Miro" matches seed "Miro" (embedded dba segment + TRADE_NAME_DBA column); "Mirova US LLC" does not
- `test_extra_distinctive_tokens_block_match`: after suffix+geo stripping, token sets must be equal — "Cohere US, Inc." matches seed "Cohere"; "Cohere Health, Inc." does not
- `test_lca_certified_only`: Denied/Withdrawn LCA rows contribute nothing to registry flags; empty padding rows skipped
- `test_name_normalization`: "Spotify AB", "SPOTIFY LTD", "Spotify Technology S.A.", "Spotify Limited" → same normalized token key; suffix stripping table-driven (Ltd/Limited/LLC/LLP/N.V./AB/PTE/branch designators)
- `test_fuzzy_match_confidence`: exact-normalized = 1.0; token-overlap partial gets < 1.0; below threshold = no match
- `test_registry_flags_bitmask`: company on UK+NL registers → flags = UK|NL (bitmask members UK|NL|US|MANUAL — no SE bit exists)
- `test_sponsor_tier_registry_inferred`: job with silent text + flagged company → `registry_inferred`; unflagged company → `unknown`
- `test_default_sort_by_tier_then_date`: `/jobs` with no sort param orders by `sort_rank DESC, posted_at DESC`; `explicit_no` rows appear last but are present
- `test_tier_filter_is_opt_in`: `/jobs` without `sponsor_tier` param returns all tiers

Tasks:
1. Migration 002: add nothing (columns exist) — just `registries_meta(registry, fetched_at, row_count)` bookkeeping table
2. `RegistryIngester` protocol; implement `UKSponsorRegistry` (CSV) and `INDRegistry` (parses saved snapshot, refreshed manually in MVP). ~~MigrationsverketRegistry~~ dropped — scheme discontinued Dec 2023, no SE register exists. Add `MANUAL` flag path instead: `beacon flag-sponsor <company> --evidence "listed on relocate.me" ` CLI (or companies UI action) sets the MANUAL bit with `evidence` + `flagged_at`; test `test_manual_flag_yields_registry_inferred`, and MANUAL flags are exempt from fuzzy matching (direct company-id reference, confidence 1.0)
3. Name normalizer + fuzzy matcher (pure functions, exhaustively unit-tested — this is the highest-risk correctness area)
4. Use case `refresh_registries()` → updates `companies.registry_flags`, `match_confidence`
5. Tier resolver v1: `unknown` vs `registry_inferred` (text tiers come in slice 6); `tier_sort_rank()` pure function (yes=3, registry=2, unknown=1, no=0)
6. `/jobs` default ordering `sort_rank DESC, posted_at DESC` + optional `sort=date` param; `sponsor_tier[]` as opt-in filter param
7. UI: sponsorship badge on JobTable rows; sort toggle (tier / date) defaulting to tier; tier filter chips (off by default); JobDetail shows which registries matched and confidence

Acceptance:
- [x] Spot-check: 10 known UK/NL-registered seed companies get the correct flags; a control company gets none; one MANUAL-flagged company (e.g. a relocate.me listing) shows registry_inferred with its evidence note
- [x] `registry_inferred` never appears on a company with empty flags (property test over random rows)
- [x] Default JobTable view shows all jobs with likely sponsors on top; nothing filtered out unless tier chips are actively selected

---

## Slice 3 — Heuristic category & level classifier

**Goal:** Filterable category[] and level on every job.

Tests first (table-driven, one big parametrized test per classifier):
- Swift/SwiftUI/UIKit → ios; Kotlin/Compose → android; Dart → flutter; PyTorch/LLM/RAG/CUDA → ai-ml; Django/FastAPI/Go/gRPC → backend; React/Vue/CSS → frontend; overlapping signals → multi-label
- "Senior iOS Engineer" → senior; "Staff SWE" → staff; "Engineer III" + "5+ years" → senior; bare "Software Engineer" → unspecified
- `test_classification_cached_by_content_hash`: unchanged posting not reclassified

Tasks:
1. `HeuristicClassifier` (pure, keyword tables in a data module — easy to extend without touching logic)
2. Pipeline hook: classify on upsert when `content_hash` new/changed
3. Backfill command for existing rows
4. FilterBar: category[] and level[] multi-selects; JobTable chips

Acceptance:
- [x] Spot-check 30 real postings: category correct ≥ 90%, level ≥ 80% (log misses as fixture cases) — `scripts/spot_check_classifier.py` (live, 4 boards), 32-role + 32-eng-only samples: 0 category misclassifications, level clean; misses (space-form "back end"/"front end", java/infra/sre/aosp) folded into keyword tables + test rows 2026-07-08

---

## Slice 4 — Lever + Ashby adapters

**Goal:** Adapter contract proven for N sources.

Tests: same shape as slice 1 (fixture normalize + endpoint construction + idempotent upsert) per adapter. Add `test_all_adapters_satisfy_protocol` (registry of adapters, structural check).

Tasks: `LeverAdapter`, `AshbyAdapter`; `ingest_all()` use case iterating active companies by `ats_type`; per-host rate limiter (1 rps) + backoff wrapper shared by all adapters.

Acceptance:
- [x] One real company per ATS ingests cleanly via `ingest_all` — live 2026-07-08: `immutable` (lever) 3/3, `linear` (ashby) 25/25, 0 errors; all 28 rows classified + dated, per-host 1 rps applied via shared PoliteClient

---

## Slice 5 — Cross-source dedup

**Goal:** Same job from two sources → one canonical row.

Tests first:
- `test_simhash_near_duplicate`: same description with whitespace/boilerplate diffs → within Hamming threshold
- `test_canonicalization`: two rows, same normalized (company, title, country) + near simhash → second gets `canonical_id` of first
- `test_no_false_merge`: same company, different roles ("Senior iOS" vs "Senior Android") → not merged
- `test_jobs_api_returns_canonical_only` + sources listed on detail

Tasks: simhash impl (or `simhash` lib) on normalized description; dedup pass in pipeline post-upsert; `/jobs/{id}` detail endpoint including `duplicate_sources`; JobDetail view in UI.

Acceptance:
- [x] Seed a company present on both its Greenhouse board and RemoteOK (later) or synthetic fixture → one row in UI — **done 2026-07-08**: live-ingested `immutable` (lever, 3 real roles, dedup 0/0 — no false merges), then cloned one posting under a second `source_id` with a reformatted+footered description; dedup collapsed it (list 3→3, groups=1, duplicates=1) and `/jobs/{id}` detail listed both sources (lever + remoteok).

---

## Slice 5.5 — Per-job user status (seen / hidden / starred)

**Goal:** The daily list shows what's new, not the whole backlog — the toil this tool exists to kill.

Tests first:
- `test_status_defaults_new`: freshly ingested job has `user_status = 'new'`
- `test_status_transitions`: PATCH `/jobs/{id}/status` sets seen/hidden/starred; invalid value → 422
- `test_status_survives_repoll`: re-ingesting an unchanged job (same content_hash) does NOT reset status to new; a *changed* posting (new hash) resets to new (it's genuinely different)
- `test_default_filter_excludes_hidden`: `/jobs` without params excludes `hidden`; `status=all` includes them
- `test_new_only_view`: `/jobs?status=new` for the morning scan

Tasks:
1. Migration: `user_status` column default 'new'
2. Status resolver: on upsert, preserve existing status when content_hash unchanged; reset to 'new' on hash change (documented decision — a materially edited posting is new again)
3. `PATCH /jobs/{id}/status`; `/jobs` gains `status` filter (default excludes hidden, keeps new+seen+starred)
4. UI: seen/hide/star buttons per row; "new only" toggle (default on for the morning view); starred filter; hidden rows greyed under `status=all`

Acceptance:
- [x] Mark a job seen → it drops out of the "new only" view but stays findable — live 2026-07-08: PATCH job→seen, `status=new` total 2→1, `status=all` still lists it as seen
- [x] Re-poll leaves seen/starred intact; a company editing the JD flips it back to new — live: unchanged-hash re-upsert kept `seen`; edited-hash re-upsert reset to `new`
- [x] Hidden jobs vanish from default view, recoverable via status=all — live: PATCH job→hidden, default view drops it, `status=all` keeps it (greyed in UI)

---

## Slice 6 — Explicit sponsorship text tiers

**Goal:** `explicit_yes` / `explicit_no` from posting text, with evidence.

Tests first (parametrized phrase table):
- yes: "visa sponsorship available", "we sponsor work visas", "relocation package", "work permit assistance"
- no: "must have the right to work in the EU", "no visa sponsorship", "US citizens or green card holders only", "EU work authorization required"
- precedence: explicit text beats registry (`explicit_no` + flags → `explicit_no`)
- `sponsor_evidence` stores the matched sentence

Tasks: pattern classifier (regex tiers over sentence-split text); tier resolver v2 with precedence explicit > registry > unknown; JobDetail shows highlighted evidence sentence.

Acceptance:
- [ ] Spot-check 20 postings containing sponsorship language: tier + evidence correct ≥ 90%

---

## Slice 7 — HN Who's Hiring + JobTech adapters

**Goal:** Non-ATS shapes fit the contract.

Tests: HN — fixture Firebase API JSON: `user/whoishiring.json` → latest submitted item whose title matches "Ask HN: Who is hiring?" → `item/{id}.json` thread → fetch top-level `kids` (each `item/{kid}.json`), parse first line `Company | Location | Role` heuristic into postings; deleted/dead items and child comments ignored. JobTech — fixture response → normalized with SE country default.

Notes: official HN Firebase API (github.com/HackerNews/API) — one request per comment id, so batch with bounded concurrency (Semaphore ~10) and cache fetched ids per thread; thread re-polls only fetch unseen kids.

Tasks: `HNAdapter` (Firebase API: whoishiring user → latest thread → kids, bounded-concurrency item fetches), `JobTechAdapter`; both register as company-less sources (jobs may create shadow `companies` rows with `ats_type=none`).

Acceptance:
- [ ] Current month's HN thread ingests; obvious junk rate acceptably low on spot-check

---

## Slice 8 — Saved searches + Telegram digest

**Goal:** Daily-driver loop closes: new matches ping the phone via Telegram Bot API directly.

Tests first:
- `test_filters_json_roundtrip`: saved search serializes/deserializes to same query
- `test_match_only_new`: job matched yesterday not re-notified (`seen_matches`)
- `test_digest_format`: N matches → one message, grouped by search, title+company+country+tier+url per line; ≤4096 chars per message, split when over
- `test_match_reason_recorded`: each digest line notes *why* it matched (which search + which filters fired — e.g. "iOS · SE · registry_inferred"), stored in `seen_matches.match_reason`
- `TelegramNotifier` behind `Notifier` protocol; unit tests against `FakeNotifier`; Telegram HTTP layer tested with httpx MockTransport (sendMessage payload shape, chat_id, no parse_mode surprises)

Tasks: CRUD `/searches`; `match_saved_searches` in pipeline; `TelegramNotifier` (Bot API `sendMessage`, bot token + chat_id from Settings as `SecretStr`; plain text, 4096-char split); SavedSearches UI (create from current FilterBar state — "save this search" button). `CourierNotifier` explicitly deferred — the port makes it a drop-in later.

Acceptance:
- [ ] Create search "senior iOS, SE+NL+IE, tier≥registry_inferred" in UI → next ingest of a matching fixture job produces exactly one Telegram message

---

## Slice 9 — LLM fallback classifier

**Goal:** Ambiguous residue resolved; cost-capped.

Tests: heuristic-confident jobs never call LLM (spy); ambiguous fixture → LLM called once, cached by hash; malformed LLM JSON → logged, job keeps heuristic result (never crash pipeline); prompt asks JSON-only.

Tasks: `LLMClassifier` (Anthropic API, claude-haiku-class model, JSON-out prompt) **behind the same `Classifier` port as `HeuristicClassifier`; tests use `FakeLLMClassifier` returning canned classifications — never a live API call in the suite (honors the offline-test rule)**; confidence gate in heuristic (explicit ambiguity signal, not a magic number sprinkled around); monthly call counter in `registries_meta`-style bookkeeping.

Acceptance:
- [ ] Backfill run on full DB stays under call budget; spot-check 15 previously-`unspecified` rows improved

---

## Slice 10 — CountryPanel + RemoteOK/WWR + scheduler on

**Goal:** Reference data surfaced; breadth; hands-off operation.

Tasks:
1. Migration: `countries` table + seed from SPEC §4 (visa/pr/citizenship summaries, `verified_at`, `source_url`, `priority_tier`)
2. `GET /countries`; CountryPanel in JobDetail (job's country → visa context card, with "verified as of" date shown) — per DESIGN.md teal-tinted panel
3. **Countries view (DESIGN.md §4):** country cards grid + target-geography world-map (`<canvas>` dot-grid + lon/lat pins, primary vs nice-to-have colors, pin↔card cross-highlight). Sweden card surfaces "no sponsor registry" exactly as written.
4. Job-detail drawer (DESIGN.md §2): slide-over with sponsorship-evidence card, chips, description, country panel, sources + CTA; opening a `new` job marks it `seen` (ties to slice 5.5)
5. `RemoteOKAdapter` (JSON), `WWRAdapter` (RSS)
4. APScheduler wiring per SPEC §9 intervals; launchd plist loaded; closed-posting sweep — **absence counts only on successful polls**: the sweep increments a per-job miss counter solely when its source's poll succeeded and the job wasn't in the response; failed polls leave counters untouched (test: `test_failed_poll_never_closes_jobs`)
5. Nightly SQLite backup script

Acceptance:
- [ ] Machine reboots → scheduler resumes, next poll runs unattended
- [ ] JobDetail for a Swedish job shows the Sweden card with reform caveat
- [ ] Simulated 404 board across 5 poll cycles → zero jobs from that company gain `closed_at`

---

## Slice 11 — Source health & recovery

**Goal:** Sources die, move, and drift without corrupting data or decaying silently.

Backend tests first:
- `test_failure_taxonomy`: 404/410 → `gone`; timeout/5xx → `unreachable`; normalize exceptions on previously-ok source → `schema_drift` (parametrized over response fixtures)
- `test_quarantine_thresholds`: gone after 3 consecutive, unreachable after 10, schema_drift after 3; success at any point resets `consecutive_failures` to 0
- `test_quarantined_skipped_by_ingest_all`: quarantined companies produce zero fetch calls
- `test_quarantined_jobs_frozen`: closed-sweep ignores jobs whose company is quarantined
- `test_weekly_probe_restores`: probe succeeds → health `ok`, counters reset, polling resumes; probe fails → stays quarantined, no counter inflation
- `test_health_in_digest`: digest includes quarantine lines with company + reason + since-date; healthy state adds nothing
- `test_reslug_recovery`: updating `ats_type`/`ats_slug` + health reset on a quarantined row → next `ingest_all` polls it normally

Tasks:
1. Migration: health columns on `companies` (`consecutive_failures` default 0, `last_success_at`, `health` default 'ok', `quarantine_reason`)
2. `SourceHealth` domain logic as pure functions: `record_failure(state, kind) -> state`, `record_success(state) -> state`, `should_poll(state) -> bool` — thresholds as named constants, exhaustively table-tested
3. Pipeline integration: `ingest_source` classifies exceptions into the taxonomy and records; `ingest_all` filters by `should_poll`
4. Weekly probe job in scheduler (single fetch per quarantined company, generous timeout)
5. Registry staleness check: `fetched_at` > 45 days → digest warning line
6. API `/companies/health` + digest lines via existing Notifier
7. **Companies view (DESIGN.md §3):** summary cards (seed/supported/healthy/degraded/quarantined/adapter-pending counts) + companies table (Company · ATS·slug · HQ · Last success · Health badge with reason); plus "source stale since <date>" banner on jobs from quarantined companies. Seed line: `seed 53 · greenhouse 24 · lever 10 · ashby 11 · 8 awaiting adapters` (counts computed from the companies table, never hardcoded). CSV-edit recovery documented in README

Acceptance:
- [ ] Point a seed row at a nonsense slug → after 3 polls it's quarantined with reason `gone`, polling stops, Telegram digest reports it, its jobs never close
- [ ] Fix the slug, reset health → next cycle polls and upserts normally
- [ ] Kill network mid-cycle (simulated) → affected sources degrade, nothing closes, recovery is automatic on next success

---

## Cross-cutting rules

- Every network adapter is tested against recorded fixtures only; live calls happen solely in manual acceptance checks
- The refactor checkpoint is part of the loop, not a backlog item — a slice with fired-but-unaddressed triggers is not DONE
- No HTML parsing of hostile sites — if a source needs it, it's out of MVP scope by definition
- Pipeline never crashes on one bad posting: per-item try/except, structured log, continue
- `make verify` before every commit; a red verify never gets committed
