"""Opt-in only: real queries may consume API credits. Never part of offline CI."""

import os

import pytest

from tractor.core.deduplication import normalize_result
from tractor.core.models import QueryVariant
from tractor.network.client import NetworkClient
from tractor.sources.base import SearchContext, SearchOptions
from tractor.sources.common_crawl import CommonCrawl
from tractor.sources.search import BraveSearch, KagiSearch, MarginaliaSearch, MojeekSearch

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TRACTOR_LIVE_TESTS") != "1",
        reason="Set TRACTOR_LIVE_TESTS=1 to allow real provider queries",
    ),
]


@pytest.mark.parametrize(
    "provider", [BraveSearch, MojeekSearch, KagiSearch, MarginaliaSearch, CommonCrawl]
)
async def test_live_search_contract_and_continuation(provider):
    options = SearchOptions(
        mojeek_storage_allowed=os.environ.get("TRACTOR_MOJEEK_STORAGE_ALLOWED") == "1"
    )
    adapter = provider(options)
    if provider not in {MarginaliaSearch, CommonCrawl} and not adapter.credential:
        pytest.skip("Provider credential is not configured")
    if provider is MojeekSearch and not options.mojeek_storage_allowed:
        pytest.skip("Mojeek requires a storage-eligible plan")
    query = QueryVariant("https://example.com/" if provider is CommonCrawl else "climate research")
    async with NetworkClient() as client:
        batch = await adapter.search(query, SearchContext(client, limit=2))
        for result in batch.results:
            normalize_result(result)
            assert result.source_provider == adapter.id
        if batch.next_cursor:
            followup = await adapter.search(
                query, SearchContext(client, limit=2, cursor=batch.next_cursor, page=2)
            )
            assert {r.url for r in batch.results} != {r.url for r in followup.results}
