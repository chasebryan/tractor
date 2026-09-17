import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from tractor.core.convergence import Budget
from tractor.core.engine import InvestigationEngine
from tractor.core.models import QueryVariant
from tractor.network.client import NetworkClient, SourceUnavailable
from tractor.settings import Settings
from tractor.sources.base import SearchContext, SearchOptions
from tractor.sources.catalog import configuration, select_profile
from tractor.sources.common_crawl import CommonCrawl
from tractor.sources.search import BraveSearch, KagiSearch, MarginaliaSearch, MojeekSearch
from tractor.sources.web import SearxNG
from tractor.storage.health import provider_health


@pytest.fixture(autouse=True)
def provider_keys(monkeypatch):
    for key in ("brave", "mojeek", "kagi", "marginalia"):
        monkeypatch.setenv(f"TRACTOR_{key.upper()}_API_KEY", "private-fixture-" + key)


async def no_wait(*_):
    pass


def mock_client(handler):
    client = NetworkClient(
        transport=httpx.MockTransport(handler),
        allowed_origins=frozenset({"https://search.example"}),
    )
    client.limiter.wait = no_wait
    return client


def records(count=4):
    return [
        {
            "title": f"Evidence record {i}",
            "url": f"https://source-{i}.example/report",
            "description": f"Distinct original text {i}",
            "snippet": f"Original snippet {i}",
        }
        for i in range(count)
    ]


async def test_brave_auth_locale_rank_and_stable_page_size_after_budget_change():
    calls = []

    def reply(request):
        calls.append(request)
        assert request.headers["X-Subscription-Token"] == "private-fixture-brave"
        assert "private-fixture" not in str(request.url)
        return httpx.Response(
            200, json={"web": {"results": records(4)}, "query": {"more_results_available": True}}
        )

    async with mock_client(reply) as client:
        source = BraveSearch(SearchOptions(language="fr", region="ca", freshness="week"))
        first = await source.search(QueryVariant("subject"), SearchContext(client, limit=4))
        second = await source.search(
            QueryVariant("subject"), SearchContext(client, limit=2, cursor=first.next_cursor)
        )
        third = await source.search(
            QueryVariant("subject"), SearchContext(client, limit=2, cursor=second.next_cursor)
        )
    assert calls[0].url.params["search_lang"] == "fr"
    assert calls[0].url.params["country"] == "CA"
    assert calls[0].url.params["freshness"] == "pw"
    assert calls[1].url.params["count"] == "4"
    assert len(calls) == 2  # The second half of a provider page uses the private in-memory cache.
    assert [r.metadata["provider_rank"] for r in second.results + third.results] == [5, 6, 7, 8]
    assert third.next_cursor == "2:0:4"
    assert first.results[0].published_at is None


async def test_mojeek_exact_offset_query_auth_storage_gate_and_date_semantics():
    calls = []

    def reply(request):
        calls.append(request)
        assert request.url.params["api_key"] == "private-fixture-mojeek"
        return httpx.Response(
            200,
            json={
                "response": {
                    "status": "OK",
                    "head": {"results": 30},
                    "results": [
                        {**row, "timestamp": 1700000000, "cdatetimestamp": 1710000000}
                        for row in records(int(request.url.params["t"]))
                    ],
                }
            },
        )

    async with mock_client(reply) as client:
        with pytest.raises(SourceUnavailable, match="plan permits"):
            await MojeekSearch().search(QueryVariant("subject"), SearchContext(client))
        assert not calls
        source = MojeekSearch(
            SearchOptions(mojeek_storage_allowed=True, region="de", language="de")
        )
        first = await source.search(QueryVariant("subject"), SearchContext(client, limit=2))
        second = await source.search(
            QueryVariant("subject"), SearchContext(client, limit=1, cursor=first.next_cursor)
        )
        assert second.next_cursor == "4"
        assert second.results[0].metadata["provider_rank"] == 3
    assert first.next_cursor == "3"
    assert calls[0].url.params["rb"] == "DE" and calls[0].url.params["lb"] == "DE"
    assert first.results[0].published_at is None
    assert first.results[0].metadata["source_modified_at"].startswith("2023-")


async def test_kagi_uses_v1_post_bearer_and_only_search_results():
    calls = []

    def reply(request):
        calls.append(request)
        assert request.method == "POST" and request.url.path == "/api/v1/search"
        assert request.headers["Authorization"] == "Bearer private-fixture-kagi"
        body = json.loads(request.content)
        assert body["workflow"] == "search" and "limit" not in body and "extract" not in body
        assert body["filters"]["region"] == "FR"
        return httpx.Response(
            200,
            json={
                "data": {
                    "search": [
                        {**row, "props": {"language": "fr"}, "time": 1700000000}
                        for row in records()
                    ],
                    "direct_answer": "Do not use this generated answer",
                    "summary": "Not evidence",
                }
            },
        )

    async with mock_client(reply) as client:
        source = KagiSearch(SearchOptions(region="fr"))
        first = await source.search(QueryVariant("subject"), SearchContext(client, limit=2))
        second = await source.search(
            QueryVariant("subject"), SearchContext(client, limit=2, cursor=first.next_cursor)
        )
    assert len(calls) == 1 and second.next_cursor == "2:0"
    assert len(first.results + second.results) == 4
    assert all(r.published_at is None and r.original_language == "fr" for r in first.results)
    assert first.results[0].metadata["account_personalization"]
    assert "generated answer" not in str(first)


async def test_marginalia_public_key_override_domain_limit_and_license(monkeypatch):
    monkeypatch.delenv("TRACTOR_MARGINALIA_API_KEY")
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(200, json={"results": records(2), "license": "CC-BY-NC-SA-4.0"})

    async with mock_client(reply) as client:
        source = MarginaliaSearch(SearchOptions(results_per_domain=3))
        batch = await source.search(QueryVariant("subject"), SearchContext(client, limit=2))
        monkeypatch.setenv("TRACTOR_MARGINALIA_API_KEY", "different-marginalia-private-key")
        await MarginaliaSearch().search(QueryVariant("subject"), SearchContext(client, limit=2))
    assert calls[0].headers["API-Key"] == "public"
    assert calls[0].url.host == "api2.marginalia-search.com"
    assert calls[0].url.params["dc"] == "3"
    assert calls[1].headers["API-Key"] == "different-marginalia-private-key"
    assert batch.results[0].metadata["license"] == "CC-BY-NC-SA-4.0"
    assert batch.warnings and batch.next_cursor == "2:0:2"


@pytest.mark.parametrize(
    "provider,payload",
    [
        (BraveSearch, {"query": {"more_results_available": False}}),
        (MojeekSearch, {"response": {"status": "OK", "head": {"results": 0}, "results": []}}),
        (KagiSearch, {"data": {"search": []}}),
        (MarginaliaSearch, {"results": []}),
    ],
)
async def test_legitimate_empty_results(provider, payload):
    async with mock_client(lambda request: httpx.Response(200, json=payload)) as client:
        batch = await provider(SearchOptions(mojeek_storage_allowed=True)).search(
            QueryVariant("subject"), SearchContext(client)
        )
    assert not batch.results and batch.next_cursor is None and not batch.partial


@pytest.mark.parametrize("provider", [BraveSearch, MojeekSearch, KagiSearch, MarginaliaSearch])
@pytest.mark.parametrize("payload", [{}, {"error": "Not authorized"}, {"results": None}])
async def test_broken_contract_is_not_reported_as_empty(provider, payload):
    async with mock_client(lambda request: httpx.Response(200, json=payload)) as client:
        with pytest.raises(SourceUnavailable):
            await provider(SearchOptions(mojeek_storage_allowed=True)).search(
                QueryVariant("subject"), SearchContext(client)
            )


async def test_searx_partial_results_persist_and_retry_same_cursor(database):
    partial = True

    def reply(request):
        return httpx.Response(
            200,
            json={
                "results": [{**records(1)[0], "engines": ["brave", "mojeek"], "score": 0.8}],
                "unresponsive_engines": [["marginalia", "timeout"]] if partial else [],
            },
        )

    async with mock_client(reply) as client:
        source = SearxNG("https://search.example")
        inv = await InvestigationEngine([source], client, database, budget=Budget(max_jobs=1)).run(
            "subject"
        )
        assert inv.attempts[0].status == "partial" and inv.pending_tasks[0].cursor is None
        assert len(inv.results) == 1 and inv.attempts[0].warnings
        assert inv.coverage["known_independent_search_indexes"] == ["brave", "mojeek"]
        assert (
            provider_health(database.connection)["searxng"]["last_error_class"]
            == "upstream_partial"
        )
        partial = False
        resumed = await InvestigationEngine(
            [source], client, database, budget=Budget(max_jobs=1)
        ).run("", resume=database.load(inv.id))
    assert resumed.attempts[-1].status == "success"
    assert resumed.pending_tasks[0].cursor == "2:0"
    assert len(resumed.unique_results) == 1
    assert len(resumed.unique_results[0].metadata["discovery_observations"]) == 2


async def test_searx_upstream_outage_is_error_and_query_routing_explicit(database):
    async with mock_client(
        lambda request: httpx.Response(
            200, json={"results": [], "unresponsive_engines": [["brave", "timeout"]]}
        )
    ) as client:
        inv = await InvestigationEngine(
            [SearxNG("https://search.example", SearchOptions(freshness="week"))], client, database
        ).run("subject")
    assert inv.status == "failed" and inv.attempts[0].error_category == "upstream"
    assert "unsupported" in inv.attempts[0].warnings[0]


async def test_common_crawl_preserves_collection_and_every_block_row():
    calls = []

    def reply(request):
        calls.append(request)
        if request.url.path == "/collinfo.json":
            return httpx.Response(
                200, json=[{"id": "CC-MAIN-2025-30", "cdx-api": "https://evil.example"}]
            )
        assert request.url.host == "index.commoncrawl.org"
        if "showNumPages" in request.url.params:
            return httpx.Response(200, json={"pages": 2, "blocks": 2, "pageSize": 1})
        block = int(request.url.params["page"])
        return httpx.Response(
            200,
            headers={"content-type": "application/x-ndjson"},
            content="\n".join(
                json.dumps(
                    {
                        "url": f"https://example.org/{block}-{i}",
                        "timestamp": "20250801120000",
                        "mime": "text/html",
                        "status": "200",
                        "digest": f"digest-{i}",
                    }
                )
                for i in range(3)
            ),
        )

    async with mock_client(reply) as client:
        source = CommonCrawl()
        query = QueryVariant("example.org")
        first = await source.search(query, SearchContext(client, limit=2))
        second = await source.search(
            query, SearchContext(client, limit=2, cursor=first.next_cursor)
        )
        third = await source.search(
            query, SearchContext(client, limit=2, cursor=second.next_cursor)
        )
    assert [r.metadata["original_url"] for r in first.results + second.results + third.results] == [
        "https://example.org/0-0",
        "https://example.org/0-1",
        "https://example.org/0-2",
        "https://example.org/1-0",
        "https://example.org/1-1",
    ]
    assert json.loads(first.next_cursor)["collection"] == "CC-MAIN-2025-30"
    assert first.results[0].published_at is None
    assert first.results[0].metadata["capture_time"].startswith("2025-08-")
    assert all(request.url.host == "index.commoncrawl.org" for request in calls)


async def test_common_crawl_keyword_is_skipped_without_network(database):
    async with mock_client(
        lambda _: pytest.fail("Keyword lookup must not make a request")
    ) as client:
        inv = await InvestigationEngine([CommonCrawl()], client, database).run("Acme")
    assert inv.status == "complete" and inv.attempts[0].status == "skipped"
    assert inv.coverage["sources_successful"] == 0 and not inv.pending_tasks


@pytest.mark.parametrize(
    "message,empty", [("No Captures found for: example.org", True), ("Unknown collection", False)]
)
async def test_common_crawl_404_is_empty_only_for_explicit_no_captures(message, empty):
    def reply(request):
        if request.url.path == "/collinfo.json":
            return httpx.Response(200, json=[{"id": "CC-MAIN-2025-30"}])
        return httpx.Response(404, json={"message": message})

    async with mock_client(reply) as client:
        if empty:
            assert not (
                await CommonCrawl().search(QueryVariant("example.org"), SearchContext(client))
            ).results
        else:
            with pytest.raises(SourceUnavailable):
                await CommonCrawl().search(QueryVariant("example.org"), SearchContext(client))


async def test_provider_cancellation_preserves_pending_work(database):
    started = asyncio.Event()

    async def reply(request):
        started.set()
        await asyncio.Event().wait()

    async with mock_client(reply) as client:
        task = asyncio.create_task(
            InvestigationEngine([BraveSearch()], client, database).run("subject")
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    saved = database.load(database.history()[0]["id"])
    assert saved.status == "cancelled" and saved.pending_tasks


def test_profiles_and_settings_roundtrip_preserve_new_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("TRACTOR_BRAVE_API_KEY")
    settings = Settings(
        ["marginalia", "common_crawl"],
        search=SearchOptions(language="ar", results_per_domain=4),
        budget=Budget(max_jobs=120),
    )
    settings.save(tmp_path)
    assert Settings.load(tmp_path) == settings
    assert configuration(settings)["brave"]["configuration"] == "Credential missing"
    assert "brave" not in select_profile(settings, "Maximum coverage")
    assert "common_crawl" in select_profile(settings, "Historical")
    assert "mojeek" not in select_profile(settings, "Maximum coverage")
    assert "mojeek" in select_profile(
        replace(settings, search=SearchOptions(mojeek_storage_allowed=True)), "Maximum coverage"
    )
