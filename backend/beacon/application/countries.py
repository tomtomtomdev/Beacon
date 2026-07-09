"""Country reference use cases: keep the table in sync with the domain constant, read it."""

from beacon.application.ports import CountryRepo
from beacon.domain.visa import COUNTRY_REFERENCE, CountryReference


def seed_countries(repo: CountryRepo) -> None:
    """Upsert the SPEC §4 reference rows. Idempotent — the domain constant is the source
    of truth, so running this at startup keeps the table matching it."""
    repo.seed(COUNTRY_REFERENCE)


def list_countries(repo: CountryRepo) -> list[CountryReference]:
    return repo.get_all()
