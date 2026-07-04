# DESIGN.md — Beacon UI Handoff

> Canonical UI spec (from Claude Design, "Nordic Slate & Teal" theme, 2026-07-04).
> Product source of truth remains the top-level SPEC.md / PLAN.md / PROGRESS.md — where this
> doc and SPEC.md ever disagree, SPEC.md wins. (The SPEC.md copy that shipped inside the design
> zip was verified byte-identical to the canonical one on 2026-07-04; the top-level file remains
> the authoritative copy and receives all future edits.) The prototype
> `.dc.html` files and `support.js` are references only, not shipping code.

---

# Handoff: Beacon — personal tech-job scanner with visa-sponsorship awareness

## Overview
Beacon is a single-user, self-hosted web app that polls ATS/job-board APIs, normalizes postings into one database, classifies them (category, level, sponsorship tier), and surfaces them in a filterable UI with a per-job "what's new" workflow. This bundle is the **front-end design** for that UI. The authoritative product spec is `SPEC.md` (copied into this folder) — read it for data model, sources, and back-end architecture. This README documents the UI to be built.

## About the Design Files
The files in this bundle are **design references created in HTML** — a working prototype showing the intended look and behavior. They are **not** production code to copy verbatim. The `.dc.html` files are authored in a bespoke "Design Component" runtime (`support.js`) that is a prototyping tool, **not** a shipping dependency.

Your task: **recreate this UI in the target codebase's environment.** The spec calls for **React + TypeScript + Vite** (see `SPEC.md` §7) — build it there using idiomatic React (function components + hooks), the project's own component/styling conventions, and a real data layer hitting the FastAPI endpoints (`/jobs`, `/companies`, `/countries`, `/searches`, `/stats`). Where this doc gives exact hex/px values, match them; where it describes behavior, wire it to real state/data instead of the prototype's in-memory arrays.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, and interactions. Recreate the UI pixel-close using the codebase's libraries. Palette is the **"Nordic Slate & Teal"** theme (chosen by the user from 5 explored options — the alternates live in `Beacon Palettes.dc.html` for reference only).

---

## Global Layout
Full-viewport two-pane app: fixed **sidebar** (236px) + scrolling **main** (flex:1). A **job-detail drawer** (560px, max 92vw) slides in from the right over a dim overlay. Font: **Geist** (UI) + **Geist Mono** (metadata/slugs/timestamps). Body bg `#eef1f3`, ink `#16202a`.

### Sidebar (236px, bg `#f6f8f9`, right border `#e0e6ea`, padding 22×16)
- **Brand:** beacon-signal SVG logo (teal `#0e8a7d`), "Beacon" (17px/700/-0.02em) + "job scanner" (10.5px mono, muted `#93a0aa`).
- **Nav** (4 items, each a full-width button, 9×11 padding, radius 9px, gap 11px icon↔label): Jobs, Saved searches, Companies, Countries. Active item: bg `#d7efec`, text `#0a6c62`, weight 600. Idle: text `#4c5964`, weight 500. Jobs and Saved-searches carry a right-aligned count badge (mono, 11px, radius 999px; active badge bg `#a9dcd5`/`#0a6c62`, idle `#e6ecee`/`#93a0aa`). **Jobs badge shows the count of `new`-status jobs**, not total.
- **Source-health footer** (margin-top:auto, top border `#e6ecee`): uppercase label "Source health" (10.5px/600/0.06em, `#93a0aa`), then three legend rows with 7px dots — OK `#25a56a`, degraded `#d99a2b`, quarantined `#d26f68` — and a mono "last poll · 07:04" line (`#a3aeb6`).

---

## Screens / Views

The main pane renders one of four views (sidebar nav switches `view` state): **Jobs**, **Saved searches**, **Companies**, **Countries**. The **Job-detail drawer** overlays any view.

### 1. Jobs (default)
The daily-driver list.

**Header** (padding 26×34 top): H1 "Jobs" (24px/700/-0.02em); subtitle (13.5px, `#5d6b76`) = a result label like `New · 9 postings · sorted by sponsor tier`. Right side: the **4-dot tier legend** — Sponsors `#25a56a`, Registry `#3f83c8`, Unknown `#a6b0ba`, No `#d26f68` (8px dots, 12.5px labels).

**Filter bar** (sticky, top:0, z-index 5, gradient fade over page bg). Row 1:
- **Status segmented control** (segment track bg `#e2e8eb`, radius 9px, 3px pad): `New · Starred · All · Hidden`, each with a live count in mono. Active segment: white bg, `#16202a` text, subtle shadow; count `#0a6c62`. Idle: text `#6b7784`, count `#97a3ac`. This is the primary "what am I looking at" switch — default **New**.
- **Search input** (flex, min 240px): white, border `#dbe2e6`, radius 10px, 11px pad + 40px left for the search SVG (stroke `#93a0aa`). Placeholder "Search title, company, keyword…".
- **Sort segmented control**: "Sort" label + `Sponsor tier` / `Date` toggle. Default **Sponsor tier**.
- **Country** dropdown button + **Sponsor tier** dropdown button (pill style; active/filled when a selection exists, label shows count e.g. "Country · 2").

Row 2 (chips, 12px top): "CATEGORY" label + 7 category pills (iOS, Backend, AI/ML, Android, Flutter, Fullstack, Frontend) · divider · "LEVEL" label + 3 pills (Senior, Staff, Lead) · divider · posted-window segmented control (All / 24h / 7d / 30d, default All).
- **Pill (idle):** white, border `#dbe2e6`, text `#4c5964`, radius 999px, 6×13 pad. **Pill (active):** bg `#d7efec`, border `#a9dcd5`, text `#0a6c62`.
- Dividers: 1px × 20px, `#dbe2e6`.

**Country dropdown menu** (absolute, white, border `#dbe2e6`, radius 12px, shadow `0 12px 32px rgba(20,32,42,0.12)`, 230px): checkbox row per country (checkbox 17px, radius 5px; checked = teal `#0e8a7d` fill + white check). Each row shows a tier badge `P` (primary, `#0a6c62` on `#d7efec`) or `☆` (nice-to-have, `#a3aeb6` on `#e9eef0`). Countries: Singapore, Australia, Japan, Netherlands, United States, Canada, Ireland, Sweden, Norway, Denmark, Switzerland.

**Sponsor-tier dropdown menu** (210px): note line "Opt-in filter. Off by default — nothing is hidden." + 4 checkbox rows (each with its tier dot): Sponsors, Registry, Unknown, No sponsor. **This filter is opt-in and never on by default** — a core product rule (`SPEC.md` §3).

**Jobs table** (white card, border `#e0e6ea`, radius 14px). Grid columns: `minmax(0,2.4fr) 1.15fr 1.35fr 0.72fr 1fr 64px`, gap 16px. Header row (bg `#f4f7f8`, border-bottom `#e9eef0`, 12×24 pad): uppercase labels (10.5px/600/0.06em, `#97a3ac`) — Role, Location, Category, Level, "Sponsor · Posted" (right-aligned) + empty actions column.

Each **job row** (16×24 pad, border-bottom `#eef2f4`, cursor pointer, hover bg `#f4f7f8`):
- **Role cell:** a leading 7px dot (teal `#0e8a7d` when status is `new`, else transparent to preserve alignment), then title (15px/600/-0.01em, ellipsized) and a subline: company (12.5px/500, `#5d6b76`) + `ats · slug` in mono (11px, `#a3aeb6`).
- **Location:** city (13px) + country (11.5px, `#93a0aa`).
- **Category:** wrap of tag chips (11.5px, bg `#e9eef0`, text `#4c5964`, radius 6px).
- **Level:** mono, uppercase (12px, `#5d6b76`).
- **Sponsor · Posted:** right-aligned column = tier chip (pill: dot + label; colors per tier table below) stacked over "Xd ago" (11.5px, `#93a0aa`).
- **Actions (64px):** star toggle + hide/restore toggle (27px icon buttons, transparent, hover bg `#e9eef0`). Star = outline (stroke `#a6b0ba`) or filled teal when starred. Hide = eye-off icon; in Hidden view it becomes a restore (undo) icon.

**Empty state** (70px pad, centered): title + subtitle vary by status view — e.g. New → "You're all caught up" / "No new postings under these filters. Switch to All to browse everything."; Starred → "No starred postings yet"; Hidden → "Nothing hidden".

### 2. Job-detail drawer (right slide-over, 560px)
Opens on row click. bg `#f6f8f9`, left border `#e0e6ea`, shadow `-20px 0 50px rgba(20,32,42,0.1)`; overlay `rgba(16,24,32,0.22)`. **Opening a `new` job marks it `seen`.** Slide-in animation `bk-slide` 0.22s cubic-bezier(.2,.7,.2,1).

- **Header:** company + mono slug; title (21px/700/-0.02em). Top-right action group (34px buttons, white, border `#dbe2e6`): Star, Hide (or Restore if hidden), Close.
- **Chip row:** tier chip + a **status pill** (New/Seen/★ Starred/Hidden — colors in tokens) + city/remote/level chips (bg `#e9eef0`) + "posted Xd ago".
- **Sponsorship evidence card** (radius 12px, border + header tinted to the tier): header icon + title ("Sponsorship offered" / "No sponsorship" / "Registry-inferred signal" / "No signal detected"). Body:
  - `explicit_yes`/`explicit_no` → italic quoted evidence string, left border in tier accent.
  - `registry_inferred` → "Posting text is silent…, but the company appears on:" + list of registries (blue dot rows) + "Match confidence 0.94 · company-level signal, not a per-role guarantee." Registry bitmask members are **`UK | NL | US | MANUAL`** (no SE — no Swedish register exists). The prototype's sample data demonstrates UK/NL only; **implement MANUAL too** (curated-board / hand-flagged sponsor signal at confidence 1.0 — see `SPEC.md` §5.3) — render it in this same list when a job's company carries the MANUAL flag.
  - `unknown` → "No sponsorship language detected and no registry match. Shown, ranked below explicit and registry signals — never excluded."
- **Description:** uppercase label + paragraphs (13.5px, line-height 1.6).
- **Country visa panel** (teal-tinted: bg `#e6f4f1`, border `#c9e6e1`): globe icon + "<Country> — relocation reference"; three labeled blocks (Work visa / PR path / Citizenship; labels `#3d8a7e`, values `#1f3b40`) + mono "verified <date>".
- **Sources:** uppercase label (+ "· deduped across N" when multi-source), mono source rows, then a teal CTA button "Open original posting →" (bg `#0e8a7d`, hover `#0b7268`, white, radius 10px).

### 3. Companies (source health)
H1 "Companies" + subtitle on source-health-as-first-class-state, plus a mono seed line: `seed 53 · greenhouse 24 · lever 10 · ashby 11 · 8 awaiting adapters (smartrecruiters next)`. All counts computed from the companies table, never hardcoded.
**Summary cards** (white, border `#e0e6ea`, radius 12px, min 120px): 53 seed companies · 45 supported adapters · 42 healthy (`#1b8a5a`) · 1 degraded (`#9a6a12`) · 2 quarantined (`#c0504a`) · 8 adapter pending (`#93a0aa`). (Health-split numbers here are illustrative sample data; seed/supported/pending reflect the real CSV.)
**Table** (grid `minmax(0,2fr) 1.2fr 1fr 1.4fr 1.4fr`): Company · ATS·slug (mono) · HQ · Last success · Health. Health cell = a status badge (dot + label, colors below) + optional mono reason ("gone · 404", "schema drift", "2 failures · 5xx", "adapter pending").

### 4. Countries (visa reference)
H1 "Country & visa reference" + subtitle (as-known dates; PR vs citizenship distinction — Indonesia bars adult dual citizenship).
- **Target-geography panel** (bg `#f4f7f8`, border `#e0e6ea`, radius 16px): header "Target geography" (globe icon) + legend (Primary target `#0e8a7d` / Nice-to-have `#7c8791`). A **world map** drawn on `<canvas>` as a dot-grid (land dots `#cdd6db`), with absolutely-positioned country **pins** (13px dot, teal for primary / slate `#7c8791` for nice-to-have, white ring border, pulsing ring animation `bk-pulse`). Pins and cards cross-highlight on click.
- **Country cards** grid (`repeat(auto-fill, minmax(340px,1fr))`): each card (white, border `#e0e6ea`, radius 14px; selected = teal border + `0 0 0 3px rgba(14,138,125,0.15)` ring) shows name + tier pill (Primary/Nice-to-have), three labeled blocks (Work visa / PR path / Citizenship), and a footer with registry note + mono "✓ <verified date>". Data for all 11 countries is in `SPEC.md` §4 (Singapore, Japan, Australia, Netherlands, US, Canada, Ireland, Sweden, Norway, Denmark, Switzerland). **Sweden has no sponsor registry** (scheme discontinued Dec 2023) — surface exactly as written, do not invent one.

### Saved searches
H1 + subtitle. List of cards (white, border `#e0e6ea`, radius 14px): name + "N new"/"up to date" pill + mono filter summary; right side = channel (Telegram ✈ / Stdout ▸) + mono "last run …". A dashed "New saved search from current filters" button (border `#cdd6db`, hover border/text teal).

---

## Interactions & Behavior
- **Nav:** switches the main view. Only one view visible at a time.
- **Filtering (Jobs):** keyword (matches title/company/description/categories), country[], category[] (multi, any-match), level[], posted-since, sponsor-tier[] (opt-in). All combine (AND across dimensions, OR within a dimension). Results re-sort live.
- **Sorting:** `Sponsor tier` → `ORDER BY sort_rank DESC, posted_at DESC` where explicit_yes=3, registry_inferred=2, unknown=1, explicit_no=0. `Date` → newest first. **`explicit_no` is shown last, never hidden by default.**
- **Status workflow (per job):** `new → seen → starred/hidden`. Opening a job marks `new`→`seen`. Star toggles starred↔seen. Hide sets hidden (excluded from every non-Hidden view); Restore sets hidden→seen. Status view filters: New = `new` only; Starred = `starred`; All = everything except hidden; Hidden = `hidden`. Segment counts reflect the current keyword/country/etc. filters.
- **Dropdown menus:** click button to open; a fixed full-screen invisible layer catches outside-clicks to close. Only one menu open at a time.
- **Drawer:** click overlay or close/×/Esc to dismiss. `bk-fade` (0.15s) overlay, `bk-slide` (0.22s) panel.
- **Countries map:** clicking a pin selects its country and highlights the matching card (and vice-versa); clicking again deselects.
- **Hover:** rows (bg `#f4f7f8`), icon buttons (bg `#e9eef0`), CTA (darken to `#0b7268`), dashed add button (teal border/text).

## State Management
Prototype state (recreate as React state / server state as appropriate):
- `view`: 'jobs' | 'searches' | 'companies' | 'countries'
- `search` (string), `countries` (string[]), `categories` (string[]), `levels` (string[]), `posted` ('any'|'24h'|'7d'|'30d'), `tiers` (string[]), `sortBy` ('tier'|'date')
- `menu`: null | 'country' | 'tier' (which dropdown is open)
- `jobId`: selected job for the drawer (null = closed)
- `selectedCountry`: highlighted country on the Countries view
- `statuses`: map of jobId → user_status override (persist to backend `jobs.user_status`; default from server)
- `statusView`: 'new' | 'starred' | 'all' | 'hidden'

Data fetching: jobs, companies, countries, saved searches, and status mutations should hit the FastAPI API (`SPEC.md` §7). The prototype hard-codes sample arrays; replace with real queries. Times display in Asia/Jakarta at day boundaries (`SPEC.md` §9).

## Design Tokens

**Surfaces / structure**
| Token | Hex |
|---|---|
| Page bg | `#eef1f3` |
| Surface (cards, inputs) | `#ffffff` |
| Sidebar bg | `#f6f8f9` |
| Table header / hover bg | `#f4f7f8` |
| Chip bg | `#e9eef0` |
| Segment track / chip track | `#e2e8eb` |
| Border (primary) | `#e0e6ea` |
| Border (inputs/menus) | `#dbe2e6` |
| Row divider | `#eef2f4` |

**Text**
| Role | Hex |
|---|---|
| Ink / primary | `#16202a` |
| Body muted | `#5d6b76` |
| Secondary muted | `#6b7784` |
| Faint / labels | `#93a0aa` / `#97a3ac` |
| Mono faint | `#a3aeb6` |

**Accent (teal)**
| Token | Hex |
|---|---|
| Accent | `#0e8a7d` |
| Accent hover | `#0b7268` |
| Accent soft bg | `#d7efec` |
| Accent soft fg | `#0a6c62` |
| Accent border | `#a9dcd5` |

**Sponsorship tiers** (bg / fg / dot)
| Tier | bg | fg | dot |
|---|---|---|---|
| explicit_yes (Sponsors) | `#dcf0e4` | `#1b8a5a` | `#25a56a` |
| registry_inferred (Registry) | `#dde9f4` | `#2f6fae` | `#3f83c8` |
| unknown (Unknown) | `#e7ecef` | `#6b7784` | `#a6b0ba` |
| explicit_no (No sponsor) | `#f6e3e1` | `#c0504a` | `#d26f68` |

**Source health** (bg / fg / dot): ok `#dcf0e4`/`#1b8a5a`/`#25a56a` · degraded `#faf1dd`/`#9a6a12`/`#d99a2b` · quarantined `#f6e3e1`/`#c0504a`/`#d26f68` · pending `#e7ecef`/`#6b7784`/`#a6b0ba`.

**Status pills** (bg / fg): new `#d7efec`/`#0a6c62` · seen `#e7ecef`/`#6b7784` · starred `#cbeae4`/`#0a6c62` · hidden `#f6e3e1`/`#c0504a`.

**Typography** — Geist (400/500/600/700), Geist Mono (400/500). H1 24px/700/-0.02em · drawer title 21px · section/card titles 15–17px/700 · body 13–13.5px · row title 15px/600 · uppercase labels 10.5px/600/0.06em · mono metadata 11–12px.

**Radius:** cards/table 14px · geo panel 16px · inputs 10px · menus 12px · segment track 9px / item 6–7px · chips 6px · pills & dots 999px.

**Shadow:** menu `0 12px 32px rgba(20,32,42,0.12)` · drawer `-20px 0 50px rgba(20,32,42,0.1)` · segment-active `0 1px 2px rgba(0,0,0,0.08)`.

**Spacing:** page padding 26px 34px · card padding 18–24px · row padding 16px 24px · gap between filter controls 8–10px.

**Animations (in `<style>`):** `bk-fade` (opacity 0→1), `bk-slide` (translateX 40px→0 + fade), `bk-pulse` (scale 0.55→1.9 + fade, used for map pin rings).

## Assets
- **Fonts:** Geist + Geist Mono (Google Fonts). Use the equivalent in the target codebase.
- **Icons:** all inline SVG (stroke-based, 1.5–2px), hand-drawn in the prototype — nav glyphs, search, chevrons, checkmark, star, eye/eye-off, restore, globe, close, external-link, beacon logo. Replace with the codebase's icon set (e.g. Lucide) matching these shapes/weights.
- **World map:** procedurally drawn dot-grid on `<canvas>` (no image asset) — see the `drawMap`/`ELLIPSES`/`PINS` logic in `Beacon.dc.html` if you want to reproduce it; otherwise any equatorial-projection dot/vector world map with lon/lat pin placement works.
- No raster images or brand assets.

## Files
- `Beacon.dc.html` — the full high-fidelity prototype (all four views + drawer). Primary reference.
- `Beacon Palettes.dc.html` — the 5 explored color palettes; **1b "Nordic Slate & Teal" is the selected one** and is what `Beacon.dc.html` uses. Reference only.
- `support.js` — the prototype runtime (needed only to open the `.dc.html` files in a browser). **Not** a production dependency.
- `SPEC.md` — authoritative product spec: data model, sources, classification, sort semantics, source-health taxonomy, country reference data, back-end architecture.

To preview the prototype: open `Beacon.dc.html` in a browser (it loads `support.js` from the same folder).
