"""Hand-flag a company as a MANUAL sponsor — the path for human-verified signals that
have no machine-readable register (relocate.me listings, confirmed sponsorships, direct
knowledge). No fuzzy matching: the flag references the company directly at confidence 1.0.
"""

from datetime import date

from beacon.application.ports import CompanyRepo, JobRepo
from beacon.domain.registry import Registry
from beacon.domain.sponsorship import resolve_tier


def flag_manual_sponsor(
    company_repo: CompanyRepo,
    jobs: JobRepo,
    name: str,
    evidence: str,
    *,
    flagged_on: date,
) -> None:
    company = company_repo.get_by_name(name)
    if company is None or company.id is None:
        raise ValueError(f"no company named {name!r}")

    flags = Registry(company.registry_flags) | Registry.MANUAL
    note = f"MANUAL: {evidence} (flagged {flagged_on.isoformat()})"
    company_repo.set_registry_match(company.id, int(flags), 1.0, note)
    jobs.resolve_registry_tier(company.id, resolve_tier(None, int(flags)).value)
