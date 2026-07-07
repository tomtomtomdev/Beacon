"""Manual registry-match spot check — the CLAUDE.md data-correctness gate.

Company-name normalization is the highest-risk code in the repo. Run this after ANY
change to the normalizer/matcher and eyeball the diff before committing:

    cd backend && uv run python scripts/spot_check_registry.py

It matches every seed company against the in-repo registry fixtures (the only snapshots
committed) and prints flags / confidence / evidence per company, so a regression that
newly matches a trap or drops a real subsidiary is visible at a glance.
"""

from pathlib import Path

from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.adapters.seeds import parse_seed_csv
from beacon.domain.matching import match_company
from beacon.domain.registry import Registry, RegistryCompany

_BACKEND = Path(__file__).parents[1]
_FIXTURES = _BACKEND / "tests" / "fixtures" / "registries"
_SEEDS = _BACKEND.parent / "seeds" / "companies.csv"


def main() -> int:
    seeds = parse_seed_csv(_SEEDS.read_text())
    entries: dict[Registry, list[RegistryCompany]] = {
        Registry.UK: UKSponsorRegistry(_FIXTURES / "uk_sponsors_fixture.csv").fetch(),
        Registry.NL: INDRegistry(_FIXTURES / "ind_sponsors_fixture.csv").fetch(),
        Registry.US: H1BLCARegistry(_FIXTURES / "h1b_lca_fixture.csv").fetch(),
    }

    print(f"{'Company':22} {'Flags':13} {'Conf':>4}  Evidence")
    print("-" * 78)
    matched = 0
    for company in seeds:
        result = match_company(company.name, entries)
        if result.flags:
            matched += 1
        flags = "|".join(r.name or "" for r in Registry if result.flags & r) or "—"
        confidence = f"{result.confidence:.2f}" if result.confidence is not None else "  —"
        print(f"{company.name:22} {flags:13} {confidence:>4}  {result.evidence or ''}")
    print("-" * 78)
    print(f"{matched}/{len(seeds)} seed companies matched at least one registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
