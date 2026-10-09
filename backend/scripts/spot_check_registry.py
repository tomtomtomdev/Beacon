"""Manual registry-match spot check — the CLAUDE.md data-correctness gate.

Company-name normalization is the highest-risk code in the repo. Run this after ANY
change to the normalizer/matcher and eyeball the diff before committing:

    cd backend && uv run python scripts/spot_check_registry.py                # fixtures
    cd backend && uv run python scripts/spot_check_registry.py --snapshots    # real files
    ... --only-stripped          # just the confidence < 1.0 matches: the review set
    ... --baseline run.txt       # first run writes it; later runs print the diff
    ... --from-db                # every active company in beacon.db, not just the seeds

One line per (seed, registry) match: seed | registry | entry | confidence | dropped tokens |
evidence. "Dropped" is what stripping removed to reach equality. A geography drop ("usa") is
the safe kind; a structural one ("technologies") is the kind that matched Cohere to a
wireless company in slice 24, so read those lines.

The default reads the committed fixtures, which every checkout has. `--snapshots` reads the
real files under data/registries/ (via Settings, the same specs a refresh uses), which is the
only run that shows what the live matcher does.
"""

import argparse
import difflib
from pathlib import Path

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import connect
from beacon.adapters.registries.ca import CALMIARegistry
from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ie import IEPermitsRegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.perm import PERMRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.adapters.seeds import parse_seed_csv
from beacon.application.ports import RegistryIngester
from beacon.config import Settings
from beacon.domain.matching import dropped_tokens, registry_matches
from beacon.domain.registry import Registry, RegistryCompany
from beacon.refresh import available_ingesters

_BACKEND = Path(__file__).parents[1]
_FIXTURES = _BACKEND / "tests" / "fixtures" / "registries"


def _fixture_ingesters() -> list[RegistryIngester]:
    return [
        UKSponsorRegistry(_FIXTURES / "uk_sponsors_fixture.csv"),
        INDRegistry(_FIXTURES / "ind_sponsors_fixture.csv"),
        H1BLCARegistry(_FIXTURES / "h1b_lca_fixture.csv"),
        IEPermitsRegistry(_FIXTURES / "ie_permits_fixture.csv"),
        CALMIARegistry(_FIXTURES / "ca_lmia_fixture.csv"),
        PERMRegistry(_FIXTURES / "us_perm_fixture.csv"),
    ]


def report_lines(
    seed_names: list[str], entries: dict[Registry, list[RegistryCompany]], *, only_stripped: bool
) -> list[str]:
    lines: list[str] = []
    for seed in sorted(seed_names, key=str.casefold):
        for match in registry_matches(seed, entries):
            if only_stripped and match.confidence >= 1.0:
                continue
            dropped = ",".join(sorted(dropped_tokens(seed, match.entry) or ())) or "—"
            lines.append(
                f"{seed} | {match.registry.name} | {match.entry.name} | "
                f"{match.confidence:.2f} | {dropped} | {match.entry.evidence}"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshots", action="store_true", help="real data/registries files")
    parser.add_argument("--only-stripped", action="store_true", help="confidence < 1.0 only")
    parser.add_argument("--baseline", type=Path, help="write on first run, diff afterwards")
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="match every active company in the DB (what a refresh matches), not only seeds",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    ingesters = available_ingesters(settings) if args.snapshots else _fixture_ingesters()
    entries = {ingester.registry: ingester.fetch() for ingester in ingesters}
    if args.from_db:
        seeds = [c.name for c in SqliteCompanyRepo(connect(settings.db_path)).list_active()]
    else:
        seeds = [company.name for company in parse_seed_csv(settings.seeds_path.read_text())]
    lines = report_lines(seeds, entries, only_stripped=args.only_stripped)

    if args.baseline is None:
        print("\n".join(lines))
        matched = len({line.split(" | ")[0] for line in lines})
        print(
            f"-- {len(lines)} matches, {matched}/{len(seeds)} companies, registries: "
            f"{', '.join(r.name or '' for r in entries) or 'none present'}"
        )
        return 0
    if not args.baseline.exists():
        args.baseline.write_text("\n".join(lines) + "\n")
        print(f"baseline written: {args.baseline} ({len(lines)} lines)")
        return 0
    diff = list(
        difflib.unified_diff(
            args.baseline.read_text().splitlines(), lines, "baseline", "now", lineterm=""
        )
    )
    print("\n".join(diff) if diff else "no change against the baseline")
    return 1 if diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
