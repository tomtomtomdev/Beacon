# DESIGN.md — Beacon UI Handoff

> Canonical UI spec. Reflects the **dark holographic** design handoff
> (`~/Downloads/Beacon.zip` → `Beacon.dc.html`, 2026-07-13), which **supersedes** the earlier
> light "Nordic Slate & Teal" theme documented in prior versions of this file. The `.dc.html`
> prototype + the delivered screenshots are ground truth; where this doc and the top-level SPEC.md
> disagree on product behavior, SPEC.md wins. The prototype `.dc.html` and `support.js` are
> references only, not shipping code.
>
> Implemented on branch `feat/dark-globe-redesign` (see PROGRESS.md, Decisions 2026-07-13).

---

# Handoff: Beacon — personal tech-job scanner with visa-sponsorship awareness

## Overview
Beacon is a single-user, self-hosted web app that polls ATS/job-board APIs, classifies postings
(category, level, sponsorship tier), and surfaces them filtered by **visa-sponsorship signal** and
**target relocation country**. The **home page is a Countries & visa reference** dominated by an
interactive **3D holographic dot-globe**. Selecting a country (tap a globe beacon pin or a country
card) does not navigate away — it rotates the globe to frame a **beacon arc from Jakarta to the
country**, and reveals a **Jobs list pane in-place below the globe**, filtered to that country.
Clearing the selection returns to the country-card grid. A **Saved searches** page and a slide-in
**Job-detail drawer** round out the app. There is **no standalone Jobs route and no Companies tab**
— source health folds into a widget on the globe; Jobs is a pane inside Countries.

## Fidelity
**High-fidelity, dark holographic.** Match the exact hex/px/radius values in the token tables below.
Body background `#04121a`; teal accent `#5eead4`. Fonts: **Geist** (UI) + **Geist Mono**
(codes/slugs/timestamps). `-webkit-font-smoothing: antialiased`.

---

## Global Layout
Full-viewport flex: a fixed **88px icon-rail** (left) + a scrolling **main** area (`flex:1`). A
**job-detail drawer** (560px, max 100%) slides in from the right over a dim scrim, above everything.

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
- **Header:** H1 "Country & visa reference" (24px/700/-0.02em, `#e3fdf6`); sub (13.5px, `#7fa8a3`,
  max-width 760px): "As-known Jan 2026 — thresholds and timelines change. Each row carries a
  verified date for manual re-check. PR and citizenship are distinguished (Indonesia bars adult
  dual citizenship)."
- **Globe panel** (always visible; radius 18px, overflow hidden, height 66vh / min 480px,
  margin-bottom 22px; dark radial bg `radial-gradient(125% 105% at 50% 4%, #0c3138, #06181f 52%,
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
- Below the globe: the **country-card grid** (no selection) OR the **jobs pane** (a country selected).

- **Country cards** grid (`repeat(auto-fill, minmax(340px,1fr))`, gap 14px). Card: bg `#0a2028`,
  border `#123842`, radius 14px, pad 20×22, cursor pointer. Name (17px/700, `#e3fdf6`) + tier badge
  ("Primary" teal `rgba(94,234,212,0.15)`/`#5eead4`, "Nice-to-have" grey `rgba(148,180,186,0.12)`/`#9fc7c2`).
  Three labelled blocks (Work visa / PR path / Citizenship; label 10.5px uppercase `#5f8f8a`, value
  13px `#c4ebe4`). Footer (top border `#123842`): registry note (`#7fa8a3`) + "✓ {verified}" (mono,
  `#4f7873`). Clicking a card selects that country (globe focus + arc + jobs pane). Selected card:
  1.5px `#5eead4` border + `0 0 0 3px rgba(94,234,212,0.18)` ring. **Sweden has no sponsor registry**
  (scheme discontinued Dec 2023) — surface exactly as written, do not invent one.

### 2. Jobs pane (inside Countries, below the globe; `?focus=CODE`)
- **Header:** an "← All countries" back button (chevron + text, 12.5px/600, `#5eead4`, no bg) that
  clears the selection; then H1 = "Jobs · {Country}" (24px/700) when exactly one country is filtered,
  else "Jobs"; then a result sub-line ("New · N postings · sorted by sponsor tier"). Right: the
  4-dot tier legend — Sponsors `#34d399`, Registry `#60a5fa`, Unknown `#8296a0`, No `#f87171`.
- **Filter bar** (sticky, top:0, z-index 5, gradient fade `linear-gradient(#04121a 78%, transparent)`):
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
- **Jobs table** (card bg `#0a2028`, border `#123842`, radius 14px). Grid columns
  `minmax(0,2.4fr) 1.15fr 1.35fr 0.72fr 1fr 100px`, gap 16px. Header row bg `#0c2831`, uppercase
  10.5px `#5f8f8a`. Row (pad 16×24, border-bottom `#0f2c34`, hover `#0d2a33`): **Role** = 7px teal
  "new" dot (`new` status) + title (15px/600, `#e3fdf6`, ellipsis) over company (`#9fc7c2`) + "{ats}·
  {slug}" (11px mono, `#4f7873`); **Location** city/country; **Category** grey chips (`#0f333c`/`#9fc7c2`);
  **Level** mono uppercase; **Sponsor · Posted** = tier chip + posted age; **Actions** = Star / Hide
  (Restore when hidden) icon buttons (27px, hover `#0f333c`, star fills teal). Row click opens the
  drawer; action clicks `stopPropagation`. Per-view empty states (New → "You're all caught up", etc.).

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
  decides card grid (unset) vs jobs pane (set). Selecting a country sets `focus=CODE`, seeds
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
40px→0 + fade, 0.22s), `bk-pulse` (scale 0.55→1.9 + fade). Page padding 26×34.

All tokens live in `frontend/src/tokens.css` as CSS custom properties — do not invent colors.

## Assets
No raster assets. Icons via Lucide (Globe, Bookmark, Settings, Search, ChevronDown/Left, Star,
Eye/EyeOff, Check, ExternalLink, Plus, X) matching the prototype's stroke SVGs; the Beacon brand
glyph is an inline SVG. The globe is procedurally generated on a canvas — no map image. Fonts:
Geist + Geist Mono (Google Fonts).

## Files (prototype references, not shipping code)
`~/Downloads/Beacon.zip` → `design_handoff_beacon/`: `Beacon.dc.html` (the hifi dark prototype:
markup + `class Component` logic with seed data, `LAND`/`SEA`/`PINS`, the canvas globe engine, and
`renderVals()` filter/sort derivations), `README.md` (this design's handoff prose), `support.js`
(the `.dc.html` runtime — ignore), `SPEC.md` (product/architecture context).
