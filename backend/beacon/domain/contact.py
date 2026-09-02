"""Contact-email extraction from a posting's text — pure, no IO.

Most email addresses in a job posting are not for candidates. Over the 8,918 open postings in
the live corpus (2026-09-02), 1,273 carry an address and roughly four in five are the legally
required accessibility contact (accommodations@ and its variants), with the rest privacy,
security and legal boilerplate. Fewer than 40 are addresses a candidate could write to.

So the rule is exclusion-first, on two levels: drop an address whose local part names a
non-hiring function, and drop any address sitting in an accessibility sentence — because the
local part is often innocent. 1Password routes accommodation requests to nextbit@agilebits.com
and Skechers to benefits@; no list of local parts would ever guess those, but both sentences say
"accommodation" plainly. Surfacing nothing is the right answer far more often than surfacing
something — mailing an accommodations address about a vacancy reads as not having read the ad.
"""

import re

# Local-part fragments that mark an address as not-for-candidates. Substring-matched, so
# "accommodation" also covers "accommodations", "accommodations-ext" and
# "reasonableaccommodations"; the misspellings are in the corpus verbatim (114 postings say
# "accomodations") and are cheaper to list than to normalise. Data, not logic — a new kind of
# boilerplate is a new row plus a parametrized test row, never a branch below.
_NON_HIRING_LOCAL_PARTS: tuple[str, ...] = (
    "accommodation",
    "accomodation",  # sic — 114 live postings
    "acommodation",  # sic
    "accessib",
    "privacy",
    "security",
    "legal",
    "compliance",
    "dpo",
    "gdpr",
    "abuse",
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "unsubscribe",
    "webmaster",
    "postmaster",
)

# Words that make the surrounding sentence an accessibility notice rather than an invitation to
# apply. Checked against the sentence holding the address, not the whole posting: nearly every
# large employer carries such a notice, so posting-wide matching would suppress real contacts.
_ACCESSIBILITY_CONTEXT: tuple[str, ...] = (
    "accommodation",
    "accomodation",  # sic — 114 live postings
    "acommodation",  # sic
    "accessibility",
    "accessible",
    "disability",
    "disabilities",
    "adjustment",
    "assistive",
    "special needs",
)

# Sentence boundary: terminator + whitespace, or newlines — the same split detect_sponsorship
# uses. Requiring whitespace after the terminator keeps "acme.com." from splitting an address.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Deliberately conservative on the right edge: the TLD cannot end on a dot, so "jobs@acme.com."
# yields the address without the sentence's full stop.
# The local part must START on an alphanumeric: live HN text carries "at . +hn@dat.com", where a
# stray space cost the address its name and left a "+" prefix.
_EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _is_hiring_address(address: str) -> bool:
    local = address.partition("@")[0].casefold()
    return not any(fragment in local for fragment in _NON_HIRING_LOCAL_PARTS)


def _is_accessibility_notice(sentence: str) -> bool:
    folded = sentence.casefold()
    return any(word in folded for word in _ACCESSIBILITY_CONTEXT)


def extract_contact_email(text: str) -> str | None:
    """The first address in the text that could plausibly reach a human about the job, or None.

    Casing is preserved — the value is shown to the user and copied verbatim — while both
    exclusion checks are case-insensitive.
    """
    for sentence in _SENTENCE_SPLIT.split(text):
        if _is_accessibility_notice(sentence):
            continue
        for match in _EMAIL.finditer(sentence):
            if _is_hiring_address(match.group(0)):
                return match.group(0)
    return None
