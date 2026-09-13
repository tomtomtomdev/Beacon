from pathlib import Path

from beacon.adapters.seeds import parse_seed_csv

SAMPLE = """name,ats_type,ats_slug,country_hq,priority
Tines,greenhouse,tines,IE,2
Grab,smartrecruiters,Grab,SG,1
"""

REAL_SEED_FILE = Path(__file__).parents[3] / "seeds" / "companies.csv"


def test_parse_seed_csv_maps_pinned_schema_to_companies() -> None:
    companies = parse_seed_csv(SAMPLE)

    assert [(c.name, c.ats_type, c.ats_slug, c.country_hq, c.priority) for c in companies] == [
        ("Tines", "greenhouse", "tines", "IE", 2),
        ("Grab", "smartrecruiters", "Grab", "SG", 1),
    ]
    assert all(c.id is None for c in companies)


def test_home_market_is_seeded_like_any_other_row() -> None:
    """SPEC §5.1: an Indonesian employer is a seed row with country_hq=ID and nothing else
    special — not_required is derived from the JOB's country at classification time, so the
    home market needs no adapter, use-case or schema work to reach the DB.

    One row, and that is a finding rather than a starting point: 60+ slug probes across
    greenhouse/lever/ashby/smartrecruiters/workable/recruitee on 2026-09-13 found exactly
    one genuine Indonesian board. See PROGRESS Decisions 2026-09-13 (id-seeds)."""
    home = [c for c in parse_seed_csv(REAL_SEED_FILE.read_text()) if c.country_hq == "ID"]

    assert [(c.name, c.ats_type, c.ats_slug) for c in home] == [("Xendit", "greenhouse", "xendit")]


def test_delivered_seed_file_parses_completely() -> None:
    text = REAL_SEED_FILE.read_text()
    data_lines = [line for line in text.splitlines()[1:] if line.strip()]

    companies = parse_seed_csv(text)

    # Every data row becomes a Company — which is what "completely" means here. Pinning the
    # count to a literal instead would make every legitimate seed addition look like a
    # regression, and would still not prove the file parsed whole.
    assert len(companies) == len(data_lines)
    assert {c.ats_type for c in companies} <= {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workable",
        "workday",
        "teamtailor",
        "recruitee",
        "rippling",
        "gem",
        "bendingspoons",
    }
    assert all(c.priority in (1, 2, 3) for c in companies)
