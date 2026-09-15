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
- [x] Spot-check 20 postings containing sponsorship language: tier + evidence correct ≥ 90% — `scripts/spot_check_sponsorship.py` (live, 4 boards, ~530 postings carrying sponsorship language): after two fixes precision is effectively 100% on inspected rows (464 explicit_yes / 44 explicit_no; all remaining silences verified true negatives — the Visa card network, org/executive "sponsor", relocation *requirements*). Two real misses found & folded into the phrase tables + test rows 2026-07-08: (1) "not currently able to sponsor" read as YES → now NO (negation-robust regex); (2) loose relocation-offer phrasing ("relocation provided", "relocation and family support are offered") was silent → now YES.

---

## Slice 7 — HN Who's Hiring + JobTech adapters

**Goal:** Non-ATS shapes fit the contract.

Tests: HN — fixture Firebase API JSON: `user/whoishiring.json` → latest submitted item whose title matches "Ask HN: Who is hiring?" → `item/{id}.json` thread → fetch top-level `kids` (each `item/{kid}.json`), parse first line `Company | Location | Role` heuristic into postings; deleted/dead items and child comments ignored. JobTech — fixture response → normalized with SE country default.

Notes: official HN Firebase API (github.com/HackerNews/API) — one request per comment id, so batch with bounded concurrency (Semaphore ~10) and cache fetched ids per thread; thread re-polls only fetch unseen kids.

Tasks: `HNAdapter` (Firebase API: whoishiring user → latest thread → kids, bounded-concurrency item fetches), `JobTechAdapter`; both register as company-less sources (jobs may create shadow `companies` rows with `ats_type=none`).

Acceptance:
- [x] Current month's HN thread ingests; obvious junk rate acceptably low on spot-check

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
- [x] Create search "senior iOS, SE+NL+IE, tier≥registry_inferred" in UI → next ingest of a matching fixture job produces exactly one Telegram message — **verified end-to-end locally 2026-07-08** via `scripts/spot_check_digest.py`: the acceptance search + 2 matching iOS/SE+NL/registry_inferred jobs (US/backend control excluded) produce ONE grouped digest message, and a re-run notifies nothing (seen-matches dedup). Telegram `sendMessage` payload shape (chat_id, plain text, no parse_mode, one POST/message, 4096-split) proven by `test_notify.py` MockTransport; `/searches` CRUD + UI save-from-filters proven by API/frontend tests. **Live phone send pending a bot token** — set `BEACON_TELEGRAM_BOT_TOKEN`/`BEACON_TELEGRAM_CHAT_ID` and re-run the spot-check to fire a real message.

---

## Slice 9 — LLM fallback classifier

**Goal:** Ambiguous residue resolved; cost-capped.

Tests: heuristic-confident jobs never call LLM (spy); ambiguous fixture → LLM called once, cached by hash; malformed LLM JSON → logged, job keeps heuristic result (never crash pipeline); prompt asks JSON-only.

Tasks: `LLMClassifier` (Anthropic API, claude-haiku-class model, JSON-out prompt) **behind the same `Classifier` port as `HeuristicClassifier`; tests use `FakeLLMClassifier` returning canned classifications — never a live API call in the suite (honors the offline-test rule)**; confidence gate in heuristic (explicit ambiguity signal, not a magic number sprinkled around); monthly call counter in `registries_meta`-style bookkeeping.

Acceptance:
- [ ] Backfill run on full DB stays under call budget; spot-check 15 previously-`unspecified` rows improved — **mechanism built + suite-verified 2026-07-09** (LLM behind the one `Classifier` port via `TieredClassifier`; `is_ambiguous` gate; hard monthly cap in `llm_usage`; fixture/`FakeLLMClassifier` tests, never a live call). **The live run itself is pending an Anthropic key** (`BEACON_ANTHROPIC_API_KEY`): run `scripts/spot_check_llm.py` (heuristic residue → Haiku, prints improved/llm_calls; target ≥15 improved, calls < budget), then `python -m beacon.classify --upgrade-residue` to LLM-upgrade the existing `categories=''` backlog. Only this credentialed run remains — same shape as slice 8's pending live Telegram send.

---

## Slice 10 — CountryPanel + RemoteOK/WWR + scheduler on

**Goal:** Reference data surfaced; breadth; hands-off operation.

Tasks:
1. Migration: `countries` table + seed from SPEC §4 (visa/pr/citizenship summaries, `verified_at`, `source_url`, `priority_tier`)
2. `GET /countries`; CountryPanel in JobDetail (job's country → visa context card, with "verified as of" date shown) — per DESIGN.md teal-tinted panel
3. **Countries view (DESIGN.md §4):** country cards grid + target-geography world-map (`<canvas>` dot-grid + lon/lat pins, primary vs nice-to-have colors, pin↔card cross-highlight). Sweden card surfaces "no sponsor registry" exactly as written.
4. Job-detail drawer (DESIGN.md §2): slide-over with sponsorship-evidence card, chips, description, country panel, sources + CTA; opening a `new` job marks it `seen` (ties to slice 5.5)
5. `RemoteOKAdapter` (JSON), `WWRAdapter` (RSS)
4. launchd one-shots per SPEC §9 (`com.beacon.digest` for polls, `com.beacon.{refresh,backup,probe}` for maintenance — no always-on scheduler process); closed-posting sweep — **absence counts only on successful polls**: the sweep increments a per-job miss counter solely when its source's poll succeeded and the job wasn't in the response; failed polls leave counters untouched (test: `test_failed_poll_never_closes_jobs`)
5. Nightly SQLite backup script

Acceptance:
- [x] Machine reboots → scheduling resumes, next poll runs unattended — **proven end-to-end 2026-09-11**: the box booted 06:00, the agents loaded at login without a hand, and the 12:00 digest fire ran a full clean poll (59 sources, every one `errors=0`, `hourly_done exit=0 secs=2091`, `new_matches=2` → Telegram sent). Maintenance is launchd too as of the same day — `python -m beacon.maintenance {refresh-registries,backup,probe}` behind `com.beacon.{refresh,backup,probe}`, one-shot each. **The APScheduler daemon this box once ran is deleted**: a LaunchAgent lives in the user's GUI domain, so it was never alive at its own 03:00–05:00 crons and produced zero backups in nine days (PROGRESS Decisions 2026-09-11 maintenance-to-launchd). `com.beacon.backup` kickstart-verified the same day, `last exit code = 0`, first backup written since 2026-09-02.
- [x] JobDetail for a Swedish job shows the Sweden card with reform caveat — drawer CountryPanel renders `GET /countries[SE]`; live server returns SE with "scheme discontinued Dec 2023" + "reform to 8yr" caveat + verified date; `JobDrawer.test.tsx` asserts the rendered panel
- [x] Simulated 404 board across 5 poll cycles → zero jobs from that company gain `closed_at` — `test_failed_poll_never_closes_jobs` (a fetch-raising source over 5 `ingest_all` cycles never runs the sweep); the sweep only runs at the end of a successful poll

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
- [x] Point a seed row at a nonsense slug → after 3 polls it's quarantined with reason `gone`, polling stops, Telegram digest reports it, its jobs never close — **live 2026-07-09** via `scripts/spot_check_health.py`: a nonsense Greenhouse slug 404s → degraded/degraded/quarantined(gone) over 3 real polls; the pre-existing job's `closed_at` stays null; the digest health section lists it. (`test_ingest_all_quarantines_after_three_gone_polls`, `test_failed_poll_never_closes_jobs`, `test_health_in_digest`.)
- [x] Fix the slug, reset health → next cycle polls and upserts normally — **live**: editing the slug to a real board (`tines`) reset health on re-seed and the recovery poll upserted 15 jobs. Recovery is a pure CSV edit — a changed `ats_type`/`ats_slug` on re-seed clears quarantine (`test_reslug_on_reseed_resets_health`); an unchanged re-seed never un-quarantines.
- [x] Kill network mid-cycle (simulated) → affected sources degrade, nothing closes, recovery is automatic on next success — covered by `test_success_after_a_failure_restores_health` (unreachable → degraded → success restores ok) + the no-sweep-on-failed-poll guard; the weekly probe (`probe_quarantined`, `test_probe_*`) restores a source that was down long enough to quarantine.

Note: the per-job "source stale since <date>" banner on the Jobs view (DESIGN §2/§3) and the sidebar source-health footer are deferred (consistent with prior UI-defer decisions) — the Companies view + `/companies/health` + digest are the primary surfaces and cover the acceptance.

---

## Slice 12 — Resume upload + fit scoring (heuristic all-jobs; opt-in LLM per job)

**Goal:** Upload a resume; every job gets a free, deterministic fit score you can sort by; one job at a time gets an optional budget-capped LLM rationale. SPEC §11. The two-tier split (heuristic over all jobs, LLM only on demand) is the whole feasibility argument — build Tier 1 first and fully; Tier 2 is a thin, gated upgrader on top.

**Build order: 12a domain (pure) → 12b resume ingest → 12c heuristic scoring on `/jobs` → 12d UI → 12e LLM deep-match (last, gated).** Ship 12a–12d with zero LLM dependency; 12e is opt-in and parked-by-default like slice 9.

### 12a — Domain: profile + heuristic score (pure, no IO)

Tests first (table-driven, the highest-value tests in the slice — this is the correctness surface):
- `test_build_profile_extracts_skills`: resume text → `ResumeProfile` with skill token set, inferred `categories`, `level`, years — **using the same keyword tables as the classifier** (a "Senior iOS Engineer, 8 yrs Swift/SwiftUI" resume → `{ios}`, `senior`, `yoe=8`, skills⊇{swift,swiftui})
- `test_score_match_components`: parametrized — full skill overlap + category + level match → high overall; disjoint skills → low; senior resume vs junior post → level penalty; staff post → mild, not zero
- `test_score_match_sponsorship_fit`: a target-country job with `explicit_yes`/`registry_inferred` scores its sponsor sub-score above an `explicit_no` or off-strategy-country job (Beacon's differentiator)
- `test_matched_and_missing_skills`: score reports which resume skills hit the job and which job-required skills the resume lacks
- `test_score_match_is_pure`: same `(profile, job)` → identical `MatchScore` (deterministic; no clock, no IO)

Tasks:
1. Domain: `ResumeProfile`, `MatchScore` (frozen/slots value objects), `build_profile(text)`, `score_match(profile, job)` — pure functions; skill vocabulary READ from the existing `keywords.py` data (do not duplicate it). Sub-score weights as named constants.

**Refactor watch:** if `build_profile` and the classifier both start reaching into keyword data ad hoc, extract a shared read-only accessor — do not copy the tables (duplication trigger). Level-fit and category logic must stay in `score_match`, never leak a tier/level conditional into the API layer.

### 12b — Resume ingest (parse → profile → store)

Tests first:
- `test_plaintext_parser`: pasted text / `.txt` bytes → text unchanged (no dep)
- `test_pdf_parser`: fixture PDF bytes → extracted text (recorded fixture under `tests/fixtures/resume/`)
- `test_ingest_resume_sets_active`: `ingest_resume` stores `source_text` + `profile_json` + `resume_hash`, marks it active, demotes the prior active
- `test_resume_hash_dedup`: re-uploading identical text reuses the row (same `resume_hash`), does not re-profile

Tasks:
1. Migration: `resumes` + `job_match_scores` tables (SPEC §7 schema)
2. `ResumeParser` port + `PlainTextResumeParser` (zero-dep, always available) and `PdfResumeParser` (pdf→text; add the pdf dep only here, scoped like `apscheduler`). DOCX deferred behind the same port.
3. `ResumeRepo`, `MatchScoreRepo`; use case `ingest_resume`
4. `POST /resumes` (upload/paste), `GET /resumes`, `PUT /resumes/{id}/active`, `DELETE /resumes/{id}`

### 12c — Heuristic scoring wired into `/jobs` (Tier 1, cached, bounded)

Tests first:
- `test_score_jobs_for_resume_caches`: scoring a job twice with unchanged `(resume_hash, content_hash)` computes once (spy on `score_match`); a changed `content_hash` recomputes just that job
- `test_jobs_sort_match`: `/jobs?resume=<id>&sort=match` orders by `overall DESC`; **without `sort=match` the default ordering is unchanged** (sponsor_rank, then posted_at) — fit is opt-in
- `test_jobs_scores_current_page_only`: scoring is bounded to the returned window, not the whole table (assert the score lookup count == page size, not row count)
- `test_jobs_no_resume_no_scores`: `/jobs` with no `resume` param returns rows with no `match_score` and behaves exactly as before

Tasks:
1. Use case `score_jobs_for_resume(resume, jobs)` — heuristic, reads/writes `MatchScoreRepo` cache keyed `(resume_hash, content_hash)`
2. `/jobs` gains optional `resume=<id>` (attaches `match_score` to each row, scoring only the current page) and `sort=match`; default sort untouched
3. `match_score` added to the jobs list read model + DTO + `types.ts` (one place)

**Refactor watch:** reuse the existing `to_job_filters`/read-model projection; do not fork a parallel jobs query. Scoring joins onto the existing page, it does not become a second listing path.

### 12d — UI: resume upload + fit surfacing

Tasks:
1. Resume upload/paste in Settings (or a small Resume view): paste box + file input, list of resumes, set-active, delete
2. Fit badge/score on job rows when a resume is active; a `match` option in the sort control (alongside tier/date), default unchanged
3. Drawer **Fit card**: overall + sub-scores + matched/missing skill chips — styled per DESIGN.md tokens, rendered as a soft signal like the sponsorship card (never a filter-out)

Tests: rows render `match_score` when a resume is active and omit it otherwise; `sort=match` drives a refetch; Fit card renders sub-scores and matched/missing skills.

### 12e — Deep-match rationale (Tier 2, on-demand) — built as LLM 2026-07-16, replaced by a deterministic generator the same day (see PROGRESS Decisions 2026-07-16 (12e-determinism))

Tests (fixtures only, never a live call — honors the offline-test rule, same as slice 9):
- `test_deep_match_json_out`: fixture Anthropic response → `MatchRationale` (summary, strengths, gaps, verdict, sponsor note); tolerant parser, raises on unparseable
- `test_deep_match_budget_gate`: budget exhausted → no call, returns the heuristic-only result (spy); under budget → one call, cached by `(resume_hash, content_hash)`
- `test_deep_match_llm_failure_degrades`: any LLM error → heuristic score preserved, pipeline never crashes
- `test_deep_match_single_job_only`: the endpoint scores exactly one job (no whole-DB fan-out path exists)

Tasks:
1. `Matcher` port + `LLMMatcher` (raw httpx to Anthropic, thin style of `LLMClassifier`; reuses the **existing `LLMBudget`** — no second budget); use case `deep_match_job`
2. `POST /jobs/{id}/match?resume=<id>` → runs Tier 2 for one job, stores `llm_rationale`, returns it
3. Drawer "Assess fit" button calls it; rationale renders under the Fit card
4. Wired only at the composition root via `make_matcher` (mirrors `make_classifier`): heuristic-only until `BEACON_ANTHROPIC_API_KEY` is set — the key is the switch (Decisions 2026-07-11 precedent)

Acceptance:
- [x] Upload a resume → every job on the current `/jobs` page shows a heuristic fit score; `sort=match` ranks by it; default sort unchanged; scoring a full result set is instant and free (Tier-1 covers all jobs) — **12c/12d, suite-verified + manual end-to-end spot-check 2026-07-15** (real app + temp DB: registry iOS/NL role 96, off-strategy junior Android 17, no-resume rows null); browser sign-off owed
- [x] Re-poll of an unchanged job reuses its cached score; a materially edited posting (new `content_hash`) re-scores only itself — `test_score_jobs_for_resume_caches`, `test_changed_content_hash_recomputes_only_that_job` (12c); (the 12e Tier-2 rationale cache was removed with the deterministic rework 2026-07-16 — the rationale is recomputed per request, so nothing can go stale)
- [x] "Assess fit" on one job produces a rationale; no path deep-matches the whole DB — **REWORKED 2026-07-16: the LLM mechanism was replaced by the deterministic `build_rationale` domain generator** (`domain/rationale.py`; `deep_match_job` computes score + wording with no matcher/budget/cache; `POST /jobs/{id}/match` scores exactly one job and always returns the rationale). The former live-key acceptance step is **obsolete** — no key, no budget, nothing to degrade; suite-verified end-to-end 2026-07-16

---

## Slice 13 — More boards for iOS / Java backend / AI

**Goal:** widen source coverage for the three role families without touching `application/` or `domain/`. Four per-company ATS adapters (SmartRecruiters, Workable, Workday CxS, Teamtailor) and two company-less boards (Himalayas, MyCareersFuture). SPEC §5.1/§5.2.

**Build order: port → per-company adapters → company-less adapters → factory + seeds.** Each adapter is one RED fixture test → GREEN adapter; the factory entry is the last step so a half-built adapter can never be polled.

### 13a — `Fetcher.post_json`

- `test_post_json_sends_the_body_and_returns_the_parsed_response`, `test_post_json_shares_the_per_host_rate_limit_with_get`, `test_post_json_maps_http_failure_to_source_unavailable` — Workday CxS and MyCareersFuture expose search as POST only. GET keeps the conditional-GET cache; POST has no validators to send.

### 13b — Per-company adapters (fixtures under `tests/fixtures/{source}/`)

- **SmartRecruiters** — list pages (`limit`/`offset` against `totalFound`), then one detail GET per posting (the list has no ad text); description = the four `jobAd.sections` joined; `location.country` is lowercase ISO-2.
- **Workable** — one widget call with `details=true`; `locations[].countryCode` is the authoritative country; `published_on` is a bare date → midnight UTC.
- **Workday CxS** — slug `tenant/wdN/site` parsed into the CxS base (malformed slug → `ValueError`); POST search paged at 20; GET `{externalPath}` per posting for `jobDescription`; `postedOn` ("Posted 4 Days Ago") is relative prose and never used.
- **Teamtailor** — `{host}/jobs.json`; slug accepts a career domain or a bare tenant; the embedded schema.org `jobLocation` gives an ISO-2 country, and a remote ad with no place stays country-less.

### 13c — Company-less boards

- **Himalayas** — role queries (data, not logic: `ROLE_QUERIES`), paged to a cap, deduped by guid; hitting the cap logs `himalayas_page_cap` so a partial sweep never reads as complete; empty `locationRestrictions` = work-anywhere, no country invented.
- **MyCareersFuture** — POST search per role query + one detail GET per uuid; Singapore unless `address.isOverseas`, then the named country only; agency postings resolve `hiringCompany` over `postedCompany`.

Acceptance:
- [x] Every new adapter satisfies the `JobSource` protocol via the factory, and `SUPPORTED_ATS` covers every seeded ats_type that has one — `test_source_factory.py`
- [x] Seed rows dormant for want of an adapter now poll: smartrecruiters (3), workable (1), workday (2 → 4 with Autodesk/Workday Inc), plus teamtailor (3 new SE/NO rows) — 58 seed rows, 56 pollable
- [x] **Live acceptance 2026-08-23** on a temp DB, zero errors: Voi 83/83 (teamtailor), SmartNews 21/21 (workable), Carousell 44/44 (smartrecruiters), Clio 150/150 (workday), Himalayas 70/70, MyCareersFuture 70/70. Role density on the query-scoped boards: Himalayas 37 backend / 17 ios / 15 ai-ml, MCF 32 ai-ml / 12 ios; sponsorship text tiers fired (himalayas 1 yes, 5 no)
- [x] `make verify` green (backend 651, frontend 61)

---

## Slice 14 — Sponsorship reach (IE/CA) + supply past the seed list

**Goal:** close the two gaps the 2026-08-26 resume-match spot check exposed — every company sits at `registry_flags = 0`, and the seed list yields 24 iOS postings out of 7,507 canonical jobs. SPEC §5.3/§5.4. Registries first: they need no new port surface and they fix a systemic scoring bias, whereas every new board makes the bias worse by adding volume.

**Build order: vocabulary fix → registries → no-auth adapters → `Fetcher` auth → NAV.** 14a is first because 14c–14d multiply the volume that 14a's bugs distort.

**Blocking prerequisite — a §4 decision.** The 2026-08-26 survey assumed a target set that adds **UK** and the **Mediterranean** to §4. Arbeitnow and Reed were rejected 2026-08-23 on *geography*, and that reason holds until §4 changes. 14a/14b/14c/14d/14e are all clear of it — **do not start any UK/Mediterranean source work until §4 is settled.**

### 14a — Vocabulary + skill-fit corrections (domain, pure)

The spot check surfaced two ranking defects; both are domain-pure and testable without a single network call.

- `test_swift_the_payment_network_is_not_the_swift_language` — Anthropic's "Cash Manager, Treasury" scored **80** against an iOS resume off *"bank connectivity (SWIFT, APIs, host-to-host)"*; Adyen's "Head of Global Credit Risk" scored 76 the same way. `extract_skills` is case-insensitive, so the payments network reads as the language. Fix in `domain/vocabulary.py` as data (a negative-context guard), not as logic in the caller.
- `test_a_one_skill_job_does_not_score_full_coverage` — `_skill_fit` is `len(matched) / len(job.skills)`, so a job yielding exactly one extracted skill scores `skills_score = 100` on a single hit. That is how Spotify's C++/auth role (1 skill) outranked Truecaller's actual iOS role (3 of 4 matched). Needs a denominator floor; the weights stay where they are.
- Both misclassifications become **appended** parametrized rows per the testing conventions — never deleted.

### 14b — Registry ingesters: Ireland + Canada

Both are `RegistryIngester` implementations reading a hand-downloaded snapshot through the existing `_csvfile.iter_rows` contract. No port change, no migration — `registry_flags` is an integer column, so `Registry.IE` and `Registry.CA` are additive enum members.

- **`IEPermitsRegistry`** — DETE `employment-permits-issued-to-companies-{year}.xlsx` → CSV, refreshed monthly, company-name column. Ireland currently holds 100 postings in the DB with zero sponsorship signal.
- **`CALMIARegistry`** — TFWP positive-LMIA employers list, quarterly on open.canada.ca. **Structural twin of `H1BLCARegistry`**: aggregate filings per employer so a large sponsor reads differently from a two-filing shop. Publisher caveat to encode in the docstring, not to hide: personal-name employers are excluded, so absence is not evidence of non-sponsorship.
- `test_registry_flags_bitmask` extends `UK|NL|US|MANUAL` → `UK|NL|US|MANUAL|IE|CA`.
- Both wire into `_available_ingesters` with the same **missing snapshot is skipped, not fatal** rule, and both write `registries_meta` so the 45-day staleness nag covers them.

### 14c — The Muse adapter — **built, then dropped 2026-08-26**

Built as planned (adapter, verbatim fixture, `NormalizedJob.source_level` so the board's own `levels[]` beat the title regex, page cap logged like Himalayas), then reverted the same day when live acceptance re-probed the API:

- `q=` and `location=` are **ignored** — `q=ios engineer` and `location=Dublin, Ireland` both return the identical `total: 100845` and the identical page 1. A second filter also degrades the first: `descending=true` + category returns "Rotisserie Chicken Associate".
- There is **no ordering** — page 1 mixes 2025-04 and 2026-08 postings — and page 1 is **byte-stable across an hour** (20/20 identical ids).
- So a page-capped poll re-ingests the same 60 rows forever. The advertised 5,043 pages are reach we cannot reach, and sweeping them costs ~84 min/poll at 1 rps — slice 13 already rejected 33 min. Measured live before the revert: 60 rows → 6 classified (3 backend, 3 fullstack), **0 iOS**, 44 of 60 US.
- `source_level` went with it: a domain field no adapter sets is a schema that lies, and keeping it for a producer that may never arrive is speculative generality.
- **The lesson worth keeping:** a page count is not reach. Ask whether a firehose can be *steered* (keyword/location) or *advanced* (ordering, cursor) before counting its postings as supply.

### 14d — Recruitee / Rippling adapters (per-company ATS) — **Breezy dropped 2026-08-26**

Two factory entries shipped; each was one RED fixture test → GREEN adapter, factory entry last so a half-built adapter can never be polled.

- **Recruitee** — `GET {slug}.recruitee.com/api/offers/`, public, no auth. NL-origin: the Benelux widener. One call per board (ad text inline), the ad split across `description` + `requirements`, `country_code` authoritative, and `published_at` in the board's own `"… UTC"` format. Seeds: **bunq**, **Channable**.
- **Rippling ATS** — `GET api.rippling.com/platform/api/ats/v1/board/{slug}/jobs`. Two-step (the list carries no ad text) and the list repeats a posting per work location — 744 rows → 376 uuids on Rippling's own board — so dedup precedes the detail calls, and a detail that fails is skipped, not fatal. Seed: **Rippling**.
- ~~**Breezy HR**~~ — **dropped, not deferred.** Its public `{slug}.breezy.hr/json` carries no ad text at all (id/name/url/location/company) and `api.breezy.hr/v3` needs a token, so every posting would land with no `content_hash`, no sponsorship tier and no resume score — the failure slice 13 refused when it paid for two-step fetching instead. 36 slug probes found no live board but the vendor's own demo, so there was no honest seed row either. Reason recorded in SPEC §5.5 and PROGRESS.
- No seeded company used any of them, so **14d shipped with its seed rows or it shipped nothing** — an adapter with no seed row is untested reach.

### 14e — Auth-capable `Fetcher` → NAV Norway

- Credentials as `SecretStr` on `Settings`, exactly like `telegram_bot_token`, and configured on the **door keyed by host** (`PoliteClient(bearer_tokens={host: SecretStr})`) rather than passed to adapters — an adapter that never holds a token cannot leak one into a log, a repr, or another host's request, which is what the three tests pin. The politeness contract (1 rps/host, conditional GET, backoff, `SourceUnavailable`) is unchanged.
- **Second port extension, found while building:** `get_json(modified_since=…)`. NAV's feed is *historical* (from ~2019) and NAV documents `If-Modified-Since` as the way to choose where it starts — a filter, not a cache validator. A pinned request therefore bypasses the conditional-GET cache: two windows are two different questions sharing one url. Like `post_json` in slice 13, this is an HTTP verb on the door, not business logic.
- **What the feed actually required** (all fixture-pinned): ACTIVE filtering is mandatory because an INACTIVE item returns with its title and employer *stripped to `"..."`*; the ad text needs a detail call whose payload key is `ad_content` (the published docs still say `json`); an entry that closes between the two calls has no `ad_content` and is dropped; and titles are vocabulary-filtered before a detail call is spent — measured 4,711 ACTIVE ads over five days, **48 with a tech-shaped title (~1%)**.
- **NAV Norway** (`GET pam-stilling-feed.nav.no/api/v1/feed`, bearer token) is the payload: Norway's official register, the NO twin of JobTech, and **NO is already a §4 target** — so it needs no §4 decision. The old `arbeidsplassen.nav.no/public-feed/...` path is dead (404); do not seed it.
- Absent credentials → the adapter is simply not wired, matching the `anthropic_api_key` / Telegram precedent. It must never be a hard dependency.
- **Adzuna is NOT the justification for this port change** — it was rejected 2026-08-23 on *quota*, not auth, and the arithmetic still fails: 1,000 calls/month free tier vs. ~4,860 needed for nine countries × three pages at a 4h cycle. Auth does not fix a quota. It returns only behind a separate slower cadence, which is a scheduler change and out of scope here.
- Reed (UK) is a one-adapter follow-on **iff** SPEC §4 adds the UK as a target country.

Acceptance:
- [x] The SWIFT false positive and the one-skill-coverage inflation both have appended parametrized rows and are green (`test_vocabulary`, `test_classifier`, `test_resume`)
- [x] `Registry` covers IE + CA; `test_registry_flags_bitmask` green (and pins the bit *values* as frozen); the hypothesis invariant (`registry_inferred` ⇒ `registry_flags != 0`) still holds
- [x] A real IE and a real CA snapshot each match ≥1 seeded company — full snapshots (IE 6,360 employers / CA 7,884) match **7**: Cohere (CA), Stripe (IE+CA), OpenAI, Anthropic, Notion, Spotify, Workday (IE), plus Rippling (IE) once it was seeded. `spot_check_registry.py` diff eyeballed against both the fixtures and the full snapshots: **exactly one change either way** (Stripe gains IE off "Stripe Technology Company Limited", 57 permits), nothing lost, no trap matched
- [x] Every new adapter satisfies `JobSource` via the factory; `SUPPORTED_ATS` covers every seeded `ats_type` that has one — `test_source_factory.py`
- [x] Recruitee and Rippling each land with seed rows that poll green (Breezy dropped — see 14d)
- [x] **Live acceptance 2026-08-26** on temp DBs, zero errors: bunq 10/10, Channable 15/15 (recruitee), Rippling 376/376 (rippling; dedup found 8 duplicate groups), NAV 2/2 → 1 row (the duplicate uuid that exposed the cross-page dedup bug, fixed with its own test). Country reach from Rippling alone: US 153, IN 101, **IE 26, CA 15, AU 9, SG 3**. Registry refresh on the same DB moved **371 of 401 jobs `unknown` → `registry_inferred`** while the 5 `explicit_yes` and 1 `explicit_no` correctly kept text precedence — the first non-zero `registry_flags` in Beacon's history
- [x] Resume match re-run — **iOS supply did NOT move, and here is why.** The new sources added 402 postings and **zero iOS**: Rippling's 376 have no mobile roles at all, bunq/Channable are backend/AI shops, NAV's window yielded one fullstack ad, and The Muse (the volume play) was dropped as unsteerable. The registry half of the 2026-08-26 finding *is* fixed — every job of a matched employer moves sponsor fit 0.40 → 0.75 and `sort_rank` 1 → 2. **The structural conclusion: iOS supply is limited by which employers hire iOS, not by how many boards Beacon reads.** Widening ATS coverage buys backend/AI volume. The two sources that actually produce iOS postings are the keyword-steerable ones already shipped in slice 13 (Himalayas 17 iOS, MyCareersFuture 12 iOS). Next lever is iOS-first *seed companies* in the nine target countries, not more boards — carried to slice 15
- [x] Every source re-listed from the 2026-08-23 rejection set carries its reversal reason in PROGRESS Decisions; the two sources dropped *during* this slice (Breezy, The Muse) carry their probe evidence in SPEC §5.5
- [x] `make verify` green (backend 702, frontend 61)

---

## Slice 15 — Home market (Indonesia): the `not_required` tier — **DONE 2026-09-13**

**Goal:** make the 2026-09-01 spec amendment real. SPEC §3/§4/§5.1/§6/§7/§10, DESIGN §Overview/§1/§2/§Globe/§Tokens. Today an ID job is indistinguishable from an unknown one: **171 Indonesian postings sit at `unknown`**, sorting below every speculative registry guess — the one market whose feasibility is *certain* ranks near-worst. The docs were amended; none of it was built, and it never entered this file at all. That omission is what this slice closes.

**Build order: 15a domain (pure) → 15b write paths + backfill → 15c seeds → 15d UI.** 15a first, because every other half reads the tier table it defines.

**Two corrections to the 2026-09-01 PROGRESS backlog — neither migration it names exists to be written:**
- *"Migration: widen `sponsor_tier` to admit `not_required`"* — unnecessary. The column is `TEXT NOT NULL DEFAULT 'unknown'` and **no migration declares a CHECK constraint** on it, so a fifth value is already admissible.
- *"renumber `sort_rank`"* — not a column, so not a migration. `sort_rank` is `_SORT_RANK_CASE` (`adapters/persistence/jobs.py:23`), built at import from the domain `SORT_RANK` table. Renumbering is an edit to one dict in `domain/sponsorship.py`; the SQL follows for free.

In the event the slice needed **no migration at all** — see 15c for why the third expected one was wrong too.

### 15a — The fifth tier as a location predicate (domain, pure)

- `test_jakarta_right_to_work_is_not_required_not_explicit_no` — RED first, the case the amendment exists to settle: a job with `country='ID'` whose ad reads *"must have the right to work in Indonesia"* resolves `not_required`. Today `_WORK_AUTHORIZATION_PATTERNS` matches `\bright to work\b` and it lands `explicit_no` — rank 0 for the one certain option.
- `test_not_required_sits_outside_the_text_chain` — parametrized over all four text tiers × both registry states: when `country == 'ID'` the answer is `not_required` regardless; when it is not ID, `explicit_no > explicit_yes > registry_inferred > unknown` stays byte-for-byte what it is today. CLAUDE.md pins that chain as single-source — the predicate is evaluated **before** it, never folded into it.
- `test_sort_rank_renumbered` — yes=4, **not_required=3**, registry_inferred=2, unknown=1, no=0 (extends `test_tier_sort_rank_matches_domain_table`).
- `test_every_tier_has_a_sponsor_fit_and_a_rationale` — an exhaustiveness guard parametrized over `SponsorTier`: every member must be a key of `_SPONSOR_TIER_FIT` (`domain/resume.py:147`) and of the rationale sentence table (`domain/rationale.py:25`). Both are plain dicts, so a fifth member without a row is a `KeyError` on the first Jakarta job scored against an active resume — and this test is what stops the *next* tier from doing it again.

Tasks:
1. `SponsorTier.NOT_REQUIRED = "not_required"`; `SORT_RANK` renumbered; `HOME_COUNTRY = "ID"` as a named domain constant (magic-literal trigger — it recurs in the resolver, the backfill and the UI).
2. `resolve_tier(text_tier, registry_flags, country)` — location predicate first, the existing chain untouched beneath it. The signature change is deliberate: country is the input the amendment turns on, and a caller that cannot supply one is a caller that cannot answer the question.
3. `_SPONSOR_FIT[NOT_REQUIRED] = 1.0` — a home role carries no sponsorship risk whatsoever; it is country fit, not sponsor fit, that keeps it below a confirmed sponsor abroad. Rationale sentence per SPEC §6: no visa, no sponsor, the right already held.

### 15b — Write paths + backfill

- `test_ingest_sets_not_required_from_job_country` — `_resolve_sponsorship` (`application/ingest.py:28`) passes `job.country`. `NormalizedJob.country` already carries it, so this needs **no adapter change and no port change** — the derivation is from the job's country, never the company's HQ (SPEC §5.1), which is what makes a Jakarta req from SG-HQ Grab resolve correctly.
- `test_registry_refresh_never_demotes_a_home_job` — **the hazard worth its own test.** `resolve_registry_tier` (`adapters/persistence/jobs.py:132`) bulk-rewrites every job of a matched company whose tier is not in `_EXPLICIT_TIER_LITERALS`. Grab's Jakarta reqs are `not_required`; a Grab registry match would silently demote them to `registry_inferred` on the next refresh. `not_required` joins the protected set — it is a fact about the reader, not a claim a registry can overturn.
- `test_backfill_is_a_location_predicate_only` — the existing ID rows move to `not_required` **without re-classification**: no content_hash change, no LLM spend, no `first_seen_at` churn. ID rows already at `explicit_yes`/`explicit_no` move too (the predicate outranks the chain) — the one place this differs from the registry refresh's protected set.

Tasks: thread `country` through the two `resolve_tier` call sites (`ingest.py:36`, and the registry paths which pass the job's stored country); add the tier to the protected set; a `--backfill-home` one-shot in the existing backfill module, run once against `beacon.db`.

### 15c — Seed data: the home row and the home employers

- ~~`011_country_id.sql`~~ — **no migration at all, which is the fourth correction and one this plan got wrong too.** `006_countries.sql` says it: the `countries` table is "seeded from the domain constant `COUNTRY_REFERENCE` (domain/visa.py) at startup — a queryable projection of that source of truth". The home row is therefore a row in that constant, upserted by the seed that already runs. `priority_tier='home'` is a third value beside `primary`/`nice_to_have`. **Third correction to the backlog:** it says the visa/PR/citizenship/`verified_at`/`source_url` columns are "left NULL", but all five are `NOT NULL`. The honest fill is the copy SPEC §4 already writes ("None — right to work already held" / "n/a — citizen" / "Held"). `registry_name` is nullable but says why no register applies rather than sitting empty. `verified_at`/`source_url` carry the amendment date and the SPEC anchor — the row states a fact about citizenship, not a policy with a government URL to cite.
- Seed rows: Indonesian companies on greenhouse / lever / ashby / smartrecruiters with `country_hq=ID`, **each slug hit in a browser before it is added** (slice-1 task 0 rule: a 404 is a wrong slug, never an adapter bug). Kalibrr / Glints / Dealls stay out by decision (SPEC §5.1) — a local board is a new adapter plus a fixture suite, and the seed route already reaches the employers worth watching.
- `test_countries_endpoint_lists_the_home_row` — `/countries` returns 12 rows and the ID row carries `priority_tier='home'`.

### 15d — UI (DESIGN §1/§2/§Globe/§Tokens)

- Token trio `rgba(252,211,77,0.14)` / `#f8dd8a` / `#fcd34d`, label **"No visa needed"** — into `tokens.css`, `TIER_LABEL` (`frontend/src/jobs/taxonomy.ts:7`) and the `SponsorTier` union (`frontend/src/api/types.ts:3`). The union is exhaustive, so `tsc` points at every surface that must change.
- Indonesia home card pinned **first** in the stack with the amber `#5c4a1f` accent border and a "Home" badge; the home-market block replaces the visa legend when ID is selected; the sponsor-tier menu grows to five rows (still never pre-selected — CLAUDE.md); Jakarta becomes a selectable pin whose arc is suppressed, origin and destination being the same place.
- `test_home_card_is_pinned_first`, `test_no_visa_needed_chip_renders`, `test_selecting_jakarta_draws_no_arc`.

Acceptance:
- [x] A Jakarta ad reading "must have the right to work in Indonesia" resolves `not_required`; the text chain's behavior outside ID is unchanged — `test_resolve_tier`'s expectations are byte-identical, only a country column was added
- [x] The exhaustiveness guard fails if a sixth tier is ever added without a `_SPONSOR_TIER_FIT` and a rationale row — it fired on the first run, on both tables
- [x] Backfill moved every ID row off `unknown` — **171 on the real `beacon.db`** (169 `unknown` + 2 `registry_inferred`), 14,485 non-ID rows untouched, 0 rows left carrying evidence, second run retiered 0. No content_hash moved, so nothing re-classified and no LLM call was spent
- [x] A registry refresh immediately after the backfill demotes none of them — pinned by `test_refresh_never_demotes_a_home_market_job` against real SQLite, which **failed before the fix**: the hazard was live
- [x] `/countries` lists the ID home row; the Countries view pins it first, badges it Home, swaps the visa legend for the home-market block, and draws it no arc
- [x] Every added ID seed slug polls green on a temp DB, zero errors — **Xendit 30/30, its 8 Jakarta postings `not_required` straight out of ingest**
- [x] `make verify` green on both stacks — **800 backend + 77 frontend**, `vite build` clean

---

## Slice 16 — iOS supply: employer selection, not source coverage — **DONE 2026-09-13**

**Goal:** raise the number of *employers* posting iOS roles in the §4 countries, and measure each lever before pulling the next.

Slice 14 settled the direction empirically: three new adapters, 402 new postings, **zero iOS**. Rippling's 376 carry no mobile roles at all, bunq and Channable are backend/AI shops, NAV's window yielded one fullstack ad. iOS supply is limited by *which employers hire iOS*, not by how many boards Beacon reads. The two sources that do produce iOS postings are the keyword-steerable ones (Himalayas 17, MyCareersFuture 12) — which is the same finding from the other side: steering beats breadth.

**The discipline this slice exists to enforce:** slice 14 spent itself adding reach and then discovered the reach was the wrong axis. So here **every lever is measured before the next one is pulled**, cheapest first, and a lever that moves nothing is written down as a finding rather than quietly topped up with another.

**Build order: 16a restore the measurement → 16b steer the boards already wired → 16c iOS-first seed rows → 16d re-read and record.**

### Before 16a — two chores that distort everything after them

- **Re-poll Lever.** 486 open Lever jobs still store ~1k of truncated text (the adapter read `description` and dropped `lists`/`additional`, where the skills live — fixed 2026-09-02, never re-fetched). Every one is currently scored on a fraction of its ad: Spotify's "iOS Engineer – Subscriptions" (London, a §4 target) scores **45 truncated, 72 whole**. Measuring iOS supply before this lands means measuring it partly blind. `python -m beacon.ingest` rewrites them. **Must run before `BEACON_ANTHROPIC_API_KEY` is set**, or the re-classification spends ~486 of the 500/month budget in one poll. Do not rank "today's" jobs against a DB with a poll in flight — dedup runs at the end of the sweep (2026-09-03).
- **Make `make verify` mean what it says.** From a non-interactive shell it dies at `verify-frontend` with `npx: command not found` (exit 127), so the frontend half silently does not run while the backend half reports green — against a repo whose third golden rule is that verify gates every commit. `run.sh` already solves it (resolve `npm` from `$NVM_DIR/alias/default`, else the highest installed version); lift that block into the Makefile or a `scripts/node-path.sh` that both source.

### 16a — Restore the measurement, and write down the baseline

No new code. Re-poll Lever, then take the reading **before** changing anything, so every later number has something to be compared against:

- `uv run python scripts/spot_check_demand.py` — the company-normalized view (SCORE = capped demand, FIRMS = distinct employers, TOP = largest single contributor). **FIRMS on the iOS row is this slice's metric**, not posting count: ten reqs from one employer is a fact about that employer, not about the market.
- The resume-match re-read, per country, as slice 14's last acceptance line did it.
- Record both in PROGRESS *before* 16b. A baseline taken after the change is not a baseline.

### 16b — Steer the two boards that already produce iOS

The cheapest lever, and pure data: `ROLE_QUERIES` is a tuple in `adapters/sources/himalayas.py:22` and `adapters/sources/mycareersfuture.py:26`, three queries each, `_MAX_PAGES = 3` (60 newest matches per query per poll).

- `test_role_queries_cover_the_ios_vocabulary` — the new queries are read from the tuple, not hardcoded in a test assertion; adding one is a data edit plus a row here (the vocabulary convention, CLAUDE.md).
- Candidate widenings, each a separate row so its yield is attributable: `swift engineer`, `mobile engineer`, `senior ios developer`, `ios developer`. **Not** bare `mobile` — the slice-14 lesson about unsteerable queries applies to over-broad ones too.
- Watch the page cap: more queries × 3 pages × 1 rps is poll time. If a query hits `_MAX_PAGES` it logs `himalayas_page_cap`, and a partial sweep must never read as complete.
- **Measure before 16c.** Re-run `spot_check_demand.py`; if FIRMS on the iOS row moved, this lever was underused and may deserve more queries before any seeding.

### 16c — iOS-first seed rows

The expensive lever, so it goes last and informed. Mobile-first employers in the nine §4 countries, and the ATS types they actually use.

- **Every slug is verified before it is added** (slice-1 task 0), and slice 15 sharpened what verification means: a 200 is not enough. Of four live boards probed on 2026-09-13, **three were name collisions** — `greenhouse/flip` is a New York company, `ashby/flip` is in Stuttgart, `greenhouse/kargo` is in San Francisco. Confirm *which company* the board belongs to by reading its postings' locations, not just its status code.
- One CSV row per company (`name,ats_type,ats_slug,country_hq,priority`), no code — if adding a source needs a use-case change, the abstraction is wrong (CLAUDE.md).
- Probe across **all nine supported ats_types**, not the four SPEC §5.1 names: that list predates slices 13/14, which added smartrecruiters, workable, workday, teamtailor, recruitee and rippling. **Fix §5.1 while here** — it is stale, and it is what sent the slice-15 probe at four types first.
- A seed row with no verified board is untested reach; a company with no iOS postings today is still a valid row if it is a mobile-first employer, but say so in the commit rather than counting it as supply.

### 16d — Re-read, and record what each lever bought

- Re-run `spot_check_demand.py` and the resume match; report the iOS row's **FIRMS** delta against 16a's baseline, per lever.
- A lever that moved nothing gets written down as a finding in PROGRESS Decisions with its evidence — that record is what stopped slice 15 from re-probing the same dead slugs, and is worth more than the postings it failed to add.

Acceptance:
- [x] Lever re-poll done — **it had already happened**: the scheduled 05:00 poll on 2026-09-13 re-fetched all 482 open Lever rows (avg 4,048 chars, `lists`/`additional` present, only 38 under 1,200 and those are genuinely short Ninja Van logistics ads). Spotify London "iOS Engineer – Subscriptions" scores **77** where it scored 45 truncated — scored from stored full text, the req having closed 2026-09-07. No poll was re-run to re-prove it
- [x] `make verify` runs both halves from a non-interactive shell — `scripts/node-path.sh`, sourced by run.sh and every node-touching target (`1d56df3`). Proven both ways: 78 vitest tests actually run, and with node absent it exits 127 with a named reason instead of skipping
- [x] 16a baseline recorded in PROGRESS **before** any widening (`1cc9eb6`)
- [x] `ROLE_QUERIES` widened as data with a parametrized row each — and **two of the four candidates were rejected on measured evidence**: `swift engineer` returns *zero rows* on MyCareersFuture (ships on Himalayas, 37 firms), `mobile engineer` is 8% iOS on Himalayas (ships on MCF, 62%). Page caps logged on 5 of 6 Himalayas queries; MCF poll 1:41
- [x] Every new seed slug verified **and identity-confirmed** against its postings' locations — **one name collision caught**: `ashby/lunar` is a US healthcare company, not the Danish neobank. Eight rows added, all live-polled green on a temp DB, **zero errors**, 346 postings
- [x] SPEC §5.1 (and §2's copy of the same stale list) updated to the nine ats_types that actually have adapters
- [x] FIRMS reported per lever against the 16a baseline — **16b bought +34 employers, 16c bought +1**, and the third finding is that the metric itself was wrong (below)
- [x] `make verify` green on both stacks — **805 backend + 78 frontend**

**What each lever bought, measured (the point of the slice):**

| Lever | §4 iOS posts | §4 iOS firms | firms ex-Bjak |
|---|---|---|---|
| 16a baseline | 48 | 33 | 32 |
| 16b query widening | 86 | 67 | 66 |
| 16c seed rows | 87 | 68 | 67 |

- **16b was the lever.** Steering the two boards already wired more than doubled employer count for the cost of a data edit, and opened AU 0→5 and NL 0→1. The iOS category went 146 → 230 canonical postings.
- **16c bought exactly one measurable employer** — Mercari (JP 0→1, scoring 73) — from eight seed rows and 346 postings. The other seven are mobile-first employers with no iOS req open today; they are honest reach, not supply, and are labelled as such.
- **The plan's named metric was wrong.** "FIRMS on the `ios engineer` row" moved 26 → 27 across both levers, because it keys on *one title phrasing*; the widening's employers phrase it "iOS Developer", which appeared as a **new 35-firm row that did not exist in the baseline at all**. Use the category-scoped view or the per-country table, not that row.
- **The binding constraint is no longer employer selection — it is `parse_location`.** Proton is a genuine Swiss employer with a *"Senior iOS Software Engineer – Geneva"* req, and CH still measures 0, because the board writes bare city names and the parser reports a country only when the string names one (deliberately — SPEC forbids fabricating). **62 of Proton's 67 postings, and 141 of the 342 new ones, carry no country; DB-wide it is 42.7% of open canonical jobs.** Known misses on target-country supply: `SG - Singapore` (5 iOS jobs), `Remote - United States`, and bare `Geneva`/`Zurich`/`Toronto`/`Copenhagen`. This is a `domain/countries.py` + `parse_location` data/parsing slice, and it would move more §4 supply than another round of seeding.

---

## Slice 17 — Country attribution: teach `parse_location` what the boards actually write — **DONE 2026-09-13**

**Goal:** stop losing supply Beacon has already fetched. SPEC §4/§5.1, DESIGN §Globe/§Countries. **42.7% of open canonical jobs carry no country** (3,679 of 8,616 at slice 16's baseline; 3,814 of 8,950 when 17a re-measured), so they are invisible to every country filter, absent from the globe, and scored with `country=None`. **Shipped: 42.7% → 9.0% (809 of 8,950), written to disk, and measured on a controlled before/after — 17d re-ran the per-country table against the pre-backfill backup so no corpus drift sits in the number.** Of the 809 left, **463 are correctly uncountried and 346 are a real gap** (3.9% of the corpus). Slice 16 found the cost in one line: **Proton advertises "Senior iOS Software Engineer – Geneva" and Switzerland still measures 0 iOS employers.** That is not an employer-selection problem — the employer is seeded and the req is in the DB.

**This is not a loosening of the parser.** `location.py` is conservative on purpose ("a country is only reported when the string names one… nothing is ever fabricated") and that stays. Every rule below either reads a country the string *already names*, or looks one up in a table that says so explicitly. Where a string is genuinely ambiguous, the answer stays `None` — the same discipline as `posted_at` (SPEC forbids fabricating a date, and a country is no different).

**The re-parse is free, and was designed for.** `location.py`'s own docstring: *"The raw string is preserved on the job row, so a better parser can re-parse without re-fetching."* So the backfill needs **no network, no classifier, no key** and cannot move a `content_hash` — the same shape as slice 15's `python -m beacon.retier`.

**Sized from the real DB (2026-09-13), uncountried rows with a location string, 3,759 total — and what each bucket actually came to:**

| Bucket | Jobs | Share | Fixed by | Outcome |
|---|---|---|---|---|
| bare single token (`Amsterdam`, `San Francisco`, `Geneva`) | 1,880 | 50.0% | 17b — city table | **done** — the 313-row table, plus the HQ tie-break for 14 shared names |
| delimiter form, a part names a country (`SG - Singapore`, `Remote - United States`) | 709 | 18.9% | **17a — no guessing at all** | **done** |
| delimiter form, no country part (`AL; FL; GA; …`) | 508 | 13.5% | partly 17a (US state lists) | **done** — and 17b's table then read the *city* in the rest (`DE - Berlin` → DE) |
| comma form, unresolved tail | 268 | 7.1% | partly 17b | **done** — 26 missing country names (Serbia, Qatar, Costa Rica…) carried most of it |
| `City, <US state NAME>` (`Austin, Texas`, `Bellevue, Washington`) | 262 | 7.0% | **17a — no guessing at all** | **done** |
| genuinely borderless (`Anywhere in the World`, `Remote`, `N/A`) | 132 | 3.5% | nothing — already correct | **unchanged, by design** |

**Residue after both parser halves: 809 rows** — this paragraph predicted ~210 correct refusals and three named follow-ups (parenthetical countries 28, the hyphenless `US-Remote` family ~22, Canadian province codes in a comma tail 14). **17d measured it and the prediction was wrong by half, in both directions.** Correct refusals are **463, not ~210**, because the estimate counted only strings naming *no* country and missed the **166 that name more than one** (`"Remote (United States | Canada)"` 39 jobs, `"Dublin, London"` 9, `"US / Canada"` 5) — an equally correct refusal, since one column cannot hold two. And the gaps are **six families, not three**, led by one that was not on the list at all: a **multi-city comma list read as one "city, region"** (98). Full taxonomy in 17d below. **None of them is in slice 17's scope**; they are written down so they are not rediscovered.

**Build order: ~~17a the unambiguous parses~~ → ~~17b the city table~~ → ~~17c backfill~~ → ~~17d measure~~ — all four done 2026-09-13.** 17a first because it needed no new reference data and could ship on its own; 17b second because it carried the judgment, with the guard rails already in place. **The ordering paid off twice: 17b's dry run caught 27 wrong rows before anything was written, and 17c's pre-computed prediction meant the real run could be checked rather than trusted.**

### 17a — The parses that require no new knowledge (domain, pure) — **DONE 2026-09-13**

Each of these reads a country the string already spells out; none of them can invent one.

- `test_us_state_name_resolves_like_its_code` — parametrized: `"Austin, Texas"`, `"Bellevue, Washington"`, `"Chicago, Illinois"` → `("US", <city>)`. Today `US_STATE_CODES` holds two-letter codes only, so a full state name falls through and the function returns **`(None, None)`** — losing the city as well as the country. 262 jobs.
- `test_delimiter_form_reads_the_country_part` — `"SG - Singapore"`, `"Remote - United States"`, `"US - San Francisco"`, `"Remote - USA"`, `"US - Remote"` → the country, plus the city where one is named. The separator set is ` - `, ` – `, ` | `, `•`, `;`. 709 jobs, and **five of them are open iOS reqs in Singapore** — a §4 primary.
- `test_multi_location_takes_the_country_only_when_the_parts_agree` — `"San Francisco, CA • New York, NY • United States"` → `US`; `"Mountain View, California; San Francisco, California"` → `US`; but a string naming two *different* countries resolves to `None` (one job, one country column — a disagreement is not a country).
- `test_still_refuses_to_guess` — the guard that keeps 17a honest, parametrized over `"Anywhere in the World"`, `"Remote"`, `"N/A"`, `"EMEA"`, `"AMER"`, `"Worldwide"` → `(None, …)`. These 132 are **correct today** and must stay correct.

Tasks: extend `domain/countries.py` with `US_STATE_NAMES` (data, beside the existing codes); add the delimiter split ahead of the comma split in `parse_location`; keep every existing return path byte-identical — the existing `test_location` expectations must not move.

**Built (`f712c6d`). Measured dry run over the real DB: uncountried 3,814/8,950 (42.6%) → 2,537 (28.3%), 1,277 jobs filled, and 0 rows where the parser disagrees with an already-stored country.** §4+home: SG 164, AU 29, NL 13, IE 9, CA 8, JP 5, CH 3, DK 3, SE 1, US 897.

**Four things the plan did not foresee, three of them found by re-parsing the corpus rather than by reading the code:**
- **Position carries meaning, and it is opposite in the two forms.** In `"Chicago, IL"` the two-letter tail is Illinois; in `"IL - Tel Aviv"` the same token is Israel. So a delimiter part reads a bare code as a *country* code, and the five that collide with a state (**CA DE ID IL IN** — Canada, Germany, Indonesia, Israel, India) resolve nothing alone. `"DE - Berlin"` therefore keeps its city and waits for 17b. This replaced the planned flat "part names a country" rule.
- **A delimiter part is itself a location and must be parsed as one.** Without that recursion `"Hybrid - New York, NY"` (17 jobs) lost the US its comma tail plainly names — a regression introduced and caught by the corpus, not the test table.
- **A comma list names countries as plainly as a `;` list does.** `"Mexico, Portugal, Spain"`, `"Canada, United States"`, `"Australia, Hong Kong, Taiwan, Thailand, Vietnam"` — the old code took whichever came last, quietly making a five-country ad Vietnamese. The agreement rule planned for the `;` form had to cover the comma form too; that is what took the 13 disagreements to 0.
- `"Anywhere in the World"` and `"N/A"` were being stored **as cities**. `NON_CITY_TOKENS` now covers compass points, `Hybrid`, and placeholders.

**A constraint this handed to 17c, which the plan had wrong:** the backfill must **fill only where `country IS NULL`, never overwrite**. Several adapters establish a country without `parse_location` — jobtech and teamtailor rows store `SE` for `"Stockholm, Sverige"`, MyCareersFuture stores `SG` from its address block — so a blind re-parse would *delete* 543 correct countries. Re-parsing is a way to fill gaps, not a source of truth that outranks an adapter.

### 17b — The city table (reference data, and the risk in this slice) — **DONE 2026-09-13**

1,880 jobs, and the only part that involves judgment. **Treat a city row as the same risk class as the company-name normalizer** (CLAUDE.md): it is a data table, every row earns a parametrized test, and the diff gets eyeballed over the real DB before it is kept.

- `test_unambiguous_city_resolves_to_its_country` — `Amsterdam`→NL, `Stockholm`→SE, `Copenhagen`→DK, `Oslo`→NO, `Zurich`/`Zürich`→CH, `Bengaluru`→IN, `Bangkok`→TH, `Mexico City`→MX, `東京都中央区`→JP (62 jobs; the board writes the ward in Japanese and there is nothing ambiguous about it).
- `test_a_city_shared_with_a_us_city_does_not_resolve_alone` — **the trap this table exists to survive.** `Geneva` (CH / Illinois), `Toronto` (CA / Ohio), `Birmingham` (GB / Alabama), `Cambridge` (GB / Massachusetts), `Manchester` (GB / New Hampshire), `Athens` (GR / Georgia), `Paris` (FR / Texas), `San Jose` (US / Costa Rica), `London` (GB / Ontario — 75 jobs) → **`None` on the bare string alone.**
- `test_an_ambiguous_city_is_resolved_by_the_employer_hq` — the tie-break, and the only inference in the slice: when a city maps to several candidate countries and **one of them is the posting company's `country_hq`**, take it. Proton is `country_hq=CH`, so its `Geneva` req resolves CH while its `London`, `Barcelona` and `Vilnius` reqs do **not** become Swiss. This is disambiguation between candidates the table already names — never a fallback to the company's HQ for a city the table does not know, which would tag every remote req with the employer's address.
- `test_city_table_has_no_row_the_country_table_lacks` — an exhaustiveness guard: every value in the city table must be a known country code, so a typo'd code fails at import rather than at the first Jakarta job.

Tasks: `CITY_TO_COUNTRY: dict[str, tuple[str, ...]]` in `domain/countries.py` (a tuple because ambiguity is the normal case, not the exception); rank the rows by the real DB's own frequency table so effort lands where the jobs are; `parse_location` gains an optional `hq: str | None` for the tie-break, defaulted so every existing caller compiles unchanged. **Record the rejected rows and why** — the ambiguous-city list above is as valuable as the accepted one, and it is what stops the next session re-adding `Geneva`.

**Built. 313 city rows + 26 country names the corpus named; dry run over the real DB: uncountried 3,814/8,950 (42.6%) → 809 (9.0%), 3,005 filled, 0 disagreements with an already-stored country.** `scripts/spot_check_locations.py` was written here rather than in 17d, because it is 17b's own gate — the table cannot be judged without it. **Nothing is written to the DB yet; the backfill is still 17c.**

**The plan's ambiguity list did not survive the corpus, and the measurement is why.** Listing `Toronto`, `London` and `Paris` as shared names handed them to the HQ tie-break, which got **27 of 81 rows wrong** — Cohere is CA-hq so its 15 bare `London` reqs became Ontario's, Stripe is US-hq so its 10 `Toronto` reqs became Ohio's and its 2 `Paris` reqs became Texas's. Every miss was a multinational advertising outside its home country, which an HQ cannot detect. A row now earns a second candidate only when **both** places plausibly host jobs (employment, not cartography): Toronto OH is pop. 5,000 and Paris TX pop. 25,000, so those three resolve outright. The tie-break is left with 14 rows, all correct, and the ambiguous list keeps the names that genuinely contest — `Cambridge`/MA, `Birmingham`/AL, `Manchester`/NH, `Athens`/GA, `San Jose`/CR, `Melbourne`/FL, `Vancouver`/WA, `Geneva`/IL. See Decisions 2026-09-13 (17b).

**A second defect the corpus found, one level up:** an employer's home market could settle *one part* of a multi-location string and manufacture the agreement `_parse_many` exists to withhold — Proton's `"Paris; Geneva"` resolved CH, then FR. The hq is now read for a shared *name* and never for a list, and a part that names a place the table knows to be shared blocks agreement unless the country the other parts reached is one it could mean (`"Geneva; Zurich"` is still Swiss).

**Follow-ups this left, all measured, none in 17b's scope:** a parenthetical that names the country (`"Remote (United States)"`, `"REMOTE (US)"` — 28 jobs); the hyphenless `"US-Remote"`/`"US Remote"` family (~22); Canadian province codes in a comma tail (`"Kitchener-Waterloo, ON; Toronto, ON"` — 14). The city *column* still takes occasional junk from the comma form (`"Remote, US"` → city `Remote`), which predates 17b.

### 17c — Backfill by re-parse (no network, no key, no spend) — **DONE 2026-09-13**

**Both parser halves are dry runs; this is the one that writes.** The expected magnitude is known in advance, so the run can be checked against it rather than trusted: **3,005 rows gain a country, 809 keep `NULL`, 0 rows disagree with an already-stored country.** A run that moves a materially different number means something changed under it — stop and find out what before keeping it.

- `test_backfill_reparses_without_refetching` — rows keep their `content_hash`, `first_seen_at` and `description`; only `country`/`city` move. Second run moves zero (idempotent, like `retier`).
- `test_backfill_reresolves_the_tier_when_the_country_changed` — **the coupling that must not be missed.** `not_required` is a *location* predicate (slice 15a): a Jakarta req currently sitting at `country=NULL` becomes `ID`, and its tier must be re-resolved to `not_required` with `sort_rank` following. Conversely a row that gains a country must not have an explicit text tier overturned — the 15a precedence chain still owns that decision.
- `test_backfill_never_invents_a_country` — a row whose string still does not name one keeps `country=NULL`; the count of those is the honest residue, and it is reported rather than hidden.

Tasks: `backfill_locations` beside `backfill_home_market` in `application/backfill.py`, **filling only rows where `country IS NULL`** (see 17a — a blind re-parse deletes 543 countries an adapter established); `python -m beacon.relocate` as its one-shot composition root, modelled on `beacon/retier.py`. **Back the DB up before the first real run** (`scripts/backup_db.py` exists).

**Ran against the real DB after a backup (`backups/beacon-20260913-074737.db`), and it matched its own prediction exactly: `relocate filled=4364 residue=1741 retiered=5`.** The canonical-open share the slice is measured on went **42.6% → 9.0%** (809 of 8,950). Diffed column-by-column against the pre-run backup: **0 `content_hash`, 0 `first_seen_at`, 0 `last_seen_at`, 0 `description`, 0 `posted_at`, 0 `user_status` moved; 0 countries overwritten; 4,364 filled; 5 tiers moved.** A second run printed `filled=0 retiered=0`. The full-DB figure is larger than 17b's 3,005 because the backfill covers duplicates and closed rows too — only the canonical-open subset is what the slice's percentage is quoted against.

**The headline landed:** **CH 0 → 1 iOS employer with no new seed row** — Proton's Geneva req, resolved by the HQ tie-break, which is the slice-16 finding closed. NL also went 0 → 1, and the home market shows 3.

**Two constraints 17b handed to this one:**
- **Pass the company's `country_hq` into `parse_location`.** It is the second, defaulted argument, and it is what settles the 14 shared-name rows — Proton's `Geneva` among them. A backfill that re-parses without it leaves those rows `NULL` and **the slice's headline acceptance box (CH 0 → ≥1) cannot close**. The SQL therefore joins `companies`, exactly as `spot_check_locations.py` already does.
- **The tie-break reads `country_hq`, never `''`.** Some seed rows carry an empty HQ; an empty string is not a candidate and must not be treated as one. The domain already refuses it — do not re-implement the check in the use case.


### 17d — Measure, and eyeball the diff — **DONE 2026-09-13**

- ~~`scripts/spot_check_locations.py`, the twin of `spot_check_registry.py`~~ — **built in 17b**, because the city table could not be judged without it. It prints three sections in the order they deserve attention: DISAGREEMENTS (must stay empty — an adapter that read a structured address outranks a re-parse), the HQ-tie-break rows (the only inference in the table; read every line), and the filled diff grouped by source string. **Read it before keeping the run**, exactly as the registry spot-check is read.
- Re-run the slice-16 measurements: the per-country iOS table and `spot_check_demand.py --category ios`. **The number that settles this slice is whether CH goes 0 → ≥1** on the strength of Proton's Geneva req, with no new employer seeded. **Already checked directly after the 17c run — CH is 1 (Proton, Geneva) and NL is 1 — but `spot_check_demand.py --category ios` has not been re-run, and slice 16's own warning applies: the `ios engineer` demand ROW is a title, not a market, so read the category-scoped and per-country views.**
- Report the uncountried share against slice 16's 42.7% baseline, and the residue that is *correctly* uncountried.

**Measured, against the pre-backfill backup rather than against slice 16's write-up** — no poll has run since 06:00 and the backup is 07:47, so both tables cover the **identical 173 iOS rows** and every delta is the backfill's, with no corpus drift in it. **iOS-category rows carrying a country 139 → 165** (uncountried 34 → 8); **§4: 90 posts / 69 firms / 39 ≥70 → 102 / 73 / 41**; **CH 0 → 1** (Proton Geneva, HQ tie-break, no new seed row), US 32 → 33 firms, SG 26 → 27, CA 2 → 3; **NO and DK still zero, which is supply, not parsing**. All five of slice 16's named misses resolve corpus-wide (`SG - Singapore` 157, `Remote - United States` 94, `Toronto` 55, `Copenhagen` 8, `Geneva` 2); the globe went **49 → 66 distinct countries**.

**Two corrections the measurement forced.** (1) 17c's entry credited **NL 0 → 1** to the backfill; NL already held Arise App's `"Netherlands"` req before it — that 0 was 16a's baseline, so the gain is slice 16's. **CH is the only new §4 country this backfill opened.** (2) The residue estimate was wrong by half: ~210 predicted, **463 measured**, because the estimate counted only strings naming *no* country and missed the **166 that name more than one** (`"Remote (United States | Canada)"` 39, `"Dublin, London"` 9, `"US / Canada"` 5) — a refusal that is just as correct, since one column cannot hold two.

**The 346 real gaps, for whoever picks this lever up:** multi-city comma list read as one "city, region" **98** (not on 17b's follow-up list at all, and the largest family); country token glued to a qualifier **84** (`US-Remote`, `US Remote`, `Remote USA`); parenthetical holds the country **84** (incl. `"KOHO (CAN)"` ×9 — needs an alpha-3 table); Canadian province code/name **26**; `"X or Y"` alternatives **25** (`_is_city` rejects any segment containing ` or `); slash-separated **12**; bare US state name alone **9**; 8 other. **A diminishing lever, and worth saying so: slice 17 bought 33.7 points of coverage, closing all six of these would buy 3.9.**

**Reading note:** `spot_check_demand.py` counts canonicals **including closed rows** — which is what `/jobs` itself does — while the per-country table and the uncountried share are open-only (236 vs 173 for the same category). **The demand table is country-blind by construction and correctly did not move**: `ios engineer` FIRMS 27, exactly where slice 16 left it.

Acceptance:
- [x] `"Austin, Texas"` and `"SG - Singapore"` resolve; `"Anywhere in the World"` and `"Remote"` still do not; every existing `test_location` expectation is byte-identical — 64 rows in `test_location.py`, 851 backend green *(as ticked at 17a. 17b then moved exactly the expectations 17a had written as "waits for 17b" — `"Bangkok"` → TH, `"DE - Berlin"` → DE — which is the change 17b exists to make, not drift. 112 rows, 899 backend green.)*
- [x] No bare ambiguous city resolves on its own — `Geneva`, `Cambridge`, `Athens`, `Birmingham`, `Manchester`, `Melbourne`, `Vancouver`, `San Jose` each pinned by a row; `Toronto`, `London` and `Paris` **deliberately no longer on this list** (measured: 27 wrong rows), with the reasoning recorded in PROGRESS
- [x] Proton's `Geneva` req resolves CH via the employer-HQ tie-break while its `London`/`Barcelona`/`Vilnius` reqs do not become Swiss (they resolve GB/ES/LT)
- [x] Backfill re-parses with no network and no key; no `content_hash` moves, no LLM call is spent, a second run moves zero rows — verified by diffing every column against the pre-run backup, not by inspection
- [x] A job that gains `country='ID'` is re-tiered `not_required` and its `sort_rank` follows; an explicit text tier is not overturned — 5 rows moved, and `sort_rank` follows for free because it is derived from `sponsor_tier` in the ORDER BY, never stored
- [x] `spot_check_locations.py` diff eyeballed over the real DB before the run is kept; the DB is backed up first (`backups/beacon-20260913-074737.db`)
- [x] Uncountried share reported against the 42.7% baseline, with the correctly-uncountried residue named separately — **42.7% → 9.0%** (809 of 8,950), and the 809 split **by measurement, not estimate**: **463 (57%) correctly uncountried** — 297 name no country at all, **166 name more than one**, which the earlier ~210 estimate had missed entirely — and **346 (3.9% of the corpus) a real gap** in six named families. The floor is 5.2%, not 0%
- [x] **CH goes 0 → ≥1 iOS employer with no new seed row** — the slice-16 finding, closed. **CH = 1** (Proton, `Geneva`, via the HQ tie-break) measured directly against the DB after the 17c run; NL also 0 → 1. The §4 iOS table now reads US 33 firms, SG 27, AU 5, CA 3, ID 3, SE 3, CH 1, IE 1, JP 1, NL 1. *(The fact is proven; what 17d still owes is the write-up around it — `spot_check_demand.py --category ios` has not been re-run.)*
- [x] `make verify` green on both stacks — 906 backend + 78 frontend; 17d wrote no product code

---

## Slice 18 — §4 widening: reachable markets, and one country list

**Goal:** two problems with the same root — the country list is maintained in two places and only one of them is the source of truth. Measured on the real `beacon.db` (open canonical jobs, 2026-09-15):

| | open | firms | iOS | backend | AI/ML | who is producing it |
|---|---|---|---|---|---|---|
| **GB** | **480** | **47** | 3 | **30** | **20** | 47 firms incl. OpenAI, Anthropic, Stripe — already `explicit_yes` on the rows sampled |
| **HK** | 33 | 3 | 0 | 0 | 0 | Airwallex 18, Crypto.com 13, Carousell 2 |
| **TW** | 13 | 7 | 1 | 1 | 0 | Stripe 4, Spotify 2, Crypto.com 2, Agoda 2, Proton/Bjak/Binance 1 each |
| **NZ** | 8 | 4 | 0 | 1 | 0 | Databricks 3, Canva 2, Airwallex 2, Stripe 1 |

Against the current bottom of the table — **DK 27/7, CH 12/6, NO 7/3** — none of NZ/TW/HK is out of place: **HK already outranks Denmark on volume**, TW ≈ Switzerland, NZ ≈ Norway. All three enter `nice_to_have` on supply evidence rather than on enthusiasm. **But say the weak part out loud: their combined target-profile supply is 3 jobs.** This slice buys them optionality and a truthful map, not volume.

**GB is the finding that reframes the slice.** 480 open jobs — **53 of them target-profile** — are correctly countried by slice 17, fully searchable through the API (`/jobs?country=GB` → 682 total), and **unreachable in the UI**. Three independent reasons: the filter menu renders from a hardcoded `COUNTRY_OPTIONS` array with no GB row (`FilterBar.tsx:124`); `countryName('GB')` falls through to `?? code` so the heading would read "Jobs · GB" (`taxonomy.ts:71`); and there is no `PIN_GEO` entry, so the globe cannot select it. Filter state lives in URL params (`searchParams.getAll('country')`), so **hand-editing the URL to `?country=GB` works today** and renders degraded when it does. SPEC §4 excluded the UK as a *relocation target* deliberately — it never said the jobs should be unreachable, and the sponsorship signal is already there because the UK register is already ingested.

**The structural cause, which this slice fixes first:** `COUNTRY_OPTIONS` (`taxonomy.ts:50`) is a **hand-maintained duplicate** of `COUNTRY_REFERENCE` (`domain/visa.py`), which `/countries` already serves and which `CountriesPage` already consumes. Two sources of truth for one table. Adding three rows without fixing this means editing both files and shipping a silent bug the first time one is forgotten — a country with a globe pin and no filter checkbox.

**What this costs, verified against the code rather than assumed:** no new adapter, no new port, no schema change, no new seed company, and no migration. `006_countries.sql` says the `countries` table is "seeded from the domain constant `COUNTRY_REFERENCE` at startup — a queryable projection of that source of truth", upserted by the seed that already runs; the same finding that made 15c need no migration. Tests are count-agnostic (`test_countries_repo.py:50`), so rows do not break the suite. The globe caption is **already derived** (`CountriesPage.tsx:87` renders `{countries.length} markets`) — only DESIGN.md's frozen "11 markets + home" copy goes stale.

**Build order: 18a one country list (no §4 decision needed) → 18b verify the figures → 18c the rows → 18d globe + UI → 18e the NZ register (gated).** 18a leads because it is a pure refactor that every later sub-slice would otherwise duplicate work against.

### 18a — One country list, and GB reachable (frontend; no §4 decision required)

The refactor that has to happen before rows are added, not after. **Behavior-preserving for the twelve existing markets** — it changes where the list comes from, not what it contains.

- `test_filter_menu_lists_the_markets_the_api_serves` — RED first: the filter menu renders one row per `/countries` entry, tier badge included, with no hardcoded array behind it. Mock at the fetch boundary (msw/`vi.fn`), never React Query internals.
- `test_country_name_never_falls_back_to_a_bare_code` — the `?? code` fallback is the bug that would render "Jobs · GB". Once names come from the API the fallback is unreachable for any served country; keep it for genuinely unknown codes but pin that a served country resolves its real name.
- Delete `COUNTRY_OPTIONS`; `countryName` and `COUNTRY_NAMES` derive from the `['countries']` query that `CountriesPage` already runs, so the cache is shared and no second request is made. `PriorityTier` stays in `types.ts` — the tier badge is presentation, the list is data.
- **The GB question this sub-slice does *not* decide:** deriving from `/countries` alone leaves GB exactly as stranded, because GB has no row. Two ways out, and they are a product decision (see the decision box below): **promote GB to a §4 row** (18c covers it), or add an **"other markets" affordance** — the countries that have jobs but are not relocation targets, from a distinct-country rollup — so 480 GB jobs, and the rest of the 66-country tail slice 17 opened up, stop being invisible. **Until one of the two ships, 18a's acceptance is the refactor only; GB stays unreachable and that is stated, not quietly tolerated.**

### 18b — Verify the figures before a single row is written (owner-run; gates 18c)

**The slice's real cost, and it is not code.** CLAUDE.md is explicit: country visa data carries `verified_at` + `source_url`, and stale rows must never render as current. Three-to-four rows × five prose columns of policy that changes without notice — **none of it may be written from memory or from a model's recollection, including mine.** 18c does not start until this table is filled from official pages.

For each market, confirm and capture a `source_url`: the **entry work visa** and its salary/points threshold; the **PR path** and its clock; the **citizenship endpoint** — and for this profile specifically, whether **dual citizenship** is permitted, since Indonesia bars it for adults and SPEC §4 therefore distinguishes PR from citizenship deliberately; and whether a **public employer register** exists.

Three claims to check rather than assume, each of which changes what gets built:
1. **NZ is believed to publish a public accredited-employer list (AEWV).** If true it is the only registry candidate of the three and 18e is live; if it is not downloadable as a table, 18e dies here.
2. **TW's Gold Card is believed to be self-sponsored** — an open work permit obtained by the applicant with no employer sponsor. If true it changes the *copy*, not the tier logic (see 18d's refactor watch).
3. **HK's citizenship endpoint is believed to be effectively closed** (PRC nationality law), leaving PR as the real endpoint. The row must say so plainly rather than leave the column vague.

These rows get a **real `verified_at` of the date they are checked — not `_AS_KNOWN`** (`domain/visa.py:14`, the table-wide Jan 2026 date the existing twelve share). A row verified in September must not inherit January's date.

### 18c — The `CountryReference` rows (domain, pure)

- `test_countries_endpoint_lists_the_new_markets` — RED first: `/countries` returns the new count; NZ/TW/HK each carry `priority_tier='nice_to_have'`.
- `test_every_country_row_is_verifiable` — a guard over **all** of `COUNTRY_REFERENCE`, not just the new rows: every `source_url` is `https://`, every `verified_at` is a real date not in the future, no summary column is empty. Cheap, and it is what stops row sixteen being added with a blank PR path.
- `test_new_rows_do_not_share_the_table_wide_knowledge_date` — pins 18b's rule.

Tasks: the `CountryReference` entries, filled from 18b's table. `registry_name` states why no register applies where none does — the Sweden row is the precedent for a note that explains an absence instead of sitting empty. **HK's `citizenship_summary` states the endpoint limitation directly**; a market is allowed to be honestly unattractive, and a vague column reads as missing research.

### 18d — Globe + UI (DESIGN §1/§Globe)

- `PIN_GEO` gains an entry per new market (`globeGeo.ts:71`), country-centroid values in the existing style.
- **Taiwan needs a `LAND` trace and the others do not** — the one real geometry finding. `LAND` already carries New Zealand's North and South islands, and Hong Kong sits on the traced Pearl River Delta coastline, but **Taiwan is not an island in the outline**: the Eurasia path runs up the mainland Fujian coast, so a TW pin would float in open sea. Trace it as its own entry beside Japan / Sri Lanka / Tasmania, **from the same Natural Earth 1:110m silhouettes the file header cites** — traced, not eyeballed. (GB, if promoted, needs none: "Great Britain" is already traced.)
- `test_every_country_has_a_pin` — an exhaustiveness guard in the 15a spirit: every code `/countries` serves has a `PIN_GEO` entry. A country row without a pin is a market that renders in the card stack and nowhere on the globe. This is the test that makes 18a's single list actually safe.
- **No caption change** — `CountriesPage.tsx:87` already derives the count. **DESIGN.md does need one**: its "live beacon field · 11 markets + home" (§1 bottom-left caption) is frozen copy the code outgrew; update it to describe the derived count rather than a number, so it cannot rot again.
- The idle tour picks new markets up for free — it rotates whatever `codes` it is handed (`useIdleTour.ts:22`).

**Refactor watch — the trap in this slice.** If 18b confirms TW's Gold Card is self-sponsored, there will be a pull toward teaching `resolve_tier` about it, the way 15a taught it Indonesia. **Do not.** `not_required` is a location predicate for the *home* market — the one place the reader already holds the right to work. A Gold Card is still a permit somebody has to obtain, so TW is an ordinary market whose sponsorship tier means exactly what it means everywhere else. The Gold Card belongs in the country card's `visa_summary` copy. A second location predicate in the resolver is the CLAUDE.md single-source rule breaking, and it would be the layer-leak trigger that outranks all others.

### 18e — The NZ accredited-employer register (gated on 18b.1)

Only NZ of the three plausibly has one, and it is what would move NZ off a wall of `unknown` into `registry_inferred` — the NL/IE/CA pattern, and the reason NZ leads the three rather than HK's larger volume.

- `Registry.NZ = 64` — the next free bit. Values are **frozen and append-only** (`domain/registry.py:19`): `registry_flags` is a stored integer column, so renumbering would silently re-label every company already matched.
- Adapter on the existing shape: `adapters/registries/nz.py` over `_csvfile.iter_rows` + `_evidence.counted`, fixture under `tests/fixtures/registries/nz_*.csv`, exactly as `ie.py` and `ca.py` are built. Zero changes to `application/` or `domain/` beyond the bit — if it needs more, the port is wrong (CLAUDE.md).
- The snapshot is a **hand download into `data/registries/`** (gitignored, this box only) like IE/CA, and `registries_meta` nags after 45 days. Note the standing debt this adds to: the IE/CA snapshots already need a manual refresh, and this makes three.
- The property test already in the suite covers the new bit for free: `registry_inferred` ⇒ `registry_flags != 0`.
- **Kill criterion, stated now so it is not relitigated later:** if the register is not published as a downloadable table, 18e stops and NZ ships as a `nice_to_have` whose `registry_name` says why none applies. No HTML scraping of a government site — out of MVP scope by definition (cross-cutting rules).

**GB — DECIDED 2026-09-15: promote to a full §4 row** (option (ii) of the three this plan offered). GB joins NZ/TW/HK in 18b/18c/18d as a fourth new market, with verified visa/PR/citizenship data, a globe pin and a reference card. The "other markets" affordance from 18a is **no longer needed for GB** and drops out of this slice — the 66-country tail slice 17 opened is still unreachable, but that is a separate lever and is not smuggled in here.

**Two consequences worth stating, because they are not obvious:**
1. **SPEC §4's UK note must be rewritten, not just extended.** It currently reads that the UK register is ingested "even though UK isn't a target country… presence there is a company-level 'sponsors somewhere' signal." That premise is now false. The note becomes a statement that the UK is a target market whose register is ingested directly.
2. **The UK register gets stronger, for free.** `Registry.UK` matches currently function as a *proxy* — evidence a company sponsors somewhere, used to infer tier for jobs anywhere. With GB a target country, a GB job at a UK-register company is `registry_inferred` **about the country the job is actually in**, which is the strongest form of that signal and exactly what the registry was built to say. No code change: the bit, the matcher and the tier resolver already do this; only the interpretation sharpens. Expect GB's `unknown` share to fall without a single line written.

**`priority_tier` — assumed `primary`, flip it with one word if that is wrong.** The supply case is strong: 480 open / 47 firms ranks GB **second by volume** behind SG (504) and ahead of JP (452), CA (299), NL (284), AU (238) and IE (162), with 53 target-profile jobs and sponsorship already well-evidenced. That is `primary` company on every measure this repo has. The counter-argument is not supply but endpoint — it belongs in 18b's research, not here.

Acceptance:
- [ ] `COUNTRY_OPTIONS` is deleted; the filter menu, the pane heading and the globe all read one list served by `/countries`, and the twelve existing markets behave byte-identically
- [ ] A country added to `COUNTRY_REFERENCE` alone appears in the filter menu, with its real name and tier badge, with **no frontend edit** — the duplicate is provably gone
- [ ] `test_every_country_has_a_pin` fails if a row is added without a `PIN_GEO` entry; it fired before the new pins were added
- [ ] Every figure in every new row was read off an official page and carries its own `source_url` and a `verified_at` of the date it was checked — no row inherits `_AS_KNOWN`, and nothing was written from recollection
- [ ] The verifiability guard passes over every row and fails if any is given a blank summary or a future date
- [ ] The new markets appear on the globe, in the card stack, in the filter menu and in the idle tour, with **no code change to the markets caption** (already derived)
- [ ] Taiwan is traced as its own landmass from Natural Earth 1:110m; its pin sits on land, and NZ/HK needed no new geometry
- [ ] `resolve_tier` is **byte-identical** at the end of this slice — no new location predicate, no TW special case; the Gold Card lives in `visa_summary` copy
- [ ] The already-ingested NZ/TW/HK/GB jobs surface with **no re-poll, no re-classification and no `content_hash` movement** — this slice adds reference data and deletes a duplicate; it does not touch jobs
- [x] The GB decision is recorded in PROGRESS with its reasoning — **promote to a full §4 row**, 2026-09-15
- [ ] SPEC §4's "even though UK isn't a target country" note is rewritten, not merely extended — the premise is now false
- [ ] GB's `unknown` share is measured before and after the row lands, to record what the already-ingested UK register buys once it is pointed at a target country
- [ ] 18e either lands with `Registry.NZ = 64`, a fixture-tested adapter and a real snapshot in `data/registries/` — or is recorded closed in PROGRESS with the reason
- [ ] DESIGN.md's "11 markets + home" caption no longer names a number
- [ ] `make verify` green on both stacks

---

## Slice 19 candidates — measured 2026-09-15, none chosen yet

Three levers, each measured against the real `beacon.db` rather than argued from the spec.
Recorded together so the trade is visible; picking one is a decision, not a default.

### A — Make coverage visible (the class of defect slice 18 found)

Slice 18's lesson was not "add countries". It was that **Beacon asserts things it never
measured**, found in three separate places in one session:

| assertion | reality on 2026-09-15 |
|---|---|
| SPEC §4: the UK sponsor register "is ingested" | **zero** companies carry the UK bit — no snapshot since slice 2 |
| Globe source-health widget: "44 OK / 1 degraded / 2 quarantined" | live **65 / 0 / 3**, plus **2 pending** it has no row for |
| DESIGN §1: "11 markets + home" | the code already derived the count; the copy drifted to 16 |

The third is fixed. The first is corrected in SPEC and waiting on a hand download. **The second
is still rendering false numbers on screen right now.**

The cost of the first one is the argument for this slice: `_available_ingesters`
(`refresh.py:36`) prints a skip line for a missing snapshot and nothing else, so **the single
biggest tier lever in the repo stayed invisible for sixteen slices**. A UI that showed registry
coverage would have caught it the week it happened.

Shape:
- Wire `SourceHealth` (`CountriesPage.tsx:121`) to `GET /companies/health`, which **already
  exists, is tested, and returns exactly this rollup** — `api/companies.ts` was written for it
  and has never been imported. Add the `pending` row the widget currently has no concept of.
- **One real gap to close first:** the widget renders "poll 07:04" and `HealthSummary` carries
  **no last-poll field at all**. The honest fix is a `last_poll_at` on the rollup in
  `application/company_health.py` (max `last_success_at`), not a client-side `Math.max` — it is
  a rollup, and the rollup is the application layer's job.
- Surface **registry coverage** beside it: which registries have a snapshot, its `fetched_at`,
  and how many companies matched. `registries_meta` already stores the first two and already
  nags after 45 days; today only IE (6,360 rows) and CA (7,884) appear, and **UK/NL/US are
  absent with nothing saying so**.
- Deferred UI polish that belongs with it, carried since slice 10: per-job "source stale since"
  banner, sidebar source-health footer, nav count badges.

**Honest caveat: this surfaces no new jobs.** It is maintenance, not capability — it makes the
tool stop lying about what it has. The counter-argument is that it is small and the defect is
real and on screen.

### B — The GB problem generalised: 1,808 unreachable jobs

GB was not a special case, it was the visible instance. Open canonical jobs whose country has
no §4 row, and therefore no filter checkbox, no globe pin and no card:

**1,808 jobs · 45 countries · 106 firms** — nearly four times the GB number that motivated 18a.

| | IN | MY | TH | DE | FR | CN | VN | MX |
|---|---|---|---|---|---|---|---|---|
| open | 346 | 235 | 217 | 194 | 105 | 80 | 73 | 71 |
| target-profile | 48 | 22 | 20 | 9 | — | — | — | — |

Two shapes, and they are not the same slice:
1. **A generic "other markets" affordance** — the countries that have jobs but are not
   relocation targets, from a distinct-country rollup, filterable without claiming any of them
   as a target. One feature, covers all 45, and is the option 18a explicitly deferred.
2. **Widen §4 again.** Expensive per row: each needs the hand-verified visa research 18b did,
   and 18b is the reason slice 18 took as long as it did. **The sharpest single instance is
   Germany — 194 open, a major EU tech market with an EU Blue Card route, absent from §4
   entirely.** The rest of the tail (IN/MY/TH/VN/MX) is reachable-but-probably-not-wanted,
   which is precisely the argument for (1) over fifteen more verified rows.

**The open question is not a measurement**, so it is not answerable here: whether those markets
are wanted at all. (1) is the answer that does not require deciding.

### C — The 346 remaining parser gaps (carried from 17d)

Unchanged and still specified, family by family, in 17d: multi-city comma list **98**, country
token glued to a qualifier **84**, parenthetical holds the country **84** (incl. `"KOHO (CAN)"`
needing an alpha-3 table), Canadian province code/name **26**, `"X or Y"` alternatives **25**,
slash-separated **12**, bare US state name **9**, 8 other.

17d costed it honestly and the cost has not changed: **slice 17 bought 33.7 points of country
coverage; closing all six families buys 3.9.** A day of table-and-regex work against machinery
that already exists — real, bounded, and explicitly diminishing.

---

## Cross-cutting rules

- Every network adapter is tested against recorded fixtures only; live calls happen solely in manual acceptance checks
- The refactor checkpoint is part of the loop, not a backlog item — a slice with fired-but-unaddressed triggers is not DONE
- No HTML parsing of hostile sites — if a source needs it, it's out of MVP scope by definition
- Pipeline never crashes on one bad posting: per-item try/except, structured log, continue
- `make verify` before every commit; a red verify never gets committed
