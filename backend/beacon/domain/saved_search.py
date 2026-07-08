"""A saved search: the filter criteria a user wants to be alerted about.

`SearchFilters` is the matchable subset of the Jobs filter bar (no pagination,
sort or status — those are view concerns). It serializes to the `filters_json`
column and back with no loss, so the round-trip is the contract."""

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """The criteria of a saved search. Tuples (not lists) keep the value hashable and
    immutable; every dimension defaults empty so an unconstrained search matches all."""

    q: str | None = None
    countries: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    tiers: tuple[str, ...] = ()


def filters_to_json(filters: SearchFilters) -> str:
    """Serialize to the compact JSON stored in saved_searches.filters_json."""
    return json.dumps(asdict(filters), separators=(",", ":"))


def filters_from_json(raw: str) -> SearchFilters:
    """Rebuild filters from stored JSON. Lists become tuples so equality with a
    freshly-constructed SearchFilters holds (the round-trip invariant)."""
    data = json.loads(raw)
    return SearchFilters(
        q=data.get("q"),
        countries=tuple(data.get("countries", ())),
        categories=tuple(data.get("categories", ())),
        levels=tuple(data.get("levels", ())),
        tiers=tuple(data.get("tiers", ())),
    )


def match_reason(
    filters: SearchFilters,
    *,
    categories: Sequence[str],
    country: str | None,
    level: str | None,
    tier: str,
) -> str:
    """Human note of *which* of the search's criteria this job satisfied, in a fixed
    dimension order (category · country · level · tier). Only dimensions the search
    actually constrained appear, showing the job's own matched value(s) — e.g.
    'ios · SE · registry_inferred'. An unconstrained search reports 'all'."""
    parts: list[str] = []
    parts.extend(c for c in filters.categories if c in categories)
    if filters.countries and country is not None:
        parts.append(country)
    if filters.levels and level is not None:
        parts.append(level)
    if filters.tiers:
        parts.append(tier)
    return " · ".join(parts) if parts else "all"
