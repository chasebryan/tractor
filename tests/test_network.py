import httpx
import pytest

from tractor.network.client import (
    NetworkClient,
    NetworkPolicyError,
    RequestStats,
    SourceUnavailable,
)
from tractor.network.robots import allows_crawl
from tractor.storage.cache import ResponseCache


async def test_cache_and_request_accounting(database):
    calls = []

    def response(request):
        calls.append(request)
        assert request.headers["user-agent"].startswith("TRACTOR/")
        return httpx.Response(200, json={"hello": "world"})

    async with NetworkClient(
        ResponseCache(database.connection), transport=httpx.MockTransport(response)
    ) as client:
        stats = RequestStats()
        for _ in range(2):
            assert await client.get_json("https://api.github.com/test", stats=stats) == {
                "hello": "world"
            }
    assert len(calls) == stats.network == stats.cached == 1


async def test_no_store_policy_and_expiry(database):
    cache = ResponseCache(database.connection)
    cache.put("a", b"{}", {"cache-control": "no-store"}, 60)
    assert cache.get("a") is None
    cache.put("a", b"{}", {"cache-control": "max-age=0"}, 60)
    assert cache.get("a") is None
    cache.put("a", b"{}", {"set-cookie": "secret", "content-type": "application/json"}, 60)
    assert "set-cookie" not in cache.get("a").headers


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/x",
        "https://127.0.0.1/x",
        "https://api.github.com.evil.org/x",
        "http://private.onion/",
        "file:///etc/passwd",
        "https://api.github.com:8080/",
        "https://u:p@api.github.com/",
    ],
)
async def test_clearnet_policy_blocks_unregistered_routes(url):
    async with NetworkClient() as client:
        with pytest.raises((NetworkPolicyError, ValueError)):
            await client.get_json(url)


async def test_redirects_are_validated_before_following():
    calls = []

    def response(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://private.onion/secret"})

    async with NetworkClient(transport=httpx.MockTransport(response)) as client:
        with pytest.raises(NetworkPolicyError):
            await client.get_json("https://api.github.com/test", interval=0)
    assert len(calls) == 1


async def test_redirect_chain_is_recorded():
    def response(request):
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "/new"})
        return httpx.Response(200, json={"ok": True})

    async with NetworkClient(transport=httpx.MockTransport(response)) as client:
        stats = RequestStats()
        assert await client.get_json("https://api.github.com/old", stats=stats, interval=0)
    assert stats.redirects == ["https://api.github.com/new"]
    assert stats.network == 2


async def test_retry_backoff_and_cooldown(monkeypatch):
    import tractor.network.client as module

    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={})

    async with NetworkClient(transport=httpx.MockTransport(response)) as client:
        assert await client.get_json("https://api.github.com/x", interval=0) == {}
    assert len(calls) == 3
    assert 1 in sleeps and 2 in sleeps
    async with NetworkClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"retry-after": "120"}))
    ) as client:
        with pytest.raises(SourceUnavailable, match="cooldown"):
            await client.get_json("https://api.github.com/x", interval=0)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            200, content=b"binary", headers={"content-type": "application/octet-stream"}
        ),
        httpx.Response(200, content=b"nope", headers={"content-type": "application/json"}),
        httpx.Response(
            200, content=b" " * (4 * 1024 * 1024 + 1), headers={"content-type": "application/json"}
        ),
    ],
)
async def test_only_bounded_json_is_accepted(response):
    async with NetworkClient(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(SourceUnavailable):
            await client.get_json("https://api.github.com/x")


async def test_tor_cannot_route_clearnet_and_requires_remote_dns():
    with pytest.raises(NetworkPolicyError):
        NetworkClient(tor=True, proxy="socks5://localhost:9050")
    async with NetworkClient(
        tor=True, proxy="socks5h://127.0.0.1:9050", allowed_hosts=frozenset({"public.onion"})
    ) as client:
        assert client.validate("http://public.onion/") == "http://public.onion/"
        with pytest.raises(NetworkPolicyError):
            client.validate("https://api.github.com/")


def test_robots_policy():
    robots = "User-agent: *\nDisallow: /private\nAllow: /public"
    assert allows_crawl(robots, "https://example.org/public")
    assert not allows_crawl(robots, "https://example.org/private")
