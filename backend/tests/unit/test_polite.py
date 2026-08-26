"""PoliteClient — the shared HTTP door: 1 rps per host, conditional GET (304→cache),
exponential backoff. Time is injected (fake clock/sleep) so the suite never really waits.
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from beacon.adapters.http.polite import PoliteClient
from beacon.application.errors import SourceUnavailable
from beacon.domain.health import FailureKind


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


async def test_get_text_returns_the_raw_body() -> None:
    # RSS feeds (We Work Remotely) need the raw text, not JSON.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss><channel/></rss>")

    clock = FakeClock()
    body = await _client(httpx.MockTransport(handler), clock).get_text(
        "https://weworkremotely.com/remote-jobs.rss"
    )

    assert body == "<rss><channel/></rss>"


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


async def test_exhausted_5xx_retries_raise_unreachable() -> None:
    # A persistent 5xx is not data — it surfaces as SourceUnavailable so the pipeline can
    # record health without importing httpx. 5xx → unreachable (transient, be patient).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0, max_retries=3)

    with pytest.raises(SourceUnavailable) as exc_info:
        await client.get_json("https://host.example/jobs")
    assert exc_info.value.kind is FailureKind.UNREACHABLE


@pytest.mark.parametrize("status", [404, 410], ids=["not-found", "gone"])
async def test_404_and_410_raise_gone(status: int) -> None:
    # A 404/410 means the slug moved or was removed — a fast-quarantine signal, not transient.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0)

    with pytest.raises(SourceUnavailable) as exc_info:
        await client.get_json("https://host.example/jobs")
    assert exc_info.value.kind is FailureKind.GONE


async def test_transport_error_raises_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("dns blip")

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0, max_retries=2)

    with pytest.raises(SourceUnavailable) as exc_info:
        await client.get_json("https://host.example/jobs")
    assert exc_info.value.kind is FailureKind.UNREACHABLE


async def test_post_json_sends_the_body_and_returns_the_parsed_response() -> None:
    # Workday CxS and MyCareersFuture expose their search as POST-only — the same politeness
    # door serves them, minus the conditional-GET cache (a POST has no validators).
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"total": 1, "jobPostings": [{"title": "iOS Engineer"}]})

    clock = FakeClock()
    data = await _client(httpx.MockTransport(handler), clock).post_json(
        "https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/Careers/jobs",
        json={"limit": 20, "offset": 0},
    )

    assert data == {"total": 1, "jobPostings": [{"title": "iOS Engineer"}]}
    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {"limit": 20, "offset": 0}


async def test_post_json_shares_the_per_host_rate_limit_with_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=1.0)

    await client.post_json("https://host.example/search", json={"page": 0})
    await client.get_json("https://host.example/jobs/1")  # same host → must wait ~1s

    assert clock.sleeps == [1.0]


async def test_post_json_maps_http_failure_to_source_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0)

    with pytest.raises(SourceUnavailable) as excinfo:
        await client.post_json("https://host.example/search", json={})

    assert excinfo.value.kind is FailureKind.GONE


# ── Auth (slice 14e) ──────────────────────────────────────────────────────────────
# Credentials are configured on the door, not handed to adapters: an adapter that never
# holds a token cannot leak one, and the per-host map means a token can only ever travel to
# the host it belongs to. NAV Norway is the first source that needs it.
async def test_get_json_sends_the_configured_bearer_token_for_that_host() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"items": []})

    clock = FakeClock()
    client = _client(
        httpx.MockTransport(handler),
        clock,
        bearer_tokens={"pam-stilling-feed.nav.no": SecretStr("nav-secret")},
    )

    await client.get_json("https://pam-stilling-feed.nav.no/api/v1/feed")

    assert seen[0].headers["authorization"] == "Bearer nav-secret"


async def test_a_credential_is_never_sent_to_another_host() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    clock = FakeClock()
    client = _client(
        httpx.MockTransport(handler),
        clock,
        bearer_tokens={"pam-stilling-feed.nav.no": SecretStr("nav-secret")},
    )

    await client.get_json("https://api.example.com/v1/jobs")

    assert "authorization" not in seen[0].headers


async def test_auth_credentials_never_appear_in_logs_or_reprs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"title": "Unauthorized"})

    clock = FakeClock()
    client = _client(
        httpx.MockTransport(handler),
        clock,
        bearer_tokens={"pam-stilling-feed.nav.no": SecretStr("nav-secret")},
    )

    with caplog.at_level("DEBUG"), pytest.raises(SourceUnavailable) as raised:
        await client.get_json("https://pam-stilling-feed.nav.no/api/v1/feed")

    assert "nav-secret" not in caplog.text
    assert "nav-secret" not in repr(client)
    assert "nav-secret" not in str(raised.value)  # the 401's message must not echo it back


# ── Pinned windows (slice 14e) ───────────────────────────────────────────────────
async def test_get_json_pins_the_window_with_an_rfc_1123_if_modified_since() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"items": []})

    clock = FakeClock()
    await _client(httpx.MockTransport(handler), clock).get_json(
        "https://pam-stilling-feed.nav.no/api/v1/feed",
        modified_since=datetime(2026, 8, 23, 8, 31, 14, tzinfo=UTC),
    )

    # NAV documents If-Modified-Since as a *filter* (RFC-1123), not only a cache validator.
    assert seen[0].headers["if-modified-since"] == "Sun, 23 Aug 2026 08:31:14 GMT"


async def test_a_pinned_window_never_reuses_the_conditional_get_cache() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"items": [1]}, headers={"ETag": "abc", "Last-Modified": "x"}
        )

    clock = FakeClock()
    client = _client(httpx.MockTransport(handler), clock, min_interval=0.0)
    url = "https://pam-stilling-feed.nav.no/api/v1/feed"

    await client.get_json(url, modified_since=datetime(2026, 8, 1, tzinfo=UTC))
    await client.get_json(url, modified_since=datetime(2026, 8, 20, tzinfo=UTC))

    # Two different windows are two different questions; caching the first answer under the
    # url alone would serve August 1st's page as if it were the 20th's.
    assert [r.headers.get("if-none-match") for r in calls] == [None, None]
    assert [r.headers["if-modified-since"] for r in calls] == [
        "Sat, 01 Aug 2026 00:00:00 GMT",
        "Thu, 20 Aug 2026 00:00:00 GMT",
    ]
