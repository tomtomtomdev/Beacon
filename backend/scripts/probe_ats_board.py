"""Manual candidate-board probe — the evidence a seed row needs (slice 15b).

Slices 13 and 14 probed every candidate live before writing a line of code, by hand, and
those probes are what killed The Muse and Breezy HR. This is that discipline as one command:
it builds the *real* adapter through the real factory, runs it through the real classifier,
and reports what Beacon would actually ingest — which is the thing a curl of the board
cannot answer. Live network by design (manual acceptance only, never the suite):

    cd backend && uv run python scripts/probe_ats_board.py
    cd backend && uv run python scripts/probe_ats_board.py --candidate "Mercari:greenhouse:mercari"
    cd backend && uv run python scripts/probe_ats_board.py --focus backend --titles 12

With no --candidate it probes every row of `seeds/ios_candidates.csv`, whose slugs are
unverified guesses by construction — that is what this script is for. A candidate that
passes (real postings, real ad text) prints a paste-ready `seeds/companies.csv` row; nothing
is written and nothing is persisted, so a probe can never seed a company by itself.

Ranking note (slice 13/14): judge a candidate by focus-role *density*, not posting count.
Rippling's 376 postings held zero mobile roles, and nvidia's 2,000 cost 33 min of the polite
budget per poll.
"""

import argparse
import asyncio
from pathlib import Path

import httpx

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.seeds import parse_seed_csv
from beacon.adapters.sources.factory import make_source_factory
from beacon.application.errors import SourceUnavailable
from beacon.application.probe import CandidateProbe, probe_candidate
from beacon.domain.classification import Category
from beacon.domain.company import Company

_CANDIDATES = Path(__file__).parents[2] / "seeds" / "ios_candidates.csv"


def _candidate(spec: str) -> Company:
    """`Name:ats_type:slug[:country[:priority]]` — a slug may itself contain colons
    (Workday's is `tenant/wdN/site`), so the split is bounded from the left."""
    parts = spec.split(":")
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(f"expected Name:ats_type:slug, got {spec!r}")
    name, ats_type, slug = parts[0], parts[1], parts[2]
    country = parts[3] if len(parts) > 3 else "??"
    priority = int(parts[4]) if len(parts) > 4 else 3
    return Company(
        name=name, ats_type=ats_type, ats_slug=slug, country_hq=country, priority=priority
    )


def _report(probe: CandidateProbe, focus: Category, titles: int) -> None:
    places = ", ".join(
        f"{country} {count}"
        for country, count in sorted(probe.countries.items(), key=lambda kv: -kv[1])[:6]
    )
    print(
        f"  fetched={probe.fetched} normalized={probe.normalized} with_text={probe.with_text}"
        f" errors={probe.errors} {focus.value}={probe.categories.get(focus, 0)}"
        f" unclassified={probe.unclassified}"
    )
    print(f"  countries: {places or '—'}")
    for title in probe.focus_titles[:titles]:
        print(f"    · {title}")
    if len(probe.focus_titles) > titles:
        print(f"    … and {len(probe.focus_titles) - titles} more")


def _verdict(probe: CandidateProbe, focus: Category) -> str:
    """A board earns a seed row only by returning real postings *with ad text*: no text means
    no content_hash, no sponsorship tier and no resume score, which is Breezy HR's failure."""
    if probe.normalized == 0:
        return "EMPTY — the board answered, with nothing in it"
    if probe.with_text == 0:
        return "NO AD TEXT — rows only; unusable for sponsorship or fit (cf. Breezy HR)"
    if probe.categories.get(focus, 0) == 0:
        return f"NO {focus.value.upper()} — real board, but not this role family"
    return "PASS"


async def _run(candidates: list[Company], focus: Category, titles: int) -> int:
    classifier = HeuristicClassifier()
    passed: list[Company] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        source_for = make_source_factory(PoliteClient(client))
        for company in candidates:
            print(f"\n{company.name}  [{company.ats_type} {company.ats_slug}]")
            try:
                probe = await probe_candidate(company, source_for, classifier, focus=focus)
            except SourceUnavailable as exc:
                # A 404 slug or a dead host IS the answer here — report it and keep going.
                print(f"  UNREACHABLE — {exc.kind.value}")
                continue
            except Exception as exc:  # noqa: BLE001 — a probe run must survive one bad board
                print(f"  FAILED — {type(exc).__name__}: {exc}")
                continue
            if probe is None:
                print(f"  DORMANT — no adapter for ats_type={company.ats_type!r}")
                continue
            _report(probe, focus, titles)
            verdict = _verdict(probe, focus)
            print(f"  → {verdict}")
            if verdict == "PASS":
                passed.append(company)

    print(f"\n{'=' * 78}\nprobed={len(candidates)} passed={len(passed)}")
    if passed:
        print("paste-ready rows for seeds/companies.csv (check country_hq and priority):")
        for company in passed:
            print(
                f"  {company.name},{company.ats_type},{company.ats_slug},"
                f"{company.country_hq},{company.priority}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe a candidate ATS board for what Beacon would actually ingest."
    )
    parser.add_argument(
        "--candidate",
        action="append",
        type=_candidate,
        metavar="Name:ats_type:slug[:country[:priority]]",
        help="probe this candidate instead of the candidates file (repeatable)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=_CANDIDATES,
        help=f"candidate CSV in seeds/companies.csv's schema (default {_CANDIDATES.name})",
    )
    parser.add_argument(
        "--focus",
        default=Category.IOS.value,
        choices=[category.value for category in Category],
        help="the role family being hunted (default ios)",
    )
    parser.add_argument(
        "--titles", type=int, default=8, help="focus-role titles to print per board (default 8)"
    )
    args = parser.parse_args(argv)

    candidates: list[Company] = args.candidate or parse_seed_csv(args.file.read_text())
    if not candidates:
        print(f"no candidates in {args.file}")
        return 1
    return asyncio.run(_run(candidates, Category(args.focus), args.titles))


if __name__ == "__main__":
    raise SystemExit(main())
