"""Contact-email extraction (domain/contact.py) — pure, table-driven.

The corpus reality this exists for: 1,273 of 8,918 open postings carry an email address, but
~80% are legally-required accessibility contacts (accommodations@, reasonableaccommodations@)
and the rest are privacy/security boilerplate. Fewer than 40 are addresses a candidate could
actually write to. Surfacing the wrong one is worse than surfacing none — a candidate who mails
accommodations@ about a job reads as someone who did not read the posting.
"""

import pytest

from beacon.domain.contact import extract_contact_email


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Addresses worth surfacing.
        ("Send your CV to jobs@example.com and we will reply.", "jobs@example.com"),
        ("Questions? careers@acme.io", "careers@acme.io"),
        ("Reach out to recruiting@company.se for a chat.", "recruiting@company.se"),
        ("Email hiring@startup.dev with a link to your work.", "hiring@startup.dev"),
        ("Contact talent@firm.co.uk to apply.", "talent@firm.co.uk"),
        ("Write to anna.svensson@truecaller.com about the role.", "anna.svensson@truecaller.com"),
        # The boilerplate that dominates the corpus — never a hiring contact.
        ("If you need an accommodation, email accommodations@big.com.", None),
        ("Contact reasonableaccommodations@corp.com for assistance.", None),
        ("Requests to accomodations-ext@corp.com.", None),  # verbatim corpus typo
        ("For privacy questions contact privacy@corp.com.", None),
        ("Report issues to security@corp.com.", None),
        ("Legal notices: legal@corp.com.", None),
        ("Data requests: dpo@corp.com or gdpr@corp.com.", None),
        ("Do not reply to noreply@corp.com.", None),
        # A real address alongside boilerplate — the real one wins.
        (
            "Apply via jobs@acme.com. For accommodations, email accommodations@acme.com.",
            "jobs@acme.com",
        ),
        # Boilerplate first, real address second — order must not decide it.
        (
            "Accessibility requests: accommodations@acme.com. Otherwise write to careers@acme.com.",
            "careers@acme.com",
        ),
        # Nothing to find.
        ("Apply through the link below.", None),
        ("", None),
    ],
    ids=[
        "jobs-address",
        "careers-address",
        "recruiting-address",
        "hiring-address",
        "talent-address",
        "personal-name-address",
        "excludes-accommodations",
        "excludes-reasonableaccommodations",
        "excludes-misspelled-accomodations",
        "excludes-privacy",
        "excludes-security",
        "excludes-legal",
        "excludes-dpo-and-gdpr",
        "excludes-noreply",
        "real-address-beats-boilerplate",
        "order-does-not-decide",
        "no-address",
        "empty",
    ],
)
def test_extract_contact_email(text: str, expected: str | None) -> None:
    assert extract_contact_email(text) == expected


def test_extraction_is_case_insensitive_but_preserves_the_address() -> None:
    """Excluded local-parts are matched case-insensitively; the returned address keeps the
    casing the posting used, since it is shown to the user and may be copied verbatim."""
    assert extract_contact_email("Mail ACCOMMODATIONS@corp.com.") is None
    assert extract_contact_email("Mail Careers@Acme.com.") == "Careers@Acme.com"


def test_trailing_sentence_punctuation_is_not_part_of_the_address() -> None:
    assert extract_contact_email("Apply: jobs@acme.com.") == "jobs@acme.com"


@pytest.mark.parametrize(
    "text",
    [
        # Verbatim live-corpus text (2026-09-02). The local part is innocent in every one —
        # only the sentence around it reveals that the address is for accessibility requests.
        "Accommodation is available upon request at any point during our recruitment process. "
        "If you require an accommodation, please speak to your talent acquisition partner or "
        "email us at nextbit@agilebits.com and we'll work to meet your needs.",
        "Applicants for employment who require a reasonable accommodation to apply for a job "
        "should request appropriate accommodation by emailing benefits@skechers.com.",
        "If you encounter any difficulties or have specific accessibility requirements while "
        "applying for this position, please don't hesitate to reach out to us at "
        "globalrecruitment@workhuman.com for assistance.",
        "Should you need a disability-related adjustment, write to talent@corp.com.",
    ],
    ids=[
        "1password-nextbit",
        "skechers-benefits",
        "workhuman-globalrecruitment",
        "disability-adjustment",
    ],
)
def test_an_address_inside_an_accessibility_sentence_is_never_a_contact(text: str) -> None:
    """The 2026-09-02 spot check found the local-part filter insufficient: 1Password routes
    accommodation requests to nextbit@agilebits.com and Skechers to benefits@ — brand and
    department words that no exclusion list would guess. What marks them is the sentence."""
    assert extract_contact_email(text) is None


def test_a_hiring_address_survives_an_accessibility_notice_elsewhere() -> None:
    """Exclusion is scoped to the sentence, not the posting — most postings carry an
    accessibility notice, and it must not suppress a real contact in another sentence."""
    text = (
        "If you require an accommodation, email nextbit@agilebits.com. "
        "For questions about the role itself, write to careers@agilebits.com."
    )

    assert extract_contact_email(text) == "careers@agilebits.com"


def test_a_malformed_leading_character_is_not_part_of_the_address() -> None:
    """Live HN text: "Reach out directly at . +hn@dat.com" — the local part lost its name to
    a stray space, leaving a "+" prefix. An address must start on an alphanumeric."""
    assert extract_contact_email("Reach out directly at . +hn@dat.com") == "hn@dat.com"
