import pytest

from beacon.domain.hn import HnPosting, parse_hn_posting


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Anthropic | San Francisco, CA | Full-time | Onsite",
            HnPosting(company="Anthropic", location="San Francisco, CA", role=None),
        ),
        (
            "Stripe | Remote (US) | Senior Backend Engineer",
            HnPosting(company="Stripe", location="Remote (US)", role="Senior Backend Engineer"),
        ),
        (
            "Linear | Backend Engineer | Berlin, Germany | full-time",
            HnPosting(company="Linear", location="Berlin, Germany", role="Backend Engineer"),
        ),
        (
            "Acme Corp | REMOTE | Go, Rust | full-time",
            HnPosting(company="Acme Corp", location="REMOTE", role=None),
        ),
        (
            # HN ships HTML: the header is the first paragraph, body follows a <p>.
            "Figma | New York, NY | Product Designer<p>We are hiring designers to&#x2F;"
            "build the future.<p>Apply: https://figma.com/careers",
            HnPosting(company="Figma", location="New York, NY", role="Product Designer"),
        ),
        (
            # Leading blank lines are skipped; only the first real line is the header.
            "\n\nDatadog | Paris, France | Site Reliability Engineer\nmore text",
            HnPosting(
                company="Datadog", location="Paris, France", role="Site Reliability Engineer"
            ),
        ),
    ],
    ids=[
        "no-role-in-header",
        "role-last",
        "role-middle",
        "remote-only",
        "html-first-para",
        "leading-blank",
    ],
)
def test_parse_hn_posting_extracts_header_fields(text: str, expected: HnPosting) -> None:
    assert parse_hn_posting(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "Just a normal reply with no pipes", "Company only |", "\n\n"],
    ids=["empty", "whitespace", "no-pipe", "single-field", "blank-lines"],
)
def test_parse_hn_posting_rejects_non_postings(text: str) -> None:
    assert parse_hn_posting(text) is None


def test_role_falls_back_to_none_when_no_role_keyword() -> None:
    # A header with only company + location (roles live in the body) has no parseable role.
    posting = parse_hn_posting("Notion | London, United Kingdom | Hybrid")

    assert posting is not None
    assert posting.role is None
    assert posting.company == "Notion"
    assert posting.location == "London, United Kingdom"


@pytest.mark.parametrize(
    ("header", "company"),
    [
        # Trailing YC-batch / URL annotations are stripped so one employer isn't split
        # into several shadow companies across months.
        ("PermitFlow (YC W22) | New York, NY | Staff Engineer", "PermitFlow"),
        ("String ( https://usestring.ai/ ) | ONSITE | Founding Engineer", "String"),
        ("Hive (S14) (www.hive.co) | Remote | Product Engineer", "Hive"),
        ("Acme (Europe) Ltd | Berlin, Germany | Engineer", "Acme (Europe) Ltd"),  # not trailing
        ("(Stealth) | SF | Engineer", "(Stealth)"),  # all-parenthetical → kept intact
    ],
    ids=["yc-batch", "url", "double-trailing", "mid-paren-kept", "only-paren-kept"],
)
def test_company_strips_trailing_parentheticals(header: str, company: str) -> None:
    posting = parse_hn_posting(header)

    assert posting is not None
    assert posting.company == company
