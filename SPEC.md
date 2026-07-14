# SPEC.md — Beacon

**Personal tech-job scanner with visa-sponsorship awareness**

> Status: Draft v0.1 · 2026-07-04
> Owner: Tommy Yohanes
> Type: Personal tool (single user, self-hosted, no auth, no multi-tenancy)

---

## 1. Problem Statement

Finding roles that match *both* a technical profile (iOS / backend / AI-ML, senior level) *and* a relocation strategy (specific countries, employers likely to sponsor a work visa) requires manually checking dozens of company boards and cross-referencing sponsorship likelihood by hand. No existing board exposes sponsorship as structured, filterable data.

**Beacon** polls ATS APIs and API/RSS-friendly job sources on a schedule, normalizes postings into a single local database, classifies them (category, level, sponsorship signal), and surfaces them through a filterable web UI with new-match alerting.

This is a personal tool. Correctness of the *sponsorship signal* and *dedup* matter more than breadth of sources or UI polish.

### Guiding principles (ordered)
1. **Clean Architecture is the primary principle.** Dependency direction is inward (domain ← application ← adapters/api); domain and application stay IO-free; every external system sits behind a port. When any decision conflicts with another guideline, layer integrity wins.
2. **TDD is the working method for every slice.** Each slice is built red → green → refactor; the refactor step is mandatory, triggered by an explicit smell check after each green (see PLAN.md "TDD loop").
3. Vertical slices, `make verify` gate, fixtures over live calls — in service of 1 and 2.

## 2. Goals / Non-Goals

### Goals (MVP)
- Poll public ATS APIs (Greenhouse, Lever, Ashby) for a curated company list
- Poll API/RSS-friendly boards (HN Who's Hiring, RemoteOK, We Work Remotely, Arbetsförmedlingen JobTech)
- Normalize into one `jobs` table with dedup across sources
- Classify: category (ios / android / flutter / backend / fullstack / frontend / ai-ml), level, remote-vs-onsite
- Sponsorship signal, three tiers: `explicit_yes` / `explicit_no` / `registry_inferred` / `unknown` — surfaced as **badge + default sort key**, never a default exclusion
- Cross-reference official sponsor registries (UK, NL, SE) at the company level
- Filter UI: keyword, country, category, level, posted-since; sponsorship tier as opt-in filter + primary sort control
- Saved searches + digest of new matches (Telegram or WhatsApp via Courier)
- Per-job user status (new / seen / hidden / starred) so the daily list shows only what's actually new
- Resume-fit scoring: upload a resume once, score how well each posting fits it (heuristic tier over **all** jobs, free/deterministic) with an opt-in, budget-capped **LLM deep-match rationale** per job — a soft signal and an optional sort key, never a filter-out (see §11)

### Non-Goals (explicitly deferred)
- ❌ LinkedIn / Indeed / Glassdoor scraping (anti-bot, ToS, redundant with ATS sources)
- ❌ Application tracking (different product; Beacon ends at "here is the link")
- ❌ Salary parsing / compensation analytics
- ❌ Multi-user, auth, hosting for others
- ❌ Cover-letter / CV *generation* (Beacon *scores* an existing resume against postings — §11 — but never writes or rewrites one)
- ❌ Auto-apply

## 3. Target Profile (drives seed data & classifiers)

| Dimension | Values |
|---|---|
| Categories | iOS (primary), Backend, AI/ML (secondary: Android, Flutter, Fullstack) |
| Level | Senior / Staff / Lead (filter out junior-only postings) |
| Primary countries | Singapore, Australia, Japan, Netherlands, US (SF Bay), Canada, Ireland |
| Nice-to-have countries | Sweden, Norway, Denmark, Switzerland |
| Sponsorship | **Soft signal, not a filter-out.** All jobs are shown; sponsorship tier renders as a badge and drives the default sort order (explicit_yes → registry_inferred → unknown → explicit_no). Tier filtering remains available but is opt-in, never default. |

## 4. Country & Visa Reference Data

Stored as seed data in `countries` table; shown in UI as context panel per job. **All figures are as-known Jan 2026 — thresholds and timelines change; each row carries a `verified_at` date and a `source_url` for manual re-verification.** Key constraint: Indonesia does not permit dual citizenship for adults, so "endpoint" below distinguishes PR from citizenship.

| Country | Work visa (entry) | PR path | Citizenship | Registry data source | Notes |
|---|---|---|---|---|---|
| Singapore | Employment Pass, ~S$5.6k/mo + COMPASS points | Discretionary; 5–10yr common, non-guaranteed | ~2yr after PR; renounce required | None public — company-level heuristics only | Springboard market; APAC HQs enable later intra-company transfers |
| Japan | HSP points visa | **70pts→3yr, 80pts→1yr** — fastest PR anywhere | 5yr; renounce; language | None public | Likely 80pts at senior level; PR-as-endpoint strategy |
| Australia | Skills in Demand (~AU$76k floor; AU$141k specialist tier) | 2–3yr via employer 186 or points 189 | 4yr residence | None public (sponsor status inferable from posting text) | |
| Netherlands | HSM kennismigrant, ~€5.3k/mo (30+) | 5yr (+ EU long-term residence) | 5yr; renounce (generally) + integration exams | **IND recognised sponsors list (public)** | Most English-friendly EU market |
| US (SF) | H-1B lottery (~25–35%) / L-1 transfer / O-1 | GC ~1.5–3yr via PERM; **no ID-born backlog** | 5yr after GC | H-1B LCA disclosure data (public, per-company) | Destination, not entry point; best AI/ML pay |
| Canada | Global Talent Stream (2-wk) or Express Entry PR direct | PR can be the entry itself | **3yr** — fastest passport | None needed (open work-permit ecosystem) | EE application can run in background from Indonesia |
| Ireland | Critical Skills Employment Permit (~€38–44k floor) | Stamp 4 after **2yr** | **5yr; dual allowed** → EU passport | None public; big-tech presence is proxy | Best EU-citizenship play; Irish passport ⇒ Sweden access anyway |
| Sweden | Work permit, ~80% median salary (raise proposed) | 4yr | 5yr → **reform to 8yr + tests was in progress** — likely law by 2026 | **None — employer certification scheme discontinued Dec 2023** (replaced by A–D case sorting; verified 2026-07-04) | Direct move ≠ fastest route to permanent Sweden rights. Low employer barrier: any compliant employer may sponsor, so SE `unknown` companies skew sponsor-likely |
| Norway | Skilled worker permit | 3yr | 6–8yr | None public | Small market (Oslo: Cognite, Vipps, Schibsted) |
| Denmark | Pay Limit Scheme ~DKK 514k/yr | 8yr (4 strict) | 9yr | Positive List employers (partial proxy) | Worst Nordic risk/reward; low priority seeds |
| Switzerland | Non-EU quota; employer must justify | 10yr non-EU | 10yr + cantonal | None useful | Effectively Google Zurich-only route; seed that board directly |

**UK sponsor register** is also ingested even though UK isn't a target country — many multinationals appear on it, and presence there is a company-level "sponsors somewhere" signal.

## 5. Data Sources (MVP)

### 5.1 ATS adapters (structured JSON, per-company)
| Source | Endpoint pattern | Notes |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | Largest coverage of target companies |
| Lever | `api.lever.co/v0/postings/{slug}?mode=json` | |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{slug}` | Growing among startups |

Company slugs live in a `companies` seed table loaded from `seeds/companies.csv` with pinned schema: `name,ats_type,ats_slug,country_hq,priority` (priority 1–3; `active` and `registry_flags` are DB columns defaulted at load, not CSV columns). Initial seed: **53 verified companies delivered 2026-07-04** across SG/JP/AU/NL/IE/CA/US/SE. The seed contains eight ATS types; MVP adapters cover greenhouse (24), lever (10), ashby (11) — 45 companies. Rows with unsupported ats_type (smartrecruiters, workable, workday, gem, bendingspoons) load normally but are skipped by `ingest_all`, which filters to supported types — they activate automatically when their adapter ships (candidate future slices, smartrecruiters first at 3 companies). Adding a company = one CSV row, no code.

### 5.2 Board adapters (API/RSS)
| Source | Access | Notes |
|---|---|---|
| HN Who's Hiring | Official HN Firebase API (github.com/HackerNews/API) | `user/whoishiring` → latest "Ask HN: Who is hiring?" submission → top-level `kids` |
| RemoteOK | Public JSON API | Remote roles; tag-rich |
| We Work Remotely | RSS | |
| Arbetsförmedlingen JobTech | Open API (jobtechdev.se) | Sweden-wide coverage, official |

### 5.3 Registry ingesters (company-level, not job-level)
| Registry | Format | Refresh |
|---|---|---|
| UK Home Office licensed sponsors | CSV download | Monthly |
| NL IND recognised sponsors | HTML table / list | Monthly |
| US H-1B LCA disclosures | Quarterly XLSX (DOL) | Quarterly |
| MANUAL — curated sponsor boards | Hand-entered flag; evidence note + date required | Ad hoc |

~~SE Migrationsverket certified employers~~ — **does not exist**: the certification scheme was discontinued Dec 2023 (Sweden has no employer licensing for sponsorship; see §4).

The `MANUAL` flag encodes human-verified sponsorship signals that have no machine-readable register: a company listed on relocate.me / swedishtechjobs / jobbatical (posting there is a self-declaration of sponsorship), a confirmed sponsorship from an application, or direct knowledge. It is **never scraped** — curated boards' lists are their product and off-limits to automation per Non-Goals; the workflow is: browse occasionally, flag companies by hand (one CLI/UI action storing `evidence` + `flagged_at`). MANUAL participates in `registry_inferred` exactly like the machine registries.

Registry match is fuzzy company-name matching (normalized legal suffixes, token overlap) → sets `companies.registry_flags` (bitmask per registry) with a `match_confidence`. MANUAL flags are set directly (confidence 1.0, no fuzzy matching). **Bitmask members: `UK | NL | US | MANUAL`** (no SE — no Swedish register exists; the bit is not reserved).

## 6. Classification

Runs post-ingest, cached by `content_hash` (never reclassify unchanged postings).

1. **Category** — keyword heuristics first (Swift/SwiftUI/UIKit→ios; Kotlin/Compose→android; Dart/Flutter→flutter; PyTorch/LLM/CUDA/ML→ai-ml; etc.), LLM fallback for ambiguous residue via Anthropic API. Multi-label allowed (e.g., ios+ai-ml).
2. **Level** — title tokens (senior/staff/lead/principal/junior/intern) + years-of-experience regex; `unspecified` is an honest value.
3. **Sponsorship tier** —
   - `explicit_yes`: posting text matches sponsor-positive patterns ("visa sponsorship available", "relocation support", "work permit assistance")
   - `explicit_no`: "must have right to work in…", "no sponsorship", "citizens/PR only"
   - `registry_inferred`: text silent, but company has registry_flags set
   - `unknown`: everything else
4. **Location/remote** — country extraction from location strings; `remote_scope` (global / region-locked / onsite).

## 7. Architecture

Consistent with the Sentinel/Moat pattern: FastAPI + SQLite backend, React/TS/Vite frontend, Clean Architecture with vertical slices.

```
beacon/
├── backend/
│   ├── domain/          # Job, Company, Country, SponsorshipTier, SavedSearch,
│   │                    #   ResumeProfile, MatchScore, score_match (pure, §11)
│   ├── application/     # use cases: ingest_source, classify_job, match_saved_searches,
│   │                    #   ingest_resume, score_jobs_for_resume, deep_match_job (§11)
│   ├── adapters/
│   │   ├── sources/     # GreenhouseAdapter, LeverAdapter, AshbyAdapter,
│   │   │                #   HNAdapter, RemoteOKAdapter, WWRAdapter, JobTechAdapter
│   │   ├── registries/  # UKSponsorRegistry, INDRegistry, H1BLCARegistry (+ MANUAL flag path)
│   │   ├── classify/    # HeuristicClassifier, LLMClassifier (Anthropic API)
│   │   ├── resume/      # PlainTextResumeParser, PdfResumeParser (+ LLMMatcher, §11)
│   │   ├── notify/      # TelegramNotifier (Bot API, direct), StdoutNotifier; CourierNotifier deferred
│   │   └── persistence/ # SQLite repos (sqlite3/SQLModel)
│   ├── api/             # FastAPI routers: /jobs, /companies, /countries, /searches, /resumes, /stats
│   └── scheduler/       # APScheduler: source polls (2–6h), registry refresh (monthly)
├── frontend/            # React + TS + Vite
│   ├── JobTable         # virtualized; default sort = sponsor_tier desc, then posted_at desc
│   ├── FilterBar        # keyword, country[], category[], level[], posted_since;
│   │                    #   sponsor_tier[] opt-in filter + sort-by toggle (tier / date)
│   ├── JobDetail        # description, sponsorship evidence, country visa panel
│   ├── CountryPanel     # visa/PR/citizenship reference (from §4 seed data)
│   └── SavedSearches
└── Makefile             # make verify = lint + typecheck + test (both stacks)
```

### Source adapter contract
```python
class JobSource(Protocol):
    source_id: str
    async def fetch(self) -> list[RawPosting]: ...
    def normalize(self, raw: RawPosting) -> NormalizedJob: ...
```
Pipeline per poll: `fetch → normalize → dedupe → classify → upsert → match_saved_searches → notify`.

### Dedup strategy
- Key 1: `(source_id, external_id)` — exact re-poll identity
- Key 2 (cross-source): normalized `(company_name, title, country)` + simhash(description) within Hamming distance threshold
- Duplicates link to a canonical job row; sources listed on detail view

### Core schema (SQLite)
```sql
companies(id, name, ats_type, ats_slug, country_hq, registry_flags, match_confidence, priority, active,
          consecutive_failures, last_success_at, health, quarantine_reason)
jobs(id, canonical_id, company_id, source_id, external_id, title, description,
     url, country, city, remote_scope, categories, level, sponsor_tier,
     sponsor_evidence, content_hash, posted_at, first_seen_at, last_seen_at, closed_at,
     user_status)   -- user_status: 'new' | 'seen' | 'hidden' | 'starred' (default 'new')
countries(code, name, visa_summary, pr_summary, citizenship_summary,
          registry_name, priority_tier, verified_at, source_url)
saved_searches(id, name, filters_json, notify_channel, last_run_at)
seen_matches(search_id, job_canonical_id, notified_at, match_reason)  -- match_reason: which filters fired (tier/country/category), for digest lines
resumes(id, label, source_text, profile_json, resume_hash, active, created_at)  -- §11; single user, small history, one active
job_match_scores(resume_hash, job_canonical_id, overall, skills_score, level_score,
                 sponsor_score, matched_skills, missing_skills, llm_rationale,
                 content_hash, computed_at)  -- §11; PK (resume_hash, job_canonical_id); content_hash gates cache like classification
```

Closed-posting detection: a job absent from N consecutive **successful** polls of its source gets `closed_at` set (kept, greyed out — useful for company-hiring-velocity stats later). Failed polls contribute nothing to absence — a 404'd board must never mass-close its jobs.

### Source health & recovery

Companies change ATS providers, rename board slugs, get acquired, and take boards offline; registry pages move. Beacon treats source failure as a first-class state, never as data:

- Per-company health columns: `consecutive_failures`, `last_success_at`, `health` (`ok` / `degraded` / `quarantined`), `quarantine_reason` (`gone` = 404/410, `unreachable` = 5xx/timeout streak, `schema_drift` = parse-error streak).
- Failure taxonomy drives response: 404/410 → likely moved slug (fast-quarantine after 3); 5xx/timeouts → transient (quarantine after 10, generous backoff meanwhile); normalize/parse errors on a previously-good source → schema drift (the API changed shape — quarantine after 3, this needs a human).
- **Quarantined companies stop being polled** (no log spam, no wasted requests) and their jobs are frozen: excluded from the closed-sweep, badged "source stale since <date>" in UI.
- A weekly probe re-tries quarantined sources once; success auto-restores `ok` and resets counters (handles boards that were temporarily down or DNS blips).
- Recovery from a genuine move is a data edit: update `ats_type`/`ats_slug` on the row (company switched Greenhouse→Ashby, or renamed slug), reset health — no code.
- Health surfaces in the daily Telegram digest ("⚠ 2 sources quarantined: crypto (gone), smartnews (schema_drift)") and a `/companies/health` view — silent decay is the failure mode this whole section exists to prevent.
- Registry staleness: `registries_meta.fetched_at` older than 45 days → warning in digest; registries never quarantine (manual refresh cadence), they just nag.

Sort semantics: `sponsor_tier` maps to a numeric `sort_rank` (explicit_yes=3, registry_inferred=2, unknown=1, explicit_no=0) used by `/jobs` default ordering `ORDER BY sort_rank DESC, posted_at DESC`. `explicit_no` jobs are shown last, never hidden by default.

## 8. Vertical Slices (MVP order)

| # | Slice | Proves |
|---|---|---|
| 1 | Greenhouse adapter → SQLite → `/jobs` API → plain JobTable with keyword+country filter | Ingest pipeline + data model end-to-end |
| 2 | Migrationsverket + IND + UK registry ingest → `registry_inferred` tier + badge in UI | The moat: sponsorship signal |
| 3 | Heuristic category/level classifier + filters | Classification layer |
| 4 | Lever + Ashby adapters | Adapter contract holds for N sources |
| 5 | Dedup (cross-source canonicalization) | Data quality |
| 5.5 | Per-job user status (seen/hidden/starred) | Daily list shows only what's new |
| 6 | Explicit yes/no sponsorship text classifier + evidence display | Tier completeness |
| 7 | HN Who's Hiring + JobTech adapters | Non-ATS source shapes fit the contract |
| 8 | Saved searches + Telegram digest notification | Daily-driver loop closes |
| 9 | LLM fallback classifier w/ content-hash cache | Ambiguity cleanup |
| 10 | CountryPanel (visa/PR data surfaced in job detail) + RemoteOK/WWR | Polish + breadth |
| 11 | Source health & recovery (failure taxonomy, quarantine, weekly probe, health in digest) | Resilience: sources die without lying about data |
| 12 | Resume upload + heuristic fit scoring (all jobs) + opt-in LLM deep-match (per job) | Personalized ranking without blowing the LLM budget |

Each slice: red test → green → refactor → `make verify` → commit.

## 9. Operational Notes

- **Time: all storage/comparison in UTC (aware datetimes); "day boundaries" for `posted_since` filters and the daily digest computed in Asia/Jakarta (UTC+7)** — one `LOCAL_TZ` constant, used only at display/day-boundary edges, never in storage.
- **Access model: localhost / private network (Tailscale) only. No auth in MVP by design; any public exposure requires an auth slice first (cf. Sentinel S9a precedent).**
- Poll intervals: ATS 4h, boards 6h, HN thread daily during first week of month, registries monthly
- Politeness: per-host rate limit (1 req/s), ETag/If-Modified-Since where supported, exponential backoff
- Runs on the home Mac (same box as Anvil) via launchd, or the ROCm Linux box; SQLite file backed up nightly
- LLM cost control: heuristics first, LLM only on residue, hash cache — expected <$2/mo at ~150 companies

## 10. Success Criteria

- One glance each morning answers: "any new senior iOS/backend/AI roles in my target countries since yesterday — and which of them likely sponsor?" (likely sponsors float to the top; nothing is hidden)
- Sponsorship tier is correct on spot-check ≥90% for `explicit_*`, and `registry_inferred` never fires on a company absent from all registries
- Adding a new company: ≤1 minute (one seed row)
- Zero manual scraping maintenance (no HTML parsing of hostile sites in MVP)

## 11. Resume Match — score fit against postings

Upload a resume once; Beacon scores how well each posting fits it, exposes fit as an **opt-in sort key** (never a default filter-out — same rule as sponsorship), and on demand produces an LLM rationale (strengths, gaps, sponsorship-fit verdict) for a single posting. This is *scoring*, not CV generation (§2 Non-Goals).

### Design: two tiers, mirroring the heuristic→LLM classifier (slice 9)

The whole feasibility story is the split between a free tier that runs over every job and a paid tier that never does.

**Tier 0 — Resume profile** (once per resume, cached by `resume_hash = sha256(source_text)`):
- A `ResumeParser` port turns an upload into plain text. Adapters: `PlainTextResumeParser` (paste / `.txt`, zero deps) and `PdfResumeParser` (pdf → text). DOCX is a later drop-in behind the same port. Paste-text is the always-available path so the feature never *requires* a parser dep.
- A **pure domain function** `build_profile(text) -> ResumeProfile` extracts a structured profile **reusing the classifier keyword tables** (`adapters/classify/keywords.py` data, read by the domain): skill/tech token set, inferred `categories` (ios/backend/ai-ml/…), inferred `level`, years-of-experience, and optional country/relocation preferences from a small form. Reusing the same vocabulary the job classifier uses is deliberate — a resume's category/level are computed the *same way* a job's are, so the two are directly comparable and there's one skill vocabulary, not two.

**Tier 1 — Heuristic fit score** (every job, free, deterministic, cached by `(resume_hash, content_hash)`):
- Pure `score_match(profile, job) -> MatchScore` in the domain, no IO, no API cost. Components, each a sub-score:
  - **Skill overlap** — weighted set similarity (Jaccard/cosine) between the resume skill set and the job's extracted skill/keyword set (reuses the `content_hash` normalizer + keyword tables).
  - **Category alignment** — resume categories ∩ job categories.
  - **Level fit** — resume level vs job level (senior resume ↔ junior post penalized; ↔ staff a mild stretch, not a wall).
  - **Sponsorship/country fit** — does the job's country + sponsor tier match the relocation strategy? This is where Beacon's unique data makes its match score better than a generic resume matcher.
- Output: overall `0–100` + the sub-scores + `matched_skills` / `missing_skills`. Deterministic and explainable, so it can rank the **entire** DB and is the default fit signal.

**Tier 2 — LLM deep match** (on demand or bounded top-N; budget-capped; opt-in, off by default like slice 9):
- An `LLMMatcher` behind a `Matcher` port; one JSON-only call per unseen `(resume_hash, content_hash)` pair, reusing the **existing slice-9 `LLMBudget` monthly cap** (no second budget). Produces the rationale: fit summary, concrete strengths, gaps to close, a one-line "worth applying?" verdict, sponsorship-fit note. Stored in `job_match_scores.llm_rationale`.
- **Never scores the whole DB.** It fires only for (a) the job the user opens in the drawer ("Assess fit"), or (b) an explicit "deep-rank my top N" action, N bounded (default 20) and drawn from the Tier-1 ranking. Any LLM failure degrades silently to the heuristic score — the LLM is an upgrader, never a dependency (CLAUDE.md LLM rule).

### Feasibility across many jobs (the crux of the request)

- **Tier 1 is O(jobs) pure CPU, cached** → scoring thousands of postings is milliseconds and $0; safe to compute over a whole result set and sort by it.
- **Tier 2 is O(1) per user action, hard-capped** by the shared monthly budget → cost stays inside the existing <$2/mo envelope. LLM-ranking the whole DB would be O(jobs)×cost and is explicitly out of scope; the two-tier split is exactly what makes multi-job scoring feasible.
- **Compute is bounded to the current `/jobs` page** (score the returned window, not the table) and cached by `(resume_hash, content_hash)`, so pagination never re-scores and a re-poll of an unchanged posting reuses its cached score. A changed posting (new `content_hash`) invalidates just its own score — the same gate classification and sponsorship already use.

### Ports, use cases, placement (Clean Architecture)

- **Domain (pure):** `ResumeProfile`, `MatchScore`, `build_profile`, `score_match`.
- **Ports (`application/ports.py`):** `ResumeParser` (`parse(bytes|str, kind) -> str`), `Matcher` (`deep_match(profile, job) -> MatchRationale`). Reuses existing `JobRepo` and `LLMBudget`; adds `ResumeRepo`, `MatchScoreRepo`.
- **Use cases:** `ingest_resume` (parse → profile → store, set active), `score_jobs_for_resume` (heuristic, cached; the read-side path `/jobs` calls for the current page), `deep_match_job` (LLM, budget-gated, single job).
- **Adapters:** `resume/PlainTextResumeParser`, `resume/PdfResumeParser`, `resume/LLMMatcher` (raw httpx to Anthropic, same thin style as `LLMClassifier`).
- **Zero changes to the ingest/classify use cases.** Matching is a separate read-side concern layered on canonical jobs — it never touches the poll pipeline. New capability = new ports + adapters, existing application/domain untouched (golden rule 1).

### API / UI

- `POST /resumes` (upload or paste), `GET /resumes`, `PUT /resumes/{id}/active`, `DELETE /resumes/{id}`.
- `/jobs?resume=<id>&sort=match` — `match` joins `tier` / `date` as a sort option. **Default sort is unchanged** (sponsor-tier-first stays the default; fit is opt-in). When a resume is active, each returned job carries its Tier-1 `match_score`.
- `POST /jobs/{id}/match?resume=<id>` — triggers the Tier-2 rationale for one job (the drawer's "Assess fit" button).
- UI: resume upload/paste in Settings (or a small Resume view); a fit badge on job rows when a resume is active; a **Fit card** in the job-detail drawer (overall + sub-scores, matched/missing skills, and the optional LLM rationale behind an "Assess fit" button). Fit renders as a soft signal, exactly like the sponsorship badge — visible, sortable, never a default exclusion.

## 12. Deferred / Future

- LinkedIn/Indeed ingestion (only if ever legally clean via official APIs)
- Application tracking (separate tool if ever)
- Salary extraction & comp benchmarking
- Company hiring-velocity analytics from `closed_at` history
- Crowdsource/self-recorded sponsorship confirmations ("applied, they confirmed")
- Sweden reform tracker (auto-diff Migrationsverket pages)
