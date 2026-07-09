"""Country & visa reference data (SPEC §4) — pure product knowledge, not IO.

Figures are as-known Jan 2026; each row carries verified_at + source_url so the UI can
render a "verified as of" date and a human can re-verify (SPEC §4, CLAUDE.md data notes).
This is the source of truth; the countries table is a seeded projection of it. Editing a
figure = editing a row here (and bumping its verified_at), never inventing data downstream.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

# The table-wide knowledge date SPEC §4 states ("all figures as-known Jan 2026").
_AS_KNOWN = date(2026, 1, 15)


class PriorityTier(StrEnum):
    """Target-geography weighting from SPEC §3 — drives the Countries-view legend/pins."""

    PRIMARY = "primary"
    NICE_TO_HAVE = "nice_to_have"


@dataclass(frozen=True, slots=True)
class CountryReference:
    """One country's relocation reference: entry visa, PR path, citizenship endpoint, and
    the sponsor-registry data source (or a note when none exists). code is ISO-3166-1
    alpha-2 so it joins directly to a job's parsed country."""

    code: str
    name: str
    visa_summary: str
    pr_summary: str
    citizenship_summary: str
    registry_name: str
    priority_tier: PriorityTier
    verified_at: date
    source_url: str


# Summaries are lifted verbatim from SPEC §4; registry_name mirrors its "Registry data
# source" column (a note, not always a real register — Sweden's says why none exists).
COUNTRY_REFERENCE: tuple[CountryReference, ...] = (
    CountryReference(
        code="SG",
        name="Singapore",
        visa_summary="Employment Pass, ~S$5.6k/mo + COMPASS points",
        pr_summary="Discretionary; 5–10yr common, non-guaranteed",
        citizenship_summary="~2yr after PR; renounce required",
        registry_name="None public — company-level heuristics only",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://www.mom.gov.sg",
    ),
    CountryReference(
        code="JP",
        name="Japan",
        visa_summary="HSP points visa",
        pr_summary="70pts→3yr, 80pts→1yr — fastest PR anywhere",
        citizenship_summary="5yr; renounce; language",
        registry_name="None public",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://www.isa.go.jp",
    ),
    CountryReference(
        code="AU",
        name="Australia",
        visa_summary="Skills in Demand (~AU$76k floor; AU$141k specialist tier)",
        pr_summary="2–3yr via employer 186 or points 189",
        citizenship_summary="4yr residence",
        registry_name="None public (sponsor status inferable from posting text)",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://immi.homeaffairs.gov.au",
    ),
    CountryReference(
        code="NL",
        name="Netherlands",
        visa_summary="HSM kennismigrant, ~€5.3k/mo (30+)",
        pr_summary="5yr (+ EU long-term residence)",
        citizenship_summary="5yr; renounce (generally) + integration exams",
        registry_name="IND recognised sponsors list (public)",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://ind.nl",
    ),
    CountryReference(
        code="US",
        name="United States (SF Bay)",
        visa_summary="H-1B lottery (~25–35%) / L-1 transfer / O-1",
        pr_summary="GC ~1.5–3yr via PERM; no Indonesia-born backlog",
        citizenship_summary="5yr after green card",
        registry_name="H-1B LCA disclosure data (public, per-company)",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://www.uscis.gov",
    ),
    CountryReference(
        code="CA",
        name="Canada",
        visa_summary="Global Talent Stream (2-wk) or Express Entry PR direct",
        pr_summary="PR can be the entry itself",
        citizenship_summary="3yr — fastest passport",
        registry_name="None needed (open work-permit ecosystem)",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://www.canada.ca/en/services/immigration-citizenship.html",
    ),
    CountryReference(
        code="IE",
        name="Ireland",
        visa_summary="Critical Skills Employment Permit (~€38–44k floor)",
        pr_summary="Stamp 4 after 2yr",
        citizenship_summary="5yr; dual allowed → EU passport",
        registry_name="None public; big-tech presence is proxy",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=_AS_KNOWN,
        source_url="https://www.irishimmigration.ie",
    ),
    CountryReference(
        code="SE",
        name="Sweden",
        visa_summary="Work permit, ~80% median salary (raise proposed)",
        pr_summary="4yr",
        citizenship_summary="5yr → reform to 8yr + tests was in progress — likely law by 2026",
        registry_name="None — employer certification scheme discontinued Dec 2023",
        priority_tier=PriorityTier.NICE_TO_HAVE,
        verified_at=_AS_KNOWN,
        source_url="https://www.migrationsverket.se",
    ),
    CountryReference(
        code="NO",
        name="Norway",
        visa_summary="Skilled worker permit",
        pr_summary="3yr",
        citizenship_summary="6–8yr",
        registry_name="None public",
        priority_tier=PriorityTier.NICE_TO_HAVE,
        verified_at=_AS_KNOWN,
        source_url="https://www.udi.no",
    ),
    CountryReference(
        code="DK",
        name="Denmark",
        visa_summary="Pay Limit Scheme ~DKK 514k/yr",
        pr_summary="8yr (4 strict)",
        citizenship_summary="9yr",
        registry_name="Positive List employers (partial proxy)",
        priority_tier=PriorityTier.NICE_TO_HAVE,
        verified_at=_AS_KNOWN,
        source_url="https://www.nyidanmark.dk",
    ),
    CountryReference(
        code="CH",
        name="Switzerland",
        visa_summary="Non-EU quota; employer must justify",
        pr_summary="10yr non-EU",
        citizenship_summary="10yr + cantonal",
        registry_name="None useful",
        priority_tier=PriorityTier.NICE_TO_HAVE,
        verified_at=_AS_KNOWN,
        source_url="https://www.sem.admin.ch",
    ),
)
