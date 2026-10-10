"""The per-host credential table the ingest CLI hands the HTTP door (slices 14e, 23b, 23d)."""

from pydantic import SecretStr

from beacon.adapters.http.credentials import Bearer
from beacon.adapters.sources.bundesagentur import BUNDESAGENTUR_HOST
from beacon.adapters.sources.nav import NAV_HOST
from beacon.config import Settings
from beacon.ingest import host_credentials


def test_bundesagentur_public_key_is_always_on_the_door() -> None:
    credentials = host_credentials(Settings.from_env({}))

    # A published public constant, not a setting: it needs no env and no gating.
    assert credentials[BUNDESAGENTUR_HOST].header() == ("X-API-Key", "jobboerse-jobsuche")


def test_nav_bearer_joins_only_when_a_token_is_configured() -> None:
    without = host_credentials(Settings.from_env({}))
    with_token = host_credentials(Settings.from_env({"BEACON_NAV_API_TOKEN": "t0k"}))

    assert NAV_HOST not in without
    assert with_token[NAV_HOST] == Bearer(SecretStr("t0k"))
