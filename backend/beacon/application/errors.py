"""Application-level errors that cross a port boundary.

SourceUnavailable is how a Fetcher tells the pipeline "this request failed at the transport/
HTTP level" while carrying the health FailureKind — so ingest can record source health
without ever importing httpx (Clean Architecture: the application layer stays IO-free)."""

from beacon.domain.health import FailureKind


class SourceUnavailable(Exception):
    """A fetch failed for a reason that maps to a source-health FailureKind. The concrete
    HTTP client (PoliteClient) classifies the httpx error and raises this; ingest catches it."""

    def __init__(self, kind: FailureKind, message: str = "") -> None:
        super().__init__(message or kind.value)
        self.kind = kind
