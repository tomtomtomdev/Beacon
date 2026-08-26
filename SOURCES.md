# SOURCES.md — operational reference for Beacon's shipped data sources

**What this is:** the per-source operating detail for every external dependency Beacon *currently polls* — endpoint, auth, pagination, field-by-field normalization, timestamp quirks, cadence. The view you want when a source breaks at 3am or you're writing the next adapter.

**What this is not:** a decision record. It carries no rationale for why a source was chosen, and it never lists candidates or rejections.

| Question | Canonical home |
|---|---|
| Which sources exist, and why these? | **SPEC.md §5.1–§5.3** |
| What was evaluated and rejected, with probe results? | **SPEC.md §5.4–§5.5** |
| What are we building next, in what order? | **PLAN.md** (slice 14) |
| Why did a decision change? | **PROGRESS.md** Decisions log |
| Exact request/response shapes and edge cases | **the adapter module + its docstring** — the code is authoritative over this file |

Where this file and SPEC.md disagree, **SPEC.md wins** and this file is the bug.

Compiled 2026-08-26 from `backend/beacon/adapters/`, `seeds/companies.csv`, and `backend/beacon/scheduler/schedule.py`. Covers sources shipped through **slice 14**.

---

## 1. Overview

Beacon consumes **four classes of external data**:

| Class | Count | Direction | Port | Cadence |
|---|---|---|---|---|
| ATS adapters (per-company job boards) | 9 | Inbound, read | `JobSource` | every **4h** |
| Board adapters (company-less job feeds) | 7 | Inbound, read | `JobSource` | every **6h** |
| Registry ingesters (company-level sponsor signals) | 5 + 1 manual | Inbound, read (local snapshot files) | `RegistryIngester` | **monthly** (1st, 03:00 local) |
| Outbound services | 2 | Outbound | `Classifier` / `Notifier` | on demand |

**Total: 16 live job sources, 6 registry signals, 2 outbound APIs.**

All inbound HTTP goes through a single shared `PoliteClient` (`adapters/http/polite.py`). Registry snapshots are *files on disk*, manually refreshed — nothing scrapes a government site.

**One source needs a credential.** NAV Norway (§4.7) is bearer-token authenticated; the token lives on the HTTP door keyed by host, never in an adapter, and without it NAV is not wired at all (§2).

---

## 2. The shared HTTP door — `PoliteClient`

*Canonical: `adapters/http/polite.py`; the politeness contract in CLAUDE.md and the failure taxonomy in SPEC §7.*

One instance is shared by every adapter so the per-host budget is global (all 24 Greenhouse boards collectively obey one budget).

| Property | Value |
|---|---|
| Rate limit | **1 request/second per host** |
| Timeout | 15 s |
| Retries | 3, exponential backoff |
| Retry statuses | 429, 500, 502, 503, 504 |
| Conditional GET | ETag / `If-Modified-Since`; 304 → served from in-process cache |
| Methods | `get_json`, `get_text`, `post_json` |
| Auth | `bearer_tokens={host: SecretStr}` — **per host, configured on the door**, so an adapter never holds a credential and a token can only reach the host it belongs to. `__repr__` renders authenticated *hosts*, never tokens |
| Pinned windows | `get_json(modified_since=…)` sends RFC-1123 `If-Modified-Since` as a **filter** (NAV's documented way to choose where a feed starts) and **bypasses the conditional-GET cache** — two windows are two questions sharing one url |
| Failure taxonomy | 404/410 → `FailureKind.GONE`; all other HTTP/transport/timeout → `FailureKind.UNREACHABLE`; raised as `SourceUnavailable(kind)` |

Clock and sleep are injected, so tests never actually wait.

### Failure → quarantine policy (SPEC §7)

| Failure kind | Quarantine after | Rationale |
|---|---|---|
| `GONE` (404/410) | 3 consecutive | Board moved or slug renamed — needs a human fast |
| `SCHEMA_DRIFT` (normalize/parse failure on a previously-good source) | 3 consecutive | The API changed shape — needs a human |
| `UNREACHABLE` (5xx, timeout) | 10 consecutive | Transient; given patience |

A quarantined company is skipped entirely (no fetch, no closed-sweep) and its jobs are frozen. A **weekly probe** (Mon 05:00 local) retries each quarantined source once; success auto-restores. A failed poll **never** runs the closed-sweep — a 404'd board must not mass-close its jobs.

---

## 3. ATS adapters (§5.1) — per-company, structured JSON

*Which boards and why: SPEC §5.1. Below is how each one is actually read.*

Each takes a `(slug, fetcher)` pair. Slug comes from `seeds/companies.csv`. Adding a company = one CSV row, zero code.

### 3.1 Greenhouse — `source_id: greenhouse`
| | |
|---|---|
| Endpoint | `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` |
| Auth | None |
| Shape | `{"jobs": [...]}` — one call, descriptions inline |
| Pagination | None |
| ID field | `id` |
| Title / URL | `title` / `absolute_url` |
| Description | `content` (HTML) |
| Location | `location.name` (free text → `parse_location`) |
| Posted at | `first_published` (ISO-8601, tz-aware) — may be absent |
| Seed rows | **24** (largest coverage) |

### 3.2 Lever — `source_id: lever`
| | |
|---|---|
| Endpoint | `GET https://api.lever.co/v0/postings/{slug}?mode=json` |
| Auth | None |
| Shape | **Bare JSON array**, no envelope |
| Pagination | None |
| ID field | `id` |
| Title / URL | `text` / `hostedUrl` |
| Description | `description` (HTML) |
| Location | `categories.location`; `country` trusted only when it looks like ISO-2 |
| Posted at | `createdAt` (epoch **milliseconds**) |
| Seed rows | **10** |

### 3.3 Ashby — `source_id: ashby`
| | |
|---|---|
| Endpoint | `GET https://api.ashbyhq.com/posting-api/job-board/{slug}` |
| Auth | None |
| Shape | `{"jobs": [...]}` |
| Pagination | None |
| ID field | `id` |
| Title / URL | `title` / `jobUrl` |
| Description | `descriptionHtml` |
| Location | `location` (free text) |
| Posted at | `publishedAt` (ISO-8601 with tz) |
| Seed rows | **11** (growing among startups) |

### 3.4 SmartRecruiters — `source_id: smartrecruiters`
| | |
|---|---|
| Endpoints | List: `GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=N`<br>Detail: `GET .../postings/{id}` |
| Auth | None (public) |
| Shape | `{"content": [...], "totalFound": N}` |
| Pagination | offset/limit, page size **100**, loops until `len(rows) >= totalFound` |
| Two-step | **Yes** — list rows carry no ad text, so one detail GET per posting |
| ID field | `id` |
| Title / URL | `name` / `postingUrl` → fallback `applyUrl` |
| Description | `jobAd.sections` joined in order: `companyDescription`, `jobDescription`, `qualifications`, `additionalInformation` |
| Location | `location.country` (lowercase ISO-2, upcased) + `location.city`; falls back to `fullLocation` string parse |
| Posted at | `releasedDate` (ISO-8601 UTC `Z`) |
| Seed rows | **3** (Grab's ~380 postings spend the whole poll inside the 1 rps budget) |

### 3.5 Workable — `source_id: workable`
| | |
|---|---|
| Endpoint | `GET https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true` |
| Auth | None |
| Shape | `{"jobs": [...]}` — whole board **with descriptions in one call** |
| Pagination | None |
| ID field | `shortcode` |
| Title / URL | `title` / `url` → fallback `shortlink` |
| Description | `description` |
| Location | `locations[0].countryCode` (ISO-2); falls back to flat `city, state, country` |
| Posted at | `published_on` → fallback `created_at` (**bare date** → read as midnight UTC) |
| Note | The v3 accounts endpoint is **not public**; v1 widget is the supported path |
| Seed rows | **1** |

### 3.6 Workday CxS — `source_id: workday`
| | |
|---|---|
| Endpoints | List: `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`<br>Detail: `GET {base}{externalPath}` |
| Auth | None |
| POST body | `{"appliedFacets": {}, "limit": 20, "offset": N, "searchText": ""}` |
| Shape | `{"jobPostings": [...], "total": N}` |
| Pagination | **Caps at 20 rows/page** — larger returns HTTP 400 |
| Two-step | **Yes** — ad text lives on the per-posting GET (which *does* carry ETags, so re-polls revalidate cheaply) |
| Seed slug | `tenant/wdN/site`, e.g. `clio/wd3/ClioCareerSite` — exactly what the board URL already contains |
| ID field | `jobPostingInfo.id` |
| Title / URL | `jobPostingInfo.title` / `externalUrl` |
| Description | `jobPostingInfo.jobDescription` |
| Location | `location` + `country.descriptor` |
| Posted at | `startDate` (bare date → midnight UTC). **`postedOn` ("Posted 4 Days Ago") is never used** — relative prose with no anchor |
| Seed rows | **4** (where enterprise Java backend lives) |

### 3.7 Teamtailor — `source_id: teamtailor`
| | |
|---|---|
| Endpoint | `GET https://{host}/jobs.json` (JSON Feed) |
| Auth | None |
| Slug form | Career domain (`careers.voi.com`) **or** bare tenant (`tibber` → `tibber.teamtailor.com`); a dot means it's already a host |
| Shape | `{"items": [...]}` — full ad HTML included |
| Pagination | None |
| ID field | `id` |
| Title / URL | `title` / `url` |
| Description | `content_html` |
| Location | Embedded schema.org `_jobposting.jobLocation[0].address` → `addressCountry` is already **ISO-2** |
| Posted at | `date_published` → fallback `_jobposting.datePosted` |
| Seed rows | **3** (dominant Nordic ATS, SE) |

### 3.8 Recruitee — `source_id: recruitee`
| | |
|---|---|
| Endpoint | `GET https://{slug}.recruitee.com/api/offers/` |
| Auth | None (public) |
| Shape | `{"offers": [...]}` — whole board **with ad text in one call** |
| Pagination | None |
| ID field | `id` |
| Title / URL | `title` / `careers_url` → fallback `careers_apply_url` |
| Description | `description` **+** `requirements` joined — Recruitee splits one ad across both halves and the requirements half is where the stack and any sponsorship sentence live |
| Location | `country_code` (ISO-2, authoritative) + `city`; falls back to parsing the flat `location` string |
| Posted at | `published_at` → fallback `created_at`, format **`"2026-06-02 10:10:41 UTC"`** (space instead of `T`, literal zone name — `fromisoformat` rejects it, so it is parsed explicitly; unparseable stays null) |
| Empty board | `{"offers": []}` is a *successful* poll |
| Seed rows | **2** (bunq, Channable — NL-origin ATS, the Benelux widener) |

### 3.9 Rippling ATS — `source_id: rippling`
| | |
|---|---|
| Endpoints | List: `GET https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs`<br>Detail: `GET .../jobs/{uuid}` |
| Auth | None |
| Shape | List is a bare **array** of `{uuid, name, department, url, workLocation}` |
| Pagination | None — the whole board in one call |
| Two-step | **Yes** — list rows carry no ad text |
| Repeated rows | The list repeats a posting **once per work location** (744 rows → 376 uuids on Rippling's own board), so the uuid is the identity and dedup happens *before* any detail call is spent |
| Detail failure | Logged (`rippling_detail_skipped`) and skipped, never fatal — the list is a snapshot and a posting can close between the two calls |
| ID field | `uuid` |
| Title / URL | `name` / `url` |
| Description | `description.company` + `description.role` (both halves of the ad) |
| Location | `workLocations[0]` parsed as a string ("Toronto, Canada", "Seattle, WA") |
| Posted at | `createdOn` — ISO-8601 with a **real offset** (`…-07:00`), converted to UTC, never truncated |
| Seed rows | **1** (Rippling; its board carries Dublin / Toronto / Sydney postings) |

### 3.8 Seed coverage summary

`seeds/companies.csv` — schema `name,ats_type,ats_slug,country_hq,priority`, **61 rows** (2026-08-26), countries SG/JP/AU/NL/IE/CA/US/SE/NO.

| ats_type | Rows | Adapter |
|---|---|---|
| greenhouse | 24 | ✅ |
| ashby | 11 | ✅ |
| lever | 10 | ✅ |
| workday | 4 | ✅ |
| teamtailor | 3 | ✅ |
| smartrecruiters | 3 | ✅ |
| workable | 1 | ✅ |
| recruitee | 2 | ✅ |
| rippling | 1 | ✅ |
| gem | 1 | ❌ dormant — board is captcha-gated (`CAPTCHA_REQUIRED`), no JSON endpoint |
| bendingspoons | 1 | ❌ dormant — no public feed |

**59 of 61 rows pollable.** Rows with no adapter load normally, are skipped by `ingest_all`, and show as `pending` in the health view. `SUPPORTED_ATS` is derived from the factory table (`adapters/sources/factory.py`), so it can never drift from reality.

---

## 4. Board adapters (§5.2) — company-less, employer parsed from the posting

These are not tied to a seed company; each yields jobs across many employers, so `NormalizedJob.company_name` is populated from the posting itself.

### 4.1 Hacker News "Who is Hiring?" — `source_id: hn`
| | |
|---|---|
| API | Official Firebase API (github.com/HackerNews/API) — **not Algolia** (decided 2026-07-04) |
| Walk | `GET /v0/user/whoishiring.json` → scan newest **30** submissions → first whose title contains "who is hiring" → its top-level `kids` |
| Item fetch | `GET /v0/item/{id}.json`, bounded concurrency **10** |
| Caching | Per-thread `_seen_kids` set — a re-poll fetches only unseen kids; a new month resets the cache |
| Retry semantics | A kid the API answered for (even `null`) is cached; a kid whose fetch **raised** stays uncached and retries next poll |
| Dropped | `deleted`/`dead` items, replies with no parseable header |
| ID / URL | `id` / `https://news.ycombinator.com/item?id={id}` |
| Title | Parsed `role`, falling back to `company` |
| Parsing | `domain/hn.py::parse_hn_posting` — pure domain, header-line parse |
| Posted at | `time` (epoch seconds) |
| Log line | `hn_poll thread= kids= unseen= postings=` |

### 4.2 RemoteOK — `source_id: remoteok`
| | |
|---|---|
| Endpoint | `GET https://remoteok.com/api` |
| Shape | JSON array whose **first element is a legal-notice object with no `id`** — dropped |
| ID / Title / URL | `id` / `position` / `url` |
| Description | `description` |
| Location | `location` free text ("Worldwide", "Europe") — regions stay country-less, never fabricated |
| Posted at | `date` (ISO-8601) |
| Company | `company` |

### 4.3 We Work Remotely — `source_id: weworkremotely`
| | |
|---|---|
| Endpoint | `GET https://weworkremotely.com/remote-jobs.rss` (**RSS/XML**, `get_text`) |
| Parsing | `xml.etree.ElementTree`, each `<item>` reduced to a flat dict |
| ID | `guid`, falling back to `link` |
| Title | `"Company: Role"` → split on `": "`; a title with no colon attributes no employer and is skipped by the company-less ingest |
| Location | `region` |
| Posted at | `pubDate` (RFC-2822 via `email.utils.parsedate_to_datetime`) |
| Note | Trusted feed per SPEC §5.2 — not hostile HTML scraping |

### 4.4 Arbetsförmedlingen JobTech — `source_id: jobtech`
| | |
|---|---|
| Endpoint | `GET https://jobsearch.api.jobtechdev.se/search?limit=100` |
| Auth | None (open API, jobtechdev.se) |
| Shape | `{"hits": [...]}` |
| ID / Title | `id` / `headline` |
| URL | `webpage_url` → fallback `https://arbetsformedlingen.se/platsbanken/annonser/{id}` |
| Description | `description.text_formatted` → fallback `description.text` |
| Country | `workplace_address.country_code` is JobTech's **numeric taxonomy, not ISO-2**. Absent → `SE` (the board's default); `199` → `SE`; **any other code → country unknown, never SE** |
| Posted at | `publication_date` — emitted with **no offset**; interpreted in `Europe/Stockholm`, converted to UTC |
| Company | `employer.name` |
| Coverage | Sweden-wide, official |

### 4.5 Himalayas — `source_id: himalayas`
| | |
|---|---|
| Endpoint | `GET https://himalayas.app/jobs/api/search?q={query}&limit=20&page=N` |
| Why search, not firehose | ~100k live remote postings — polled **per role family**, never as a firehose |
| Role queries (data, not logic) | `"ios engineer"`, `"java backend engineer"`, `"machine learning engineer"` |
| Page size / cap | 20 (endpoint max) × **3 pages** = 60 newest matches per query per poll; the rest arrive on later polls |
| Dedup | By `guid` across queries |
| Partial-sweep honesty | Hitting the page cap logs `himalayas_page_cap query= fetched= total=` — a partial sweep never reads as complete |
| ID | `guid` |
| Title / URL | `title` / `applicationLink` → fallback `guid` |
| Location | `locationRestrictions[]`; **an empty list means work-from-anywhere → no country reported** |
| Posted at | `pubDate` (unix epoch seconds) |
| Company | `companyName` |
| Attribution | Postings keep their himalayas.app URL, as the board's terms ask |

### 4.6 MyCareersFuture (SG) — `source_id: mycareersfuture`
| | |
|---|---|
| Endpoints | Search: `POST https://api.mycareersfuture.gov.sg/v2/search?limit=20&page=N`<br>Detail: `GET https://api.mycareersfuture.gov.sg/v2/jobs/{uuid}` |
| Auth | None (official government API) |
| POST body | `{"search": query, "sessionId": "", "categories": []}` |
| Shape | `{"results": [...], "total": N}` |
| Two-step | **Yes** — search rows carry no ad text |
| Role queries | `"iOS engineer"`, `"Java backend engineer"`, `"machine learning engineer"` |
| Page size / cap | 20 × **3 pages** per query; cap logs `mycareersfuture_page_cap` |
| ID | `uuid` (deduped across queries) |
| Title / URL | `title` / `metadata.jobDetailsUrl` |
| Location | `address.isOverseas` false → `SG` / `Singapore`; true → only the named `overseasCountry` is trusted (the street address is the *employer's*, not the role's) |
| Posted at | `metadata.newPostingDate` → fallback `originalPostingDate` (bare date → midnight UTC) |
| Company | `hiringCompany.name` preferred over `postedCompany.name` — on an agency posting the hiring company is the real employer |
| **Unique value** | The **only source shipping structured salary bands** — the figure the Employment Pass threshold is measured against |

### 4.7 NAV Norway — `source_id: nav`
| | |
|---|---|
| Endpoints | Feed: `GET https://pam-stilling-feed.nav.no/api/v1/feed` (then `next_url`)<br>Detail: `GET /api/v1/feedentry/{uuid}` |
| Auth | **Bearer token, required** — `BEACON_NAV_API_TOKEN`. Configured on the HTTP door keyed by host; the adapter never holds it. No token → the source is not wired (401 is not a source) |
| Token supply | NAV publishes a rotating public experimentation token at `/api/publicToken`; a private token is issued to registered consumers by email |
| Feed shape | Continuous **historical** feed running from ~2019 — `{version, title, feed_url, next_url, id, next_id, items[]}`, ~1,000 items/page |
| Window | `If-Modified-Since` (RFC-1123) is NAV's documented **filter**, so the poll pins **now − 3 days** via `Fetcher.get_json(modified_since=…)`; pinned requests bypass the conditional-GET cache (two windows are two questions sharing one url) |
| Page cap | **4 pages**, following `next_url`; stops when `next_id` is null (the head of the feed); the cap logs `nav_page_cap` |
| ACTIVE filter | **Mandatory, not an optimisation** — an INACTIVE item is returned with its title and employer *stripped to `"..."`*, so there is nothing left to classify |
| Title pre-filter | Only titles matching the shared vocabulary get a detail call. Measured 2026-08-26: 8 pages / 8,000 items over five days = **4,711 ACTIVE ads, 48 with a tech-shaped title (~1%)** — paying ~4,700 polite calls per poll for those is the firehose rule again |
| Two-step | **Yes** — the ad text lives on the detail call, under **`ad_content`** (the published docs still call it `json`) |
| Closed between calls | A detail with no `ad_content` is logged (`nav_entry_without_content`) and dropped |
| ID | `uuid` |
| Title / URL | `ad_content.title` / `ad_content.link` → fallback `applicationUrl` |
| Description | `ad_content.description` |
| Location | `workLocations[0]` — `country` is the register's own **Norwegian** name (`"NORGE"` → NO, via the country table). An unobserved foreign Norwegian name yields **no country**, never a guess |
| Posted at | `ad_content.published` — ISO-8601 with Norway's offset (`+02:00`), converted to UTC |
| Company | `ad_content.employer.name` |

---

## 5. Registry ingesters (§5.3) — company-level sponsorship signals

Not job feeds. These set `companies.registry_flags` (a bitmask) via fuzzy company-name matching with a `match_confidence`.

**Bitmask members: `UK | NL | US | MANUAL | IE | CA`.** Values are **frozen and only appended** — `registry_flags` is a stored integer, so renumbering a bit would silently re-label every company already matched (this is why MANUAL keeps bit 8 and IE/CA took 16/32). There is deliberately **no SE bit** — Sweden's Migrationsverket certified-employer scheme was **discontinued Dec 2023**; no Swedish employer register exists.

All file-based registries read through one shared contract (`_csvfile.iter_rows`: `newline=""` for the csv module, `utf-8-sig` to drop a BOM). The CA export prints a title banner *above* its header row, so it reads through `iter_rows_below_banner(header_column="Employer")` instead — a file whose header is never found **raises**, rather than yielding rows keyed on junk. Snapshots are **downloaded by hand** and dropped in `data/registries/` — a missing snapshot is *skipped, not fatal*.

| Registry | Enum | Default path (env override) | Source format | Refresh |
|---|---|---|---|---|
| UK Home Office licensed sponsors | `Registry.UK` | `data/registries/uk_sponsors.csv` (`BEACON_UK_REGISTRY_PATH`) | CSV download | Monthly |
| NL IND recognised sponsors | `Registry.NL` | `data/registries/ind_sponsors.csv` (`BEACON_IND_REGISTRY_PATH`) | HTML table / list → CSV | Monthly |
| US H-1B LCA disclosures (DOL) | `Registry.US` | `data/registries/h1b_lca.csv` (`BEACON_H1B_REGISTRY_PATH`) | Quarterly XLSX → CSV | Quarterly |
| IE DETE employment permits | `Registry.IE` | `data/registries/ie_permits.csv` (`BEACON_IE_REGISTRY_PATH`) | Monthly XLSX → CSV | Monthly |
| CA TFWP positive LMIA employers | `Registry.CA` | `data/registries/ca_lmia.csv` (`BEACON_CA_REGISTRY_PATH`) | Quarterly XLSX → CSV | Quarterly |
| MANUAL — curated sponsor boards | `Registry.MANUAL` | n/a (CLI) | Hand-entered | Ad hoc |

### 5.1 UK sponsor register
Columns `Organisation Name`, `Route`. Real-register hazards handled: leading/trailing whitespace, **one row per visa route** (deduped by case-folded name), trading-as segments (`split_trading_as` → aliases), **CRLF line endings**, junk county values. `Route` is kept as evidence.

*Ingested even though the UK is not a target country* — many multinationals appear on it, so presence is a company-level "sponsors somewhere" signal.

### 5.2 NL IND recognised sponsors
Columns `Organisation`, `KvK number`. **Every legal entity is kept** — multi-entity companies (Backbase ×3, Adyen ×2) match at company level and are counted once by the matcher, not deduped here. KvK preserved as evidence (`"KvK {n}"`), ready to become an exact-match key if seed rows ever gain one.

### 5.3 US H-1B LCA
Columns `EMPLOYER_NAME`, `CASE_STATUS`, `TRADE_NAME_DBA`.
- Only **`Certified`** and **`Certified - Withdrawn`** count as evidence; Denied/Withdrawn contribute nothing.
- Rows with an empty employer are the sheet's padding (openpyxl's `max_row` lies) and are skipped.
- Filings are **aggregated per employer**, so a 3,000-filing Google reads differently from a 2-filing startup.
- Brand names hide in an embedded `dba X` inside `EMPLOYER_NAME` *and* in the separate `TRADE_NAME_DBA` column — **both become aliases**.
- Reference scale: FY2026 Q2 XLSX = 1.04M rows / ~210k filings / 31,587 employers.

### 5.4 IE DETE employment permits
Columns `Employer Name`, `Permits Issued {Mon}` ×N, `Permits Issued Grand Total`.
- Ireland publishes the permits it actually **issued**, not a licensed-sponsor list — an entry is *stronger* evidence than eligibility.
- One row per employer with the monthly columns already aggregated by the publisher, so the grand total goes straight into the evidence line ("57 employment permits issued").
- Hazards: leading whitespace in published names, `T/A <brand>` trading-as segments (Irish registers use the abbreviation, not the word), and the empty trailing row an Excel export leaves behind.
- Reference scale: the 2026 file = 332 KB / **6,360 employers**.
- **Irish legal forms are normalizer data:** `Unlimited Company` (UC) and `Designated Activity Company` (DAC) joined `SUFFIX_TOKENS` in slice 14 — without them an Irish subsidiary keeps its legal form as a distinctive token and never matches its own brand ("Stripe Technology Company Limited"). `public` is deliberately excluded.

### 5.5 CA TFWP positive LMIA employers
Columns `Province/Territory`, `Program Stream`, `Employer`, `Address`, `Occupation` (NOC 2021), `Incorporate Status`, `Approved LMIAs`, `Approved Positions`.
- Structural twin of the H-1B ingester: **one row per (stream, occupation)**, so filings are aggregated per employer and a ten-LMIA sponsor never reads like a one-filing shop.
- Positions are counted **separately** from LMIAs — one LMIA can approve many positions (a fruit grower's 13 LMIAs cover 751 harvest positions). Evidence: "10 positive LMIAs (10 positions)".
- The export opens with a **one-cell title banner** above the header (hence `iter_rows_below_banner`) and closes with a `Notes:` block whose lines carry no employer — both contribute nothing.
- **Publisher caveat, not hidden:** the list *excludes all personal names and business names built on personal names*, so it is incomplete by construction — **absence from it is not evidence of non-sponsorship**.
- Reference scale: 2026Q1 XLSX = 8,797 rows / **7,884 employers**.

### 5.6 MANUAL
Encodes human-verified sponsorship signals with no machine-readable register: a company listed on relocate.me / swedishtechjobs / jobbatical (posting there is a self-declaration), a confirmed sponsorship from an application, or direct knowledge.

**Never scraped** — curated boards' lists are their product and off-limits per Non-Goals. Workflow:

```
python -m beacon.refresh --flag "Lovable" --evidence "listed on relocate.me"
```

Sets the flag directly at confidence **1.0**, no fuzzy matching. Participates in `registry_inferred` exactly like the machine registries.

### 5.7 Staleness
`registries_meta` records each snapshot's ingest time. A snapshot older than **45 days** (`REGISTRY_STALE_AFTER_DAYS`) raises a `RegistryStale` alert in the Telegram digest. Registries **never quarantine** — they just nag.

---

## 6. Outbound APIs

### 6.1 Anthropic Messages API — LLM classifier fallback
| | |
|---|---|
| Endpoint | `POST https://api.anthropic.com/v1/messages` |
| API version header | `2023-06-01` |
| Model | `claude-haiku-4-5-20251001` (`llm_model`) |
| Auth | `BEACON_ANTHROPIC_API_KEY` (`SecretStr` — kept out of reprs/logs). Absent → **heuristic-only, no LLM wired** |
| Max tokens | 256 |
| Input cap | First **2000 chars** of the description — enough to name an ambiguous role without paying for a whole JD |
| Prompt | JSON-only, no prose/fences: `{"categories": [...], "level": "..."}` |
| Transport | **Sync** httpx client (the `Classifier` port is synchronous; this is a paying-customer API, so it does **not** go through `PoliteClient`) |
| Gate | Called only for the ambiguous residue the heuristic leaves (empty category set), once per unseen `content_hash` |
| Budget | Hard cap **500 calls per local month** (`llm_monthly_budget`), enforced by `TieredClassifier` |
| Failure policy | Any failure → **fall back to the heuristic result**. The LLM is an upgrader, never a dependency |

The adapter is deliberately dumb — it fetches, parses, and raises on any reply it cannot read. The heuristic-first gate, the budget, and the fallback policy all live in `TieredClassifier`.

### 6.2 Telegram Bot API — digest delivery
| | |
|---|---|
| Endpoint | `POST https://api.telegram.org/bot{token}/sendMessage` |
| Body | `{"chat_id": ..., "text": ...}` |
| Auth | `BEACON_TELEGRAM_BOT_TOKEN` + `BEACON_TELEGRAM_CHAT_ID`. Absent → `StdoutNotifier` |
| Format | **Plain text, no `parse_mode`** — job titles with markdown-ish characters can never break rendering |
| Chunking | Digests split into ≤**4096**-char messages, one POST each |
| Note | Direct Bot API; Courier deferred behind the `Notifier` port |

---

## 7. Scheduling (`scheduler/schedule.py`)

*Canonical: `scheduler/schedule.py` — the constants below are read from it, not decided here. Cadence rationale is SPEC §9.*

APScheduler, cron boundaries keyed in `LOCAL_TZ` = **Asia/Jakarta** so "monthly"/"nightly" fall on the local calendar.

| Job | Trigger | Notes |
|---|---|---|
| `poll_ats` | Interval, **4 hours** | The 7 per-company ATS adapters |
| `poll_boards` | Interval, **6 hours** | The 6 company-less board adapters. HN's daily-first-week cadence is folded in here — its per-thread unseen-kids cache makes frequent re-polls cheap |
| `refresh_registries` | Cron, **day 1 @ 03:00** | Match seeds against available snapshots; write `registries_meta` |
| `nightly_backup` | Cron, **04:00** | Timestamped SQLite copy to `backups/` |
| `probe_quarantined` | Cron, **Mon @ 05:00** | One retry per quarantined source; success restores, failure does **not** inflate counters |

---

## 8. The port contract

*Canonical: `application/ports.py`. SPEC §7 states the architectural rule this enforces.*

```python
class JobSource(Protocol):
    source_id: str
    async def fetch(self) -> list[RawPosting]: ...
    def normalize(self, raw: RawPosting) -> NormalizedJob: ...

class RegistryIngester(Protocol):
    registry: Registry
    def fetch(self) -> list[RegistryCompany]: ...
```

`NormalizedJob` fields every adapter must produce: `source_id`, `external_id`, `title`, `url`, `description`, `location_raw`, `country`, `city`, `posted_at`, `content_hash`, and — for company-less sources — `company_name`.

**Adding a source = new adapter + fixture tests + one factory entry.** Zero changes to `application/` or `domain/`. If a new source requires touching a use case, the abstraction is wrong.

Slice 13 proved the port survives two shapes it was not designed around:
- **POST-only search** (Workday, MyCareersFuture) → added `Fetcher.post_json`, no port change.
- **Two-step list → detail** (SmartRecruiters, Workday, MyCareersFuture) → absorbed entirely inside `fetch()`; `normalize()` simply reads a detail payload.

---

## 9. Cross-cutting data rules

*Canonical: CLAUDE.md (backend conventions, data-correctness notes) and SPEC §7. Restated here because they constrain every adapter below.*

- **Dedup key 1**: `(source_id, external_id)` — exact re-poll identity.
- **Dedup key 2** (cross-source): normalized `(company_name, title, country)` + simhash(description) within a Hamming distance threshold. Duplicates link to a canonical job row; sources are listed on the detail view.
- **`content_hash`** = sha256 of the normalized description. Gates re-classification and LLM spend. Changing the normalization requires a backfill plan.
- **`posted_at` may be null** and is **never fabricated**. Explicitly refused: Workday's `postedOn` ("Posted 4 Days Ago") — relative prose with no anchor.
- **Bare dates** (Workable `published_on`, Workday `startDate`, MyCareersFuture posting dates) are read as **midnight UTC**.
- **Offset-less timestamps** get the source's real local zone: JobTech → `Europe/Stockholm` → UTC.
- **Country codes are only trusted when they look like ISO-2** (Lever, SmartRecruiters, Workable all guard this); otherwise the shared string parser runs. JobTech's numeric taxonomy is mapped explicitly, never guessed.
- **The pipeline never dies on one bad item**: per-posting try/except with a structured log line, then continue.
- **Every poll logs** `source= company= fetched= upserted= errors=`.
- **Fixtures over live calls**: every adapter is tested against recorded JSON/CSV/XML in `backend/tests/fixtures/{source}/` — 15 fixture directories, one per source plus `registries/` and `anthropic/`. Live network calls appear only in manual acceptance scripts.

---

## 10. Explicitly excluded sources

*Exclusions predating slice 13 only. Sources probed and rejected in the 2026-08-23 and 2026-08-26 surveys are in **SPEC §5.5**, with their probe results.*

| Source | Reason |
|---|---|
| LinkedIn / Indeed / Glassdoor | Anti-bot, ToS, and redundant with the ATS adapters |
| relocate.me / swedishtechjobs / jobbatical | Curated lists are the product — off-limits to automation; enter as `MANUAL` flags by hand |
| SE Migrationsverket certified employers | **Does not exist** — scheme discontinued Dec 2023 |
| Gem job boards | Captcha-gated (`CAPTCHA_REQUIRED`), no JSON endpoint |
| Bending Spoons careers | No public feed |
| Workable v3 accounts endpoint | Not public — v1 widget is the supported path |
| HN via Algolia | Rejected 2026-07-04 in favour of the official Firebase API |

---

## 11. Not in this file

Three things deliberately live elsewhere, so there is exactly one copy of each:

- **Candidate and rejected sources** (Arbeitnow, Reed, Adzuna; The Muse and Breezy, both built-or-listed then dropped) — **SPEC.md §5.4–§5.5**, with the live probe result for each and the §4 target-set decision that gates the UK/Mediterranean ones.
- **Rejected sources with their probe evidence** (Adzuna's quota arithmetic, EURES' input-only API, TokyoDev's Cloudflare wall, NZ's unpublished AEWV list) — **SPEC.md §5.5**. §10 above covers only the exclusions that predate slice 13.
- **The two ranking defects** found by the 2026-08-26 resume-match spot check (`swift` matching SWIFT the payment network; one-skill jobs scoring 100% coverage) — **PLAN.md slice 14a**, with the failing-test names, and **PROGRESS.md** `2026-08-26 (14-survey)` for the evidence.

When slice 14 ships, its sources move **into** §3–§5 of this file and out of SPEC §5.4 — that migration is what marks a candidate as built.
