"""Evidence-line wording shared by the counting registers.

Three registers now count something per employer (US certified filings, IE permits
issued, CA positive LMIAs and positions) and the count lands in the job-detail drawer as
English, so the pluralisation lives in one place instead of once per ingester.
"""


def counted(count: int, noun: str) -> str:
    """ "1 employment permit" / "2 employment permits" — regular plurals only, which is all
    the register nouns need."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
