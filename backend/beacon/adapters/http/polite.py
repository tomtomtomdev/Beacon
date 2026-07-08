"""The one HTTP door all adapters fetch through (CLAUDE.md httpx conventions).

Politeness lives here, not in each adapter: at most 1 request per second per host, a
conditional GET (ETag / If-Modified-Since → 304 served from cache), and exponential
backoff over transient failures. Clock and sleep are injected so tests never really wait.

Share ONE instance across all adapters so the per-host budget is global — every Greenhouse
board sits behind the same host and must collectively obey 1 rps.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

# Transient statuses worth a retry; every other 4xx/5xx surfaces immediately.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


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
    ) -> None:
        self._client = client
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # key -> (conditional-request headers, parsed body) for the conditional GET.
        self._cache: dict[str, tuple[dict[str, str], Any]] = {}

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        host = urlsplit(url).netloc
        key = self._cache_key(url, params)
        async with self._host_lock(host):
            await self._throttle(host)
            response = await self._get_with_retry(url, params, self._conditional_headers(key))
        if response.status_code == httpx.codes.NOT_MODIFIED:
            logger.info("http_304 url=%s served=cache", url)
            return self._cache[key][1]
        response.raise_for_status()
        data = response.json()
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

    async def _get_with_retry(
        self, url: str, params: Mapping[str, str] | None, headers: dict[str, str]
    ) -> httpx.Response:
        for attempt in range(self._max_retries):
            last = attempt == self._max_retries - 1
            try:
                response = await self._client.get(
                    url, params=params, headers=headers, timeout=self._timeout
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

    def _conditional_headers(self, key: str) -> dict[str, str]:
        cached = self._cache.get(key)
        return dict(cached[0]) if cached else {}

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
