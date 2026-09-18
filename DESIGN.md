# DESIGN.md — Beacon UI Handoff

> Canonical UI spec. Reflects the **dark holographic, two-pane** design handoff
> (`~/Downloads/Beacon-2.zip` → `design_handoff_beacon/Beacon.dc.html`, 2026-07-13). This is the
> **second** handoff: it keeps the dark theme + 88px rail + globe home of the first, and changes the
> Countries home from a stacked layout (globe on top, jobs/cards below) to a **two-pane row** — globe
> fixed left, a scrolling side panel right holding either the country cards or the jobs pane. It
> supersedes both the first dark handoff and the earlier light "Nordic Slate & Teal" theme. The
> `.dc.html` prototype is ground truth; where this doc and the top-level SPEC.md disagree on product
> behavior, SPEC.md wins. The prototype `.dc.html` and `support.js` are references only, not shipping
> code. (The bundled README prose describes a 236px light sidebar that contradicts its own dark
> prototype — the runnable prototype file wins.)
>
> Implemented on `main` (see PROGRESS.md, Decisions 2026-07-13 "Beacon-2").

---

# Handoff: Beacon — personal tech-job scanner with visa-sponsorship awareness

## Overview
Beacon is a single-user, self-hosted web app that polls ATS/job-board APIs, classifies postings
(category, level, sponsorship tier), and surfaces them filtered by **visa-sponsorship signal** and
**target relocation country — plus the home market, Indonesia**. The **home page is a Countries &
visa reference** dominated by an interactive **3D holographic dot-globe**. The Countries home is a
**two-pane row**: the globe stays
fixed on the left, and a scrolling **side panel** on the right holds the content. Selecting a country
(tap a globe beacon pin or a country card) does not navigate away — it rotates the globe to frame a
**beacon arc from Jakarta to the country**, and swaps the side panel from the all-markets card stack
to that country's **relocation reference + a Jobs list**, all beside the globe. **Jakarta is itself
selectable** — the amber origin marker is a pin like any other, and picking it shows Indonesia's jobs
with **no arc drawn** (origin and destination coincide) and a home-market block in place of the visa
reference. Clearing the selection returns the panel to the card stack. A **Saved searches** page and
a slide-in **Job-detail drawer** round out the app. There is **no standalone Jobs route and no
Companies tab** — source
health folds into a widget on the globe; Jobs is a pane inside Countries.

## Fidelity
**High-fidelity, dark holographic.** Match the exact hex/px/radius values in the token tables below.
Body background `#04121a`; teal accent `#5eead4`. Fonts: **Geist** (UI) + **Geist Mono**
(codes/slugs/timestamps). `-webkit-font-smoothing: antialiased`.

---

## Global Layout
Full-viewport flex: a fixed **88px icon-rail** (left) + a **main** area (`flex:1`). Saved searches /
Settings scroll the main area; **Countries is a fixed-height (`100vh`, `overflow:hidden`) two-pane
column** whose right-hand side panel owns the scroll (see §1). A **job-detail drawer** (560px, max
100%) slides in from the right over a dim scrim, above everything.

### Icon-rail (88px, bg `#071a22`, right border `#123842`, padding 20×10, flex column, centered)
- **Brand:** a 26px teal beacon-signal glyph (concentric arcs + centre dot, `#5eead4`) over "Beacon"
  (12.5px/700, `#e3fdf6`), gap 7px, 22px bottom padding.
- **Nav** (2 items, stacked icon-over-label, gap 5px, 11×4 pad, radius 11px):
  - **Globe** (globe icon) → the Countries home. Default/active view.
  - **Saved** (bookmark icon + mono count badge, top-right of the icon) → Saved searches. **The
    badge count is DERIVED** — the sum of `new_count` across `/searches`, never typed (it shipped
    as a literal "4" beside two searches; slice 19). **It is absent, not "0", when nothing is
    new**: a zero chip reads as a control with nothing in it.
  - Active item: bg `rgba(94,234,212,0.14)`, color `#5eead4`. Idle: color `#6c948f`. Label 10.5px/600.
  - Badge: absolute top:-5 right:-8, 9.5px/700 mono, bg `#5eead4`, color `#04121a`, radius 999px.
- **Footer** (`margin-top:auto`): a **Settings gear** icon-button (off the main nav — reachable for
  Telegram creds, slice 8) over a vertical mono tag (9px, `#3f7a76`, `writing-mode:
  vertical-rl`, letter-spacing 0.1em, opacity 0.8). The tag reads **"{age} · LIVE"** from
  `/companies/health`'s `last_poll_at` — e.g. "8h ago · LIVE" — and **"no poll yet"** when nothing
  has ever polled. **An age, not a clock time**: "07:04" (the literal it shipped as) cannot tell
  this morning's poll from last Tuesday's, and **"LIVE" is a claim, so it is only made when a poll
  has actually landed.**

---

## Screens / Views
The main area shows one of three views (`?view=` param, default **countries**): **Countries**
(home), **Saved searches** (`?view=searches`), **Settings** (`?view=settings`, off-nav). The Jobs
list is **not its own view** — it is a pane inside Countries, gated by a selected country
(`?focus=CODE`). The **Job-detail drawer** (`?job=id`) overlays any view.

### 1. Open roles & target markets (home)
- **Layout:** the view is a fixed-height flex column (`100vh`, `overflow:hidden`, pad `24×34×26`):
  header on top, then a **two-pane row** (`display:flex; gap:18px; flex:1; min-height:0`) — the
  **globe panel** left (`flex:1.35; min-width:0; min-height:420px`) and the **side panel** right (see
  below). The globe is always visible; only the side panel changes with selection.
- **Header:** H1 "Open roles & target markets" (24px/700/-0.02em, `#e3fdf6`); sub (13.5px,
  `#7fa8a3`, max-width 820px): "Every market's live postings, sponsor-tier first. Tap a beacon to
  narrow to one market; Markets holds the visa reference, as-known Jan 2026 — thresholds and
  timelines change." **The old copy ("Tap a beacon to inspect that market and its live postings")
  described a page whose default state showed no postings at all** — it named the only path to
  the list rather than the screen you land on.
- **Globe panel** (always visible, left pane; radius 18px, overflow hidden, `flex:1.35`,
  min-height 420px; dark radial bg `radial-gradient(125% 105% at 50% 4%, #0c3138, #06181f 52%,
  #04111a)`; border `#10424a`; shadow `0 24px 60px rgba(4,18,26,0.35), inset 0 0 90px
  rgba(45,212,191,0.05)`):
  - Full-bleed `<canvas>` renders the holographic 3D dot-globe (see **Globe rendering**).
  - **Top overlay** (pointer-events:none): left = teal globe icon + "Target geography"
    (14.5px/700, `#e3fdf6`) + hint "drag to rotate · tap a beacon" (12px mono, `#5f9a95`); right =
    legend "Primary target" (dot `#5eead4`, teal glow) / "Nice-to-have" (dot `#93a7ad`) / **"Home"
    (dot `#fcd34d`, amber glow)**, 12px `#9fc7c2`.
  - **Bottom-left caption:** "live beacon field · {n} markets" — **n is DERIVED from /countries,
    never typed** (it read "11 markets + home" while the code already counted; slice 18 made that
    drift visible by adding four). (11px, uppercase, 0.06em mono,
    `#3f7a76`).
  - **Bottom-right Source-health widget** (glass: bg `rgba(4,17,26,0.72)`, `backdrop-filter:blur(6px)`,
    border `#10424a`, radius 12px, min-width 218px — widened from 186px in slice 19 for the second
    block): "SOURCE HEALTH" label + the poll age (mono, "poll 8h ago" / "no poll yet" — see the rail
    footer for why it is an age), then **four** dot rows — OK (`#34d399`), degraded (`#fbbf24`),
    quarantined (`#f87171`), **pending** (`#8296a0`), 12px `#9fc7c2` with mono counts `#c4ebe4`.
    **Every count is DERIVED from `/companies/health`, never typed** — it shipped as "44 OK / 1
    degraded / 2 quarantined" against a live 65/0/3, with two `pending` sources it had no row for.
    **Pending** is a seed company whose ATS has no adapter yet: never polled, so neither healthy nor
    failing, and it takes the `unknown`-tier grey because it is the same absence of information.
  - **Registers block**, under a 1px `#10424a` divider inside the same widget (one "what do we
    actually have" surface; the globe has room for one). "REGISTERS" label, then one 11px mono row
    per registry bit from `/registries`: name (`#c4ebe4`) + detail. Ingested reads
    "6,360 · 21 firms · 11d ago" (`#9fc7c2`), with "· stale" appended past the 45-day window; a
    register with no snapshot reads **"never ingested" in the degraded amber `#fbbf24`** — not
    omitted and not "0". **The absence is the content:** UK/NL/US have adapters, are wired into
    `refresh.py`, and had never been downloaded onto this box while SPEC §4 said otherwise.
- **Side panel** (right pane; `<aside>`, `flex:1; min-width:372px; max-width:512px; overflow-y:auto`,
  bg `#071a22`, border `#123842`, radius 18px, its own scroll so the globe never leaves the viewport).
  It opens with a **two-segment tab strip** — **Jobs** (default) / **Markets** — and shows the
  **jobs pane** or the **all-markets card stack** accordingly (`?panel=markets`; Jobs is the absent
  value). The strip is `position:sticky; top:0; z-index:7`, pad `12×20×10`, bg `#071a22`, 1px
  `#123842` bottom border; segments reuse the §2 segmented-control style (active bg
  `rgba(94,234,212,0.16)`, fg `#5eead4`, radius 7px; idle `#7fa8a3`). The jobs pane's own sticky
  header sits **directly below it** at `top: var(--panel-tabs-h)` (45px), `z-index:6` — stacked
  stickies, so both the panel switch and the result count stay put while the list scrolls.
  **The panel is not gated on a selection.** Until slice 21 it was: no country selected meant the
  card stack and **no jobs on screen at all**, while the corpus held 9,130 open canonical ones.
  `?focus=` is now a *filter* — it seeds the country filter and the relocation legend — and the
  visa reference is a tab you choose, not a state you fall back into.

- **All-markets card stack** (no selection; pad `16×20×20`): a small uppercase caption "N markets ·
  tap a beacon or a card" (`#5f8f8a`) then a **vertical stack** of country cards (`flex-direction:
  column; gap:10px` — not a grid; the panel is narrow). Card: bg `#0a2028`, border `#123842`, radius
  12px, pad `14×16`, cursor pointer, hover bg `#0d2a33` / border `#1a4650`. Name (15px/700,
  `#e3fdf6`) + tier badge ("Primary" teal `rgba(94,234,212,0.15)`/`#5eead4`, "Nice-to-have" grey
  `rgba(148,180,186,0.12)`/`#9fc7c2`, **"Home" amber `rgba(252,211,77,0.15)`/`#fcd34d`**). **Two**
  labelled blocks — Work visa / PR path (label 10.5px uppercase `#5f8f8a`, value 12px `#c4ebe4`);
  **Citizenship is omitted here** — it appears in the reference legend once a market is selected
  (§2). Footer (top border `#123842`): registry note (`#7fa8a3`) + "✓ {verified}" (mono, `#4f7873`).
  Clicking a card selects that country (globe focus + arc + jobs pane replaces the stack). **Sweden
  has no sponsor registry** (scheme discontinued Dec 2023) — surface exactly as written, do not
  invent one.
- **Indonesia home card** — pinned **first** in the stack, above the relocation markets, with an amber
  accent border `#5c4a1f` in place of `#123842`. Name "Indonesia" + the "Home" badge. Its two labelled
  blocks are **Right to work / Market**, reading "Already held — no visa" and "Jakarta · iOS, Backend,
  AI/ML" (`#c4ebe4`). Footer reads "no registry — not applicable" (`#7fa8a3`) and carries **no
  "✓ verified" date**: there is nothing to re-verify, and a date here would read as reference data going
  stale. Clicking it focuses Jakarta with **no arc** (see §Globe rendering).

### 2. Jobs pane (in the side panel, beside the globe; `?focus=CODE`)
Rendered inside the §1 side panel, so its sections carry their own 20px horizontal inset; only the
header is sticky.
- **Sticky header** (`position:sticky; top: var(--panel-tabs-h); z-index:6`, bg `#071a22`, pad
  `17×20×13`, border-bottom `#123842`): an "← All markets" back button (chevron + text, 12.5px/600,
  `#5eead4`, no bg) that clears the country filter — **shown only when a country is filtered**, since
  on the default view it was a control that undid nothing above a heading already reading "Jobs";
  then H2 = "Jobs · {Country}" (20px/700) when exactly one country is filtered, else "Jobs"; then a
  result sub-line (12.5px `#7fa8a3`, e.g. "New · 15,641 postings · sorted by sponsor tier").
  **The count is the server's `total`, not the number of rows on the page.** It read `jobs.length`
  — one page of 50 — so selecting the US reported "50 postings" against a live 3,365.
- **Load more** (end of the list; full width, dashed `#14514c` border, radius 12px, bg `#0a2028`,
  teal 12.5px/600 label, hover bg `#0d2a33` + solid teal border): "Load more · {loaded} of {total}".
  The API serves 50 rows a page and the list pages by `?offset=`; the control disappears once every
  row is loaded. A derived total over a list you cannot page past row 50 is its own kind of lie,
  which is why the two shipped together.
- **Relocation-reference legend** (shown for the selected market; margin `15×20×0`, bg
  `rgba(94,234,212,0.06)`, border `#14514c`, radius 13px, pad `15×17`): title "{Country} — relocation
  reference" (14px/700) + tier badge; then **Work visa / PR path / Citizenship** blocks (labels teal
  `#5eb5ab` 10px uppercase, values `#d6f5ee` 12.5px); footer "verified {date}" (mono `#5eb5ab`). This
  is where Citizenship lives (it's off the compact card).
- **Home-market block** — the Indonesia substitute for the legend above. Same box metrics, amber
  palette: bg `rgba(252,211,77,0.06)`, border `#5c4a1f`, labels `#c9a94e`, values `#f3e5bd`. Title
  "Indonesia — home market" + "Home" badge; one line of body copy, "You already have the right to work
  here. These roles need no visa, no sponsor and no registry check."; then a single **Focus** block
  reading "iOS · Backend (Java, Python) · AI/ML". **No visa / PR / citizenship blocks and no verified
  date** — every field the relocation legend carries is inapplicable here, and rendering them empty or
  as "n/a" would read as missing data rather than as an absent question.
- **Filter bar** (pad `14×20×4`; **not** sticky — it scrolls with the panel; controls wrap within the
  ~372–512px width):
  - **Status segmented control** (New / Starred / All / Hidden). Track bg `#0c2831`, border `#123842`,
    3px pad, radius 9px. Active segment: bg `rgba(94,234,212,0.16)`, color `#5eead4`, radius 7px.
    Idle: `#7fa8a3`. Selecting a country opens the pane on **All**; standalone default is **New**.
  - **Search input** (flex, min 240px): bg `#0a2028`, border `#123842`, radius 10px, 40px left pad
    for the magnifier (`#5f8f8a`). Placeholder "Search title, company, keyword…".
  - **Sort** segmented control ("Sponsor tier" / "Date"), same segment style. Default Sponsor tier.
  - **Country** + **Sponsor tier** pill dropdowns. Pill idle: bg `#0a2028`, border `#123842`, `#9fc7c2`.
    Active (selection present): bg `rgba(94,234,212,0.15)`, border `#14514c`, `#5eead4`; label shows
    count ("Country · 2"). Menus: bg `#0c2831`, border `#1a4650`, radius 12px, shadow `0 16px 40px
    rgba(2,10,14,0.6)`, fade-in. Country rows carry a P/☆ tier badge; the Sponsor-tier menu opens
    with "Opt-in filter. Off by default — nothing is hidden." **Tier filter is never on by default.**
  - **The country menu has two groups, and the divide is the point.** It opens with the caption
    "Open postings per market — the list also carries closed ones, greyed", then the **§4 markets**
    in the order `/countries` serves them, each with a mono open count (`#9fc7c2`, 11px) between
    the name and its tier badge. Then a 1px `#123842` divider, an uppercase **"Other markets"**
    heading (`#5f8f8a`, 10.5px, 0.06em) and the note "Not relocation targets — no visa reference,
    no globe pin. Postings only.", then the countries §4 has **never assessed**, ordered by open
    count descending (ties on code). **Measured 2026-09-18: 47 of them, 1,844 open jobs, led by
    IN 355 · MY 235 · TH 215 · DE 198** — every one of which `/jobs` already served, with no way
    to ask for it. Those rows carry **no P/☆/⌂ glyph**: the badge is keyed by `priority_tier`, a
    §4 concept these countries do not have, and a grey "unknown" glyph would assert a tier had
    been assessed and come back empty. Their names come from `Intl.DisplayNames`, not from a
    code→name table in the repo. **Every count is DERIVED from `/markets`, never typed.** The
    menu scrolls (`max-height:320px`) — 63 rows do not fit on screen. The caption reads "Open
    postings per market", and since closed rows left the default list that is exactly what the
    chip opens onto.
  - **Chip row:** "CATEGORY" label + 7 category pills (iOS, Backend, AI/ML, Android, Flutter,
    Fullstack, Frontend) · divider · "LEVEL" + 3 pills (Senior, Staff, Lead). Pill styles as above.
- **Job list** (pad `4×20×22`; a **stack of compact cards**, `flex-direction:column; gap:10px` — not
  a wide table). Card: bg `#0a2028`, border `#123842`, radius 12px, pad `13×15`, cursor pointer, hover
  bg `#0d2a33` / border `#1a4650`, greyed (`opacity:0.55`) when hidden:
  - **Top row:** left = title (14px/600/-0.01em, `#e3fdf6`) over company (12px/500, `#9fc7c2`) — the
    title block is the drawer-open trigger; right (flex-shrink:0) = Star + Hide (Restore when hidden)
    icon buttons (28px, hover `#0f333c`, star fills teal `#5eead4`).
  - **Meta row** (margin-top 11px, wraps): a **"Closed" chip** when the posting is delisted, then
    the sponsorship tier chip (6px dot + label) + city (11.5px `#c4ebe4`) + level (11px mono
    uppercase `#5f8f8a`) + posted age (11.5px `#5f8f8a`, pushed right).
  - **Closed postings are out of the list by default, and greyed when you ask for them.** The
    "Show closed" pill (same idle/active pill styling as the Country and Sponsor-tier dropdowns,
    `?closed=1`) brings them back; a returned row is muted (`opacity:0.55`, the same mute a hidden
    row takes) and carries a neutral outlined "Closed" chip — 11px mono uppercase, border
    `#123842`, text `#5f8f8a`. **Grey, deliberately not a tier colour:** closed is a fact about the
    posting's life, not about its sponsorship. SPEC §5 always said a delisted posting is "kept,
    greyed out", but `closed_at` was never on the `/jobs` DTO, so **6,518 of the 15,648 rows the
    endpoint served — 42% — rendered as though you could still apply**. Greying them made the
    density visible and the density is why they are now hidden: **Sweden measured 2,669 canonical
    against 393 open, 86% closed**, so a filtered list was mostly dead rows. Hidden is not
    discarded — the toggle is one click and the drawer reports the same field.
  - Category chips and a per-row "open original" link are **not** on the card — categories stay as
    filter pills, and the original-posting link lives in the drawer CTA. Per-view empty states
    (New → "You're all caught up", etc.).

### 3. Job-detail drawer (`?job=id`, overlays any view)
Scrim `rgba(2,10,14,0.55)` + right drawer (560px, bg `#071a22`, left border `#123842`, shadow
`-20px 0 50px rgba(2,10,14,0.55)`, slide-in `bk-slide` 0.22s). Opening a `new` job marks it `seen`.
Header: company + mono slug over title (21px/700); a cluster of 34px icon buttons (bg `#0c2831`,
border `#123842`, hover `#0f333c`): Star, Hide/Restore, Close. Meta chips: tier chip, status pill,
grey info chips (city/remote/level), "posted {age}". **Sponsorship evidence** panel (border tinted by
tier): colored header + body (explicit → italic quote with a tier-colored left accent; registry →
registry list + "Match confidence 0.94 · company-level signal, not a per-role guarantee." — bitmask
members `UK | NL | US | MANUAL`, no SE; unknown → grey "shown, ranked below … never excluded" note).
**Description**. **Country relocation** panel (bg `rgba(94,234,212,0.06)`, border `#14514c`; Work visa
/ PR / Citizenship, labels `#5eb5ab`, values `#d6f5ee`; "verified {date}"). **Sources** list (mono,
small grey dot; "· deduped across N" when multi-source) + a teal CTA "Open original posting →" (bg
`#5eead4`, text `#04121a`, radius 10px, hover `#8ff3e2`).

### 4. Saved searches (`?view=searches`)
H1 "Saved searches" + sub. Column of cards (max-width 820px, bg `#0a2028`, border `#123842`): name
(16px/600) + status badge ("N new" teal / "up to date" grey) + mono filter string; right = channel
("✈ Telegram" / "▸ Stdout") + "last run {time}". Footer: a dashed "New saved search from current
filters" button (border `#1e5058`, hover border/text teal).

### Settings (`?view=settings`, off-nav)
Telegram bot-token / chat_id form + "Send test" (slice 8). Reachable via the rail-footer gear only.

---

## Interactions & Behavior
- **Navigation:** `?view=` (countries default / searches / settings). Within Countries, **`?panel=`**
  decides the side panel — jobs (absent, the default) vs the card stack (`markets`) — and `?focus=CODE`
  is a *filter*, not a gate. Selecting a country sets `focus=CODE`, seeds `country=CODE` and returns the
  panel to jobs; it **does not touch `?status=`**, because forcing `status=all` moved the list out from
  under the reader on every beacon tap. Clearing (back button, ocean tap) drops `focus`/`country` only;
  the Globe nav resets `panel` too. All filter/view/drawer state lives in URL search params (shareable,
  bookmarkable, Back-button undo).
- **Globe:** drag rotates (yaw += dx·0.45, pitch clamped ±82°; a >3px drag is a rotate, not a click).
  Pointer-up without a drag: on a pin (≤15px) selects that country; on empty ocean clears the selection.
  The **Jakarta origin marker is hit-tested as a pin** on the same 15px radius and selects `focus=ID`.
  With a highlight, the globe eases to the Jakarta↔country great-circle midpoint; **when `ID` is the
  selection that midpoint degenerates to Jakarta itself, so the globe simply eases to Jakarta and no arc
  is drawn**; idle it slow-spins.
- **Idle tour:** untouched for 15s, the globe starts walking the markets by itself, one per 9s —
  a lit beacon field rather than a dead screen, and the caption says "auto-touring — move to take
  over". Any pointer move >2px, key, wheel, touch or scroll hands control straight back, and
  `prefers-reduced-motion` switches it off entirely. **It drives the globe and nothing else.**
  It used to write `?focus=`, which was harmless while the panel showed visa cards and
  intolerable once the panel shows the job list: it would take the list away from a reader every
  9 seconds and never return to the unfiltered view. What is *lit* (arc, pin pulse, camera) and
  what is *filtered* (`aria-pressed`, the country filter) are now separate facts — `Globe` takes
  `highlightCode` alongside `selectedCode`, defaulting to it.
- **Filtering (jobs pane):** keyword (title/company/description/categories), country[], category[],
  level[], sponsor-tier[] (opt-in). AND across dimensions, OR within one. Re-fetches live.
  **Closed postings are excluded unless "Show closed" is on** — the default everywhere, including
  the saved-search card counts and the Telegram digest, because alerting on a delisted job is the
  same defect as listing one. This is what makes a country chip's count and the list it opens the
  same number: SE reads 393 on the chip and returns 393 rows.
- **Sorting:** Sponsor tier → `sort_rank DESC, posted_at DESC` (yes=4, **not_required=3**, registry=2,
  unknown=1, no=0); Date → newest first. **`explicit_no` shows last, never hidden by default.** A
  confirmed sponsor abroad outranks a home role; a home role outranks anything speculative.
- **Job triage:** row click opens the drawer (a `new` job becomes `seen`); Star toggles starred/seen;
  Hide → hidden (excluded from all views but Hidden); Restore → seen.
- **Sponsorship is a soft signal:** tier drives sort_rank + default order; the tier filter is opt-in,
  never pre-selected. The Sponsor-tier menu now lists **five** rows — "No visa needed" (`not_required`)
  sits second, between "Sponsors" and "Registry" — and, like every other tier, ships unselected.

## Globe rendering
Procedural holographic 3D dot-globe on a `<canvas>` 2D context, recomputed every frame
(`requestAnimationFrame` while Countries is mounted). Real continent outlines (`LAND`) with inland
seas (`SEA`) punched out build a 1024px equirectangular mask once; a 2° land-point cloud is sampled
from it. Each frame draws (back→front): teal atmosphere glow; shaded globe face; graticule (30°/20°,
brighter on the front hemisphere); the land dot cloud (1.35px, `rgba(94,234,212, 0.28→0.92)` by
depth, back hemisphere culled); a bright rim; the **beacon arc** (Jakarta → selected country: 90-seg
great circle bowed out `1+0.22·sin(πf)`, bright on the front / faint on the back, a `#eafffb`
travelling pulse, amber `#fcd34d` Jakarta origin marker + label) — **skipped entirely when the selection
is `ID`**, since a great circle from Jakarta to Jakarta has no length and a bowed placeholder would be a
lie about distance; then **pins** (front: glowing dot `#5eead4` primary / `#9fb6bb` nice-to-have + pulse
ring + label chip; back: faint ghost). The **Jakarta origin marker is always drawn**, arc or not, and is
itself a selectable pin: amber `#fcd34d`, gaining the same pulse ring the target pins use when `ID` is
the current selection. Screen positions of front pins **including Jakarta** are cached for 15px
hit-testing. See `frontend/src/countries/globeGeo.ts` (data + math, ported verbatim) and `Globe.tsx`
(canvas rAF engine, jsdom-guarded; sr-only pin
buttons provide keyboard/test selection).

---

## Design Tokens (dark holographic)

### Colors
- **Surfaces:** page `#04121a`; rail/drawer `#071a22`; card/input `#0a2028`; raised (segment track /
  table header / menu) `#0c2831`; row hover `#0d2a33`; neutral chip `#0f333c`.
- **Borders:** card/panel/divider `#123842`; menu `#1a4650`; globe panel `#10424a`; row `#0f2c34`;
  accent border `#14514c`.
- **Text:** heading `#e3fdf6`; body/value `#c4ebe4`; chip `#9fc7c2`; muted `#7fa8a3`; label `#5f8f8a`;
  mono-faint `#4f7873`; caption `#3f7a76`.
- **Teal accent:** `#5eead4` (primary), `#8ff3e2` (hover), `#04121a` (ink on teal); soft fills
  `rgba(94,234,212,0.14–0.16)`, accent border `#14514c`.
- **Globe scene:** radial `#0c3138 → #06181f → #04111a`, border `#10424a`; atmosphere/land/graticule/
  rim/arc on `rgba(94,234,212, α)`; face `rgba(15,70,76,0.62) → rgba(4,20,27,0.5)`; overlay `#e3fdf6`/
  `#9fc7c2`/`#5f9a95`/`#3f7a76`; primary pin `#5eead4`, nice-to-have `#93a7ad`/ghost `#9fb6bb`;
  Jakarta origin / home pin `#fcd34d` (the same amber as the `not_required` badge); arc pulse `#eafffb`.
- **Sponsorship tiers (bg / fg / dot):** yes `rgba(52,211,153,0.14)`/`#5fe3a3`/`#34d399`;
  **`not_required` (label "No visa needed") `rgba(252,211,77,0.14)`/`#f8dd8a`/`#fcd34d`** — deliberately
  the Jakarta-origin amber, so the badge, the home card's accent and the globe's home marker read as
  one thing; registry `rgba(96,165,250,0.14)`/`#7cc0fb`/`#60a5fa`;
  unknown `rgba(148,180,186,0.12)`/`#9fc7c2`/`#8296a0`;
  no `rgba(248,113,113,0.14)`/`#f7a6a2`/`#f87171`.
- **Status pills (bg / fg):** new `rgba(94,234,212,0.16)`/`#5eead4` · seen `rgba(148,180,186,0.12)`/
  `#9fc7c2` · starred `rgba(94,234,212,0.16)`/`#5eead4` · hidden `rgba(248,113,113,0.14)`/`#f7a6a2`.
- **Source-health dots:** OK `#34d399`, degraded `#fbbf24`, quarantined `#f87171`, **pending
  `#8296a0`** (the `unknown`-tier grey, reused deliberately — both mean "not known", and a fifth
  colour would imply a fifth kind of thing).

### Typography
Geist (UI, 400/500/600/700) + Geist Mono (400/500). H1 24/700/-0.02em; drawer title 21/700; card
name 16–17/600–700; body 13–14; row title 15/600; labels 10.5–11/600 uppercase (0.05–0.06em);
mono details 11–12.5.

### Radii / Shadows / Animations
Radii: 999 (pills/dots), 18 (globe panel), 14 (cards), 12 (menus/panels), 11 (nav), 9–10
(inputs/segment track), 7 (segment buttons), 6 (chips). Shadows: panel `0 24px 60px
rgba(4,18,26,0.35), inset 0 0 90px rgba(45,212,191,0.05)`; menu `0 16px 40px rgba(2,10,14,0.6)`;
drawer `-20px 0 50px rgba(2,10,14,0.55)`. Animations: `bk-fade` (opacity), `bk-slide` (translateX
40px→0 + fade, 0.22s), `bk-pulse` (scale 0.55→1.9 + fade). Page padding: Countries `24×34×26`,
Saved searches `26×34×40`; the two-pane row gap is 18px; side-panel sections inset 20px horizontally.

All tokens live in `frontend/src/tokens.css` as CSS custom properties — do not invent colors.

## Assets
No raster assets. Icons via Lucide (Globe, Bookmark, Settings, Search, ChevronDown/Left, Star,
Eye/EyeOff, Check, ExternalLink, Plus, X) matching the prototype's stroke SVGs; the Beacon brand
glyph is an inline SVG. The globe is procedurally generated on a canvas — no map image. Fonts:
Geist + Geist Mono (Google Fonts).

## Files (prototype references, not shipping code)
`~/Downloads/Beacon-2.zip` → `design_handoff_beacon/`: `Beacon.dc.html` (the hifi dark two-pane
prototype: markup + `class Component` logic with seed data, `LAND`/`SEA`/`PINS`, the canvas globe
engine, and `renderVals()` filter/sort derivations), `README.md` (handoff prose — its 236px light
sidebar section contradicts the dark prototype; the prototype wins), `support.js` (the `.dc.html`
runtime — ignore), `SPEC.md` (product/architecture context).
