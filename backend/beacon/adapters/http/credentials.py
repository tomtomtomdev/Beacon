"""Per-host credentials for the HTTP door (slice 23b) — adapter config, not domain.

A closed union of the three schemes Beacon's sources use. Each kind renders its own header,
so the door never branches on credential type. Secrets are SecretStr so a repr, a log line
or a traceback shows `**********`, never the value.
"""

from base64 import b64encode
from dataclasses import dataclass

from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class Bearer:
    """`Authorization: Bearer <token>` (NAV Norway)."""

    token: SecretStr

    def header(self) -> tuple[str, str]:
        return "Authorization", f"Bearer {self.token.get_secret_value()}"


@dataclass(frozen=True, slots=True)
class Basic:
    """HTTP Basic with the key as username and an always-empty password (Reed's scheme)."""

    username: SecretStr

    def header(self) -> tuple[str, str]:
        userpass = f"{self.username.get_secret_value()}:".encode()
        return "Authorization", f"Basic {b64encode(userpass).decode()}"


@dataclass(frozen=True, slots=True)
class ApiKeyHeader:
    """A named key header, e.g. `X-API-Key: <value>` (Bundesagentur)."""

    name: str
    value: SecretStr

    def header(self) -> tuple[str, str]:
        return self.name, self.value.get_secret_value()


type HostCredential = Bearer | Basic | ApiKeyHeader
