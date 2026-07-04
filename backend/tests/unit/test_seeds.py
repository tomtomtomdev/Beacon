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


def test_delivered_seed_file_parses_completely() -> None:
    companies = parse_seed_csv(REAL_SEED_FILE.read_text())

    assert len(companies) == 53
    assert {c.ats_type for c in companies} <= {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workable",
        "workday",
        "gem",
        "bendingspoons",
    }
    assert all(c.priority in (1, 2, 3) for c in companies)
