# VERIFY-COUNTRIES.md — how to fill the §4 country data

The SPEC §4 table is knowledge-as-of **Jan 2026**. Before relying on any row
for a real decision, verify it against the official source and stamp the row.
This is a browse-and-record task, ~10 minutes per country, no code.

## The procedure (per country)

1. Open the official source URL below (always the government body, never a
   relocation blog or law-firm page — those lag and editorialize).
2. Check the four facts against the SPEC row: work-visa salary/points
   threshold, PR timeline, citizenship timeline, dual-citizenship stance.
3. Correct the SPEC §4 row if reality moved.
4. Stamp the row: `verified_at = <today>`, `source_url = <the page you read>`.
5. If a rule is *mid-reform* (bill proposed but not law), record both the
   current rule and the pending change with its expected date — a pending
   rule is a fact worth tracking, not a footnote.

Later this becomes editing `seeds/countries.csv` before the slice-10
migration loads it; until then, edit SPEC §4 directly.

## Official sources + what specifically to check

| Country | Source | Verify specifically |
|---|---|---|
| 🇸🇪 Sweden | migrationsverket.se (work permits; citizenship pages) + regeringen.se for bills | **Highest priority.** (a) Citizenship reform: did the 8-year + tests requirement become law? Effective date? Transition rules for pending applications? (b) Work-permit salary threshold: still ~80% of median, or raised to 100%? Current SEK figure. |
| 🇳🇱 Netherlands | ind.nl — HSM salary criteria page + the recognised-sponsors register you already have | 2026 HSM monthly thresholds (they index annually every Jan; confirm the under-30 reduced rate still exists). |
| 🇮🇪 Ireland | enterprise.gov.ie (CSEP) + irishimmigration.ie (Stamp 4, citizenship) | CSEP salary floor (was being raised in steps — confirm current €), Stamp 4 still at 2 years, naturalisation still 5 years with dual allowed. |
| 🇯🇵 Japan | moj.go.jp / isa.go.jp — HSP points table + J-Skip pages | Points table unchanged (degree/salary/age bands), 70→3yr / 80→1yr PR fast-track intact, and whether J-Skip (high-salary shortcut) applies to you. |
| 🇸🇬 Singapore | mom.gov.sg — EP qualifying salary + COMPASS | EP salary floor (rises with age; check the figure for yours) and COMPASS points — score your actual profile against the four foundational criteria. |
| 🇦🇺 Australia | immi.homeaffairs.gov.au — Skills in Demand visa | Current TSMIT/core-skills threshold (indexed each July — a new figure takes effect *this month*), specialist tier figure, 186 pathway timing. |
| 🇨🇦 Canada | canada.ca — Express Entry rounds page + CRS tool | Recent draw pattern: are there category-based tech/STEM draws, and what CRS scores are cutting off? Compute your actual CRS. Citizenship still 3/5 years presence. |
| 🇺🇸 US | uscis.gov (H-1B cap season) + travel.state.gov visa bulletin | H-1B registration timing/fee changes; visa bulletin confirms no Indonesia EB backlog. |
| 🇳🇴 Norway | udi.no — skilled worker + permanent residence | Salary requirement figure, PR at 3 years, citizenship residence requirement (was in flux 6–8yr). |
| 🇩🇰 Denmark | nyidanmark.dk — Pay Limit Scheme | Current DKK threshold (indexed annually) and whether the lower supplementary pay-limit track survived. |
| 🇨🇭 Switzerland | sem.admin.ch — third-country quotas | Annual non-EU quota numbers (set each Nov/Dec) — confirms how narrow the door is. |
| 🇮🇩 Indonesia (constraint row) | — | Dual-citizenship law unchanged (periodic diaspora-bill noise; verify nothing passed). |

## Order of attack

Sweden → Canada → Australia (rules literally changing in 2025–26) → Ireland →
Japan → the rest. The first three can materially change the strategy ranking;
the others are threshold-figure refreshes.

## Recording pending reforms

Add a fifth line to affected SPEC rows, e.g.:

> SE citizenship: 5yr (current) — **pending: 8yr + language/civics test, bill
> status as of 2026-07-XX: <status>, expected effective <date>** —
> transition rule: <applications filed before X assessed under old rules? Y/N>

The transition rule is the detail that actually matters for planning — verify
it explicitly, don't infer it.
