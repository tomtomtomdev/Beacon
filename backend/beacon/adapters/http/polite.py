"""The one HTTP door all adapters fetch through (CLAUDE.md httpx conventions).

Politeness lives here, not in each adapter: at most 1 request per second per host, a
conditional GET (ETag / If-Modified-Since → 304 served from cache), and exponential
backoff over transient failures. Clock and sleep are injected so tests never really wait.

Share ONE instance across all adapters so the per-host budget is global — every Greenhouse
board sits behind the same host and must collectively obey 1 rps.

Credentials (slice 14e) are configured HERE, per host, not handed to adapters: an adapter
that never holds a token cannot leak one into a log, a repr or another host's request. They
are SecretStr for the same reason telegram_bot_token is.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from email.utils import format_datetime
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from beacon.application.errors import SourceUnavailable
from beacon.domain.health import FailureKind

logger = logging.getLogger(__name__)

# Transient statuses worth a retry; every other 4xx/5xx surfaces immediately.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

# 404/410 mean the board moved or was removed (fast-quarantine); every other HTTP failure is
# treated as transiently unreachable (SPEC §7 taxonomy).
_GONE_STATUS = frozenset({404, 410})


def _status_kind(status_code: int) -> FailureKind:
    return FailureKind.GONE if status_code in _GONE_STATUS else FailureKind.UNREACHABLE


class PoliteClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: float = 15.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        bearer_tokens: Mapping[str, SecretStr] | None = None,
    ) -> None:
        self._client = client
        # host -> bearer token. Absent host => no Authorization header, so a credential can
        # only ever reach the one host it was configured for.
        self._bearer_tokens = dict(bearer_tokens or {})
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # key -> (conditional-request headers, parsed body) for the conditional GET.
        self._cache: dict[str, tuple[dict[str, str], Any]] = {}

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        modified_since: datetime | None = None,
    ) -> Any:
        return await self._request(
            "GET", url, params, None, lambda response: response.json(), modified_since
        )

    async def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        """The raw response body — for feeds that aren't JSON (WWR's RSS/XML)."""
        return cast(
            str, await self._request("GET", url, params, None, lambda response: response.text, None)
        )

    async def post_json(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        params: Mapping[str, str] | None = None,
    ) -> Any:
        """A JSON POST through the same door — Workday CxS and MyCareersFuture only expose
        their search as POST. No conditional caching: a POST response carries no validators."""
        return await self._request(
            "POST", url, params, json, lambda response: response.json(), None
        )

    async def _request(
        self,
        method: str,
        url: str,
        params: Mapping[str, str] | None,
        json: Mapping[str, Any] | None,
        parse: Callable[[httpx.Response], Any],
        modified_since: datetime | None,
    ) -> Any:
        host = urlsplit(url).netloc
        # A caller-pinned window is a filter, not a cache validator (NAV documents
        # If-Modified-Since as the way to start the feed at a date), so it takes the header
        # over and the response is neither served from nor stored in the cache: two windows
        # are two different questions that share one url.
        conditional = method == "GET" and modified_since is None
        key = self._cache_key(url, params)
        try:
            async with self._host_lock(host):
                await self._throttle(host)
                response = await self._send_with_retry(
                    method, url, params, json, self._headers(host, key, conditional, modified_since)
                )
            if response.status_code == httpx.codes.NOT_MODIFIED:
                logger.info("http_304 url=%s served=cache", url)
                return self._cache[key][1]
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # A definite HTTP failure (retries already exhausted for transient codes).
            raise SourceUnavailable(_status_kind(exc.response.status_code), str(exc)) from exc
        except httpx.TransportError as exc:
            # DNS/connect/timeout — reachability, not a response. Always transient.
            raise SourceUnavailable(FailureKind.UNREACHABLE, str(exc)) from exc
        data = parse(response)
        if conditional:
            self._store(key, response, data)
        return data

    def _host_lock(self, host: str) -> asyncio.Lock:
        # Serialise same-host requests (so 1 rps holds under concurrency) while leaving
        # different hosts free to run in parallel.
        return self._locks.setdefault(host, asyncio.Lock())

    async def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self._min_interval - (self._monotonic() - last)
            if wait > 0:
                await self._sleep(wait)
        self._last_request[host] = self._monotonic()

    async def _send_with_retry(
        self,
        method: str,
        url: str,
        params: Mapping[str, str] | None,
        json: Mapping[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        for attempt in range(self._max_retries):
            last = attempt == self._max_retries - 1
            try:
                response = await self._client.request(
                    method, url, params=params, json=json, headers=headers, timeout=self._timeout
                )
            except httpx.TransportError:
                if last:
                    raise
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code in _RETRY_STATUS and not last:
                logger.info(
                    "http_retry url=%s status=%d attempt=%d", url, response.status_code, attempt
                )
                await self._sleep(self._backoff(attempt))
                continue
            return response
        raise AssertionError("retry loop exhausted without returning")  # pragma: no cover

    def _backoff(self, attempt: int) -> float:
        return 2.0**attempt

    def _headers(
        self, host: str, key: str, conditional: bool, modified_since: datetime | None
    ) -> dict[str, str]:
        headers = self._conditional_headers(key) if conditional else {}
        if modified_since is not None:
            headers["If-Modified-Since"] = format_datetime(modified_since, usegmt=True)
        token = self._bearer_tokens.get(host)
        if token is not None:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        return headers

    def _conditional_headers(self, key: str) -> dict[str, str]:
        cached = self._cache.get(key)
        return dict(cached[0]) if cached else {}

    def __repr__(self) -> str:
        # Never render the tokens themselves — only which hosts are configured.
        return f"PoliteClient(authenticated_hosts={sorted(self._bearer_tokens)})"

    def _store(self, key: str, response: httpx.Response, data: Any) -> None:
        validators: dict[str, str] = {}
        if etag := response.headers.get("ETag"):
            validators["If-None-Match"] = etag
        if last_modified := response.headers.get("Last-Modified"):
            validators["If-Modified-Since"] = last_modified
        self._cache[key] = (validators, data)

    @staticmethod
    def _cache_key(url: str, params: Mapping[str, str] | None) -> str:
        return f"{url}?{sorted(params.items())}" if params else url
