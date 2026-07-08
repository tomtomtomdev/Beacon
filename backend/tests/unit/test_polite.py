"""PoliteClient — the shared HTTP door: 1 rps per host, conditional GET (304→cache),
exponential backoff. Time is injected (fake clock/sleep) so the suite never really waits.
"""

from typing import Any

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient


class FakeClock:
    """Monotonic clock that only advances when we sleep — lets tests assert wait durations."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


def _client(handler: httpx.MockTransport, clock: FakeClock, **kw: Any) -> PoliteClient:
    http = httpx.AsyncClient(transport=handler)
    return PoliteClient(http, sleep=clock.sleep, monotonic=clock.monotonic, **kw)


async def test_get_json_returns_parsed_body_and_passes_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"jobs": [1, 2]})

    clock = FakeClock()
    data = await _client(httpx.MockTransport(handler), clock).get_json(
        "https://api.example.com/v1/jobs", params={"content": "true"}
    )

    assert data == {"jobs": [1, 2]}
    assert seen[0].url.params.get("content") == "true"


async def test_rate_limits_per_host_but_not_across_hosts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=1.0)

    await client.get_json("https://host-a.example/jobs")  # first: no wait
    await client.get_json("https://host-a.example/other")  # same host: must wait ~1s
    await client.get_json("https://host-b.example/jobs")  # different host: no wait

    assert clock.sleeps == [1.0]


async def test_conditional_get_returns_cache_on_304() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"v": 1}, headers={"ETag": 'W/"abc"'})
        assert request.headers.get("If-None-Match") == 'W/"abc"'
        return httpx.Response(304)

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0)

    first = await client.get_json("https://host.example/jobs")
    second = await client.get_json("https://host.example/jobs")

    assert first == {"v": 1}
    assert second == {"v": 1}  # served from cache on 304


async def test_retries_on_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0, max_retries=3)

    data = await client.get_json("https://host.example/jobs")

    assert data == {"ok": True}
    assert calls["n"] == 3
    assert len(clock.sleeps) == 2  # backed off before each retry


async def test_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0, max_retries=3)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_json("https://host.example/jobs")
