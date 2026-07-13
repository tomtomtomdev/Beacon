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
**target relocation country**. The **home page is a Countries & visa reference** dominated by an
interactive **3D holographic dot-globe**. The Countries home is a **two-pane row**: the globe stays
fixed on the left, and a scrolling **side panel** on the right holds the content. Selecting a country
(tap a globe beacon pin or a country card) does not navigate away — it rotates the globe to frame a
**beacon arc from Jakarta to the country**, and swaps the side panel from the all-markets card stack
to that country's **relocation reference + a Jobs list**, all beside the globe. Clearing the
selection returns the panel to the card stack. A **Saved searches** page and a slide-in **Job-detail
drawer** round out the app. There is **no standalone Jobs route and no Companies tab** — source
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
  - **Saved** (bookmark icon + mono "4" count badge, top-right of the icon) → Saved searches.
  - Active item: bg `rgba(94,234,212,0.14)`, color `#5eead4`. Idle: color `#6c948f`. Label 10.5px/600.
  - Badge: absolute top:-5 right:-8, 9.5px/700 mono, bg `#5eead4`, color `#04121a`, radius 999px.
- **Footer** (`margin-top:auto`): a **Settings gear** icon-button (off the main nav — reachable for
  Telegram creds, slice 8) over a vertical mono tag "07:04 · LIVE" (9px, `#3f7a76`, `writing-mode:
  vertical-rl`, letter-spacing 0.1em, opacity 0.8).

---

## Screens / Views
The main area shows one of three views (`?view=` param, default **countries**): **Countries**
(home), **Saved searches** (`?view=searches`), **Settings** (`?view=settings`, off-nav). The Jobs
list is **not its own view** — it is a pane inside Countries, gated by a selected country
(`?focus=CODE`). The **Job-detail drawer** (`?job=id`) overlays any view.

### 1. Countries & visa reference (home)
- **Layout:** the view is a fixed-height flex column (`100vh`, `overflow:hidden`, pad `24×34×26`):
  header on top, then a **two-pane row** (`display:flex; gap:18px; flex:1; min-height:0`) — the
  **globe panel** left (`flex:1.35; min-width:0; min-height:420px`) and the **side panel** right (see
  below). The globe is always visible; only the side panel changes with selection.
- **Header:** H1 "Country & visa reference" (24px/700/-0.02em, `#e3fdf6`); sub (13.5px, `#7fa8a3`,
  max-width 820px): "As-known Jan 2026 — thresholds and timelines change. Tap a beacon to inspect
  that market and its live postings in the panel beside the globe."
- **Globe panel** (always visible, left pane; radius 18px, overflow hidden, `flex:1.35`,
  min-height 420px; dark radial bg `radial-gradient(125% 105% at 50% 4%, #0c3138, #06181f 52%,
  #04111a)`; border `#10424a`; shadow `0 24px 60px rgba(4,18,26,0.35), inset 0 0 90px
  rgba(45,212,191,0.05)`):
  - Full-bleed `<canvas>` renders the holographic 3D dot-globe (see **Globe rendering**).
  - **Top overlay** (pointer-events:none): left = teal globe icon + "Target geography"
    (14.5px/700, `#e3fdf6`) + hint "drag to rotate · tap a beacon" (12px mono, `#5f9a95`); right =
    legend "Primary target" (dot `#5eead4`, teal glow) / "Nice-to-have" (dot `#93a7ad`), 12px `#9fc7c2`.
  - **Bottom-left caption:** "live beacon field · 11 markets" (11px, uppercase, 0.06em mono, `#3f7a76`).
  - **Bottom-right Source-health widget** (glass: bg `rgba(4,17,26,0.72)`, `backdrop-filter:blur(6px)`,
    border `#10424a`, radius 12px, min-width 186px): "SOURCE HEALTH" label + "poll 07:04" (mono),
    then three dot rows — "44 OK" (`#34d399`), "1 degraded" (`#fbbf24`), "2 quarantined" (`#f87171`),
    12px `#9fc7c2` with mono counts `#c4ebe4`. A **static summary widget** (wire to live counts later).
- **Side panel** (right pane; `<aside>`, `flex:1; min-width:372px; max-width:512px; overflow-y:auto`,
  bg `#071a22`, border `#123842`, radius 18px, its own scroll so the globe never leaves the viewport).
  It shows the **all-markets card stack** (no selection) OR the **jobs pane** (a country selected).

- **All-markets card stack** (no selection; pad `16×20×20`): a small uppercase caption "N markets ·
  tap a beacon or a card" (`#5f8f8a`) then a **vertical stack** of country cards (`flex-direction:
  column; gap:10px` — not a grid; the panel is narrow). Card: bg `#0a2028`, border `#123842`, radius
  12px, pad `14×16`, cursor pointer, hover bg `#0d2a33` / border `#1a4650`. Name (15px/700, `#e3fdf6`)
  + tier badge ("Primary" teal `rgba(94,234,212,0.15)`/`#5eead4`, "Nice-to-have" grey
  `rgba(148,180,186,0.12)`/`#9fc7c2`). **Two** labelled blocks — Work visa / PR path (label 10.5px
  uppercase `#5f8f8a`, value 12px `#c4ebe4`); **Citizenship is omitted here** — it appears in the
  reference legend once a market is selected (§2). Footer (top border `#123842`): registry note
  (`#7fa8a3`) + "✓ {verified}" (mono, `#4f7873`). Clicking a card selects that country (globe focus +
  arc + jobs pane replaces the stack). **Sweden has no sponsor registry** (scheme discontinued Dec
  2023) — surface exactly as written, do not invent one.

### 2. Jobs pane (in the side panel, beside the globe; `?focus=CODE`)
Rendered inside the §1 side panel, so its sections carry their own 20px horizontal inset; only the
header is sticky.
- **Sticky header** (`position:sticky; top:0; z-index:6`, bg `#071a22`, pad `17×20×13`, border-bottom
  `#123842`): an "← All markets" back button (chevron + text, 12.5px/600, `#5eead4`, no bg) that
  clears the selection; then H2 = "Jobs · {Country}" (20px/700) when exactly one country is filtered,
  else "Jobs"; then a result sub-line (12.5px `#7fa8a3`, e.g. "New · N postings · sorted by sponsor
  tier").
- **Relocation-reference legend** (shown for the selected market; margin `15×20×0`, bg
  `rgba(94,234,212,0.06)`, border `#14514c`, radius 13px, pad `15×17`): title "{Country} — relocation
  reference" (14px/700) + tier badge; then **Work visa / PR path / Citizenship** blocks (labels teal
  `#5eb5ab` 10px uppercase, values `#d6f5ee` 12.5px); footer "verified {date}" (mono `#5eb5ab`). This
  is where Citizenship lives (it's off the compact card).
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
  - **Chip row:** "CATEGORY" label + 7 category pills (iOS, Backend, AI/ML, Android, Flutter,
    Fullstack, Frontend) · divider · "LEVEL" + 3 pills (Senior, Staff, Lead). Pill styles as above.
- **Job list** (pad `4×20×22`; a **stack of compact cards**, `flex-direction:column; gap:10px` — not
  a wide table). Card: bg `#0a2028`, border `#123842`, radius 12px, pad `13×15`, cursor pointer, hover
  bg `#0d2a33` / border `#1a4650`, greyed (`opacity:0.55`) when hidden:
  - **Top row:** left = title (14px/600/-0.01em, `#e3fdf6`) over company (12px/500, `#9fc7c2`) — the
    title block is the drawer-open trigger; right (flex-shrink:0) = Star + Hide (Restore when hidden)
    icon buttons (28px, hover `#0f333c`, star fills teal `#5eead4`).
  - **Meta row** (margin-top 11px, wraps): sponsorship tier chip (6px dot + label) + city (11.5px
    `#c4ebe4`) + level (11px mono uppercase `#5f8f8a`) + posted age (11.5px `#5f8f8a`, pushed right).
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
- **Navigation:** `?view=` (countries default / searches / settings). Within Countries, `?focus=CODE`
  decides the side panel's card stack (unset) vs jobs pane (set). Selecting a country sets `focus=CODE`, seeds
  `country=CODE`, and `status=all`. Clearing (back button, ocean tap, Globe nav) removes them. All
  filter/view/drawer state lives in URL search params (shareable, bookmarkable, Back-button undo).
- **Globe:** drag rotates (yaw += dx·0.45, pitch clamped ±82°; a >3px drag is a rotate, not a click).
  Pointer-up without a drag: on a pin (≤15px) selects that country; on empty ocean clears the selection.
  With a selection, the globe eases to the Jakarta↔country great-circle midpoint; idle it slow-spins.
- **Filtering (jobs pane):** keyword (title/company/description/categories), country[], category[],
  level[], sponsor-tier[] (opt-in). AND across dimensions, OR within one. Re-fetches live.
- **Sorting:** Sponsor tier → `sort_rank DESC, posted_at DESC` (yes=3, registry=2, unknown=1, no=0);
  Date → newest first. **`explicit_no` shows last, never hidden by default.**
- **Job triage:** row click opens the drawer (a `new` job becomes `seen`); Star toggles starred/seen;
  Hide → hidden (excluded from all views but Hidden); Restore → seen.
- **Sponsorship is a soft signal:** tier drives sort_rank + default order; the tier filter is opt-in,
  never pre-selected.

## Globe rendering
Procedural holographic 3D dot-globe on a `<canvas>` 2D context, recomputed every frame
(`requestAnimationFrame` while Countries is mounted). Real continent outlines (`LAND`) with inland
seas (`SEA`) punched out build a 1024px equirectangular mask once; a 2° land-point cloud is sampled
from it. Each frame draws (back→front): teal atmosphere glow; shaded globe face; graticule (30°/20°,
brighter on the front hemisphere); the land dot cloud (1.35px, `rgba(94,234,212, 0.28→0.92)` by
depth, back hemisphere culled); a bright rim; the **beacon arc** (Jakarta → selected country: 90-seg
great circle bowed out `1+0.22·sin(πf)`, bright on the front / faint on the back, a `#eafffb`
travelling pulse, amber `#fcd34d` Jakarta origin marker + label); then **pins** (front: glowing dot
`#5eead4` primary / `#9fb6bb` nice-to-have + pulse ring + label chip; back: faint ghost). Screen
positions of front pins are cached for 15px hit-testing. See `frontend/src/countries/globeGeo.ts`
(data + math, ported verbatim) and `Globe.tsx` (canvas rAF engine, jsdom-guarded; sr-only pin
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
  Jakarta origin `#fcd34d`; arc pulse `#eafffb`.
- **Sponsorship tiers (bg / fg / dot):** yes `rgba(52,211,153,0.14)`/`#5fe3a3`/`#34d399`; registry
  `rgba(96,165,250,0.14)`/`#7cc0fb`/`#60a5fa`; unknown `rgba(148,180,186,0.12)`/`#9fc7c2`/`#8296a0`;
  no `rgba(248,113,113,0.14)`/`#f7a6a2`/`#f87171`.
- **Status pills (bg / fg):** new `rgba(94,234,212,0.16)`/`#5eead4` · seen `rgba(148,180,186,0.12)`/
  `#9fc7c2` · starred `rgba(94,234,212,0.16)`/`#5eead4` · hidden `rgba(248,113,113,0.14)`/`#f7a6a2`.
- **Source-health dots:** OK `#34d399`, degraded `#fbbf24`, quarantined `#f87171`.

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
