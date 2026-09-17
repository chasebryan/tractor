import json
import logging
from urllib.parse import quote

import httpx
import pytest

from tractor.core.models import QueryVariant, SourceResult
from tractor.credentials import Credential, Credentials, RequestAuth, redact
from tractor.export.csv_export import export_csv
from tractor.export.json_export import export_json
from tractor.export.report import export_markdown
from tractor.logging_config import JsonFormatter
from tractor.network.client import (
    NetworkClient,
    NetworkPolicyError,
    RequestStats,
    SourceUnavailable,
)
from tractor.settings import Settings
from tractor.sources.base import SearchContext
from tractor.sources.search import BraveSearch
from tractor.storage.cache import ResponseCache

SECRET = "fixture-api-secret-unique/+&private"


@pytest.fixture(autouse=True)
def credentials_env(monkeypatch):
    monkeypatch.setenv("TRACTOR_BRAVE_API_KEY", SECRET)
    Credentials()


async def no_wait(*_):
    pass


async def test_secret_echoes_do_not_reach_sqlite_exports_settings_or_logs(
    database, investigation, tmp_path
):
    auth = RequestAuth("https://api.search.brave.com", Credential(SECRET), "X-Subscription-Token")
    async with NetworkClient(
        ResponseCache(database.connection),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"title": SECRET, "url": "https://example.org/" + quote(SECRET, safe="")}
            )
        ),
    ) as client:
        client.limiter.wait = no_wait
        payload = await client.get_json("https://api.search.brave.com/test", auth=auth)
    assert SECRET not in str(payload)
    assert database.connection.execute("SELECT count(*) FROM cache").fetchone()[0] == 0
    investigation.query = SECRET
    investigation.results = [
        SourceResult(
            SECRET,
            "https://example.org/" + quote(SECRET, safe=""),
            "WEB",
            "brave",
            original_text=SECRET,
            metadata={"echo": SECRET},
        )
    ]
    database.save(investigation)
    dump = "\n".join(database.connection.iterdump())
    assert SECRET not in dump and quote(SECRET, safe="") not in dump
    export_json(investigation, tmp_path / "evidence.json")
    export_markdown(investigation, tmp_path / "evidence.md")
    export_csv(investigation, tmp_path / "evidence.csv")
    Settings().save(tmp_path)
    for path in tmp_path.iterdir():
        if path.suffix in {".json", ".md", ".csv"}:
            assert SECRET not in path.read_text() and quote(SECRET, safe="") not in path.read_text()
    record = logging.LogRecord("tractor", 40, "", 1, "request failed: " + SECRET, (), None)
    record.error_category = SECRET
    assert SECRET not in JsonFormatter().format(record)
    assert SECRET not in repr(auth) and SECRET not in repr(Credential(SECRET))


async def test_authenticated_cache_is_memory_only_and_separates_accounts(database):
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(200, json={"title": "Public result"})

    cache = ResponseCache(database.connection)
    async with NetworkClient(cache, transport=httpx.MockTransport(reply)) as client:
        client.limiter.wait = no_wait
        first = RequestAuth("https://kagi.com", Credential("first-private-kagi-credential"))
        second = RequestAuth("https://kagi.com", Credential("second-private-kagi-credential"))
        stats = RequestStats()
        for auth in (first, first, second):
            await client.get_json(
                "https://kagi.com/api/v1/search", auth=auth, body={"query": "topic"}, stats=stats
            )
        assert stats.cached == 1 and len(calls) == 2
        assert database.connection.execute("SELECT count(*) FROM cache").fetchone()[0] == 0
    assert not client._private_cache


@pytest.mark.parametrize("control", ["no-store", "no-cache", "private, max-age=0", 'max-age="0"'])
async def test_authenticated_cache_honors_server_policy(control):
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(200, json={}, headers={"cache-control": control})

    async with NetworkClient(transport=httpx.MockTransport(reply)) as client:
        client.limiter.wait = no_wait
        auth = RequestAuth("https://kagi.com", Credential(SECRET))
        await client.get_json("https://kagi.com/api/v1/search", auth=auth)
        await client.get_json("https://kagi.com/api/v1/search", auth=auth)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "location",
    [
        "https://api.github.com/echo",
        "https://kagi.com/redirected",
        "http://kagi.com/echo",
        "https://evil.example/steal",
    ],
)
async def test_credentials_never_follow_redirects(location):
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": location})

    async with NetworkClient(transport=httpx.MockTransport(reply)) as client:
        auth = RequestAuth("https://kagi.com", Credential(SECRET))
        with pytest.raises(NetworkPolicyError):
            await client.get_json("https://kagi.com/api/v1/search", auth=auth)
    assert len(calls) == 1


async def test_auth_origin_mismatch_rejected_before_request():
    async with NetworkClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("Must not send"))
    ) as client:
        with pytest.raises(NetworkPolicyError):
            await client.get_json(
                "https://api.github.com/echo",
                auth=RequestAuth("https://kagi.com", Credential(SECRET)),
            )


@pytest.mark.parametrize(
    "code,category",
    [(401, "credential"), (403, "credential"), (429, "rate_limited"), (500, "unavailable")],
)
async def test_errors_are_categorized_without_credentials_or_error_body(
    monkeypatch, code, category
):
    monkeypatch.setattr("tractor.network.client.asyncio.sleep", no_wait)
    async with NetworkClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(code, json={"error": SECRET}))
    ) as client:
        client.limiter.wait = no_wait
        stats = RequestStats()
        with pytest.raises(SourceUnavailable) as caught:
            await client.get_json(
                "https://api.search.brave.com/test",
                auth=RequestAuth("https://api.search.brave.com", Credential(SECRET)),
                stats=stats,
            )
    assert caught.value.category == category
    assert SECRET not in str(caught.value) and SECRET not in json.dumps(caught.value.details)
    assert stats.rate_limits == (3 if code == 429 else 0)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="Sign in", headers={"content-type": "text/html"}),
        httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"}),
        httpx.Response(
            200, content=b"x" * (4 * 1024 * 1024 + 1), headers={"content-type": "application/json"}
        ),
    ],
)
async def test_bad_or_oversized_api_response_fails_explicitly(response):
    async with NetworkClient(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(SourceUnavailable):
            await BraveSearch().search(
                QueryVariant("topic"),
                SearchContext(client),
            )


def test_secure_store_failures_and_environment_precedence(monkeypatch):
    class Store:
        def get(self, provider):
            raise RuntimeError("Secure store locked")

    assert Credentials(Store()).get("brave").source == "environment"
    monkeypatch.delenv("TRACTOR_BRAVE_API_KEY")
    assert Credentials(Store()).get("brave") is None
    assert "[REDACTED]" in redact(SECRET)


async def test_public_json_and_ndjson_echoes_are_redacted_before_cache(database):
    cache = ResponseCache(database.connection)
    async with NetworkClient(
        cache,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=json.dumps({"echo": SECRET}),
                headers={"content-type": "application/x-ndjson"},
            )
        ),
    ) as client:
        rows = await client.get_ndjson("https://index.commoncrawl.org/CC-MAIN-2025-30-index")
    assert rows == [{"echo": "[REDACTED]"}]
    assert SECRET not in "\n".join(database.connection.iterdump())
