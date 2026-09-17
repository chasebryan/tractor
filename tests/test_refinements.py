import json
import sqlite3

import httpx
import pytest

from tractor.core.deduplication import DuplicateIndex, normalize_result
from tractor.core.models import Investigation, QueryPlan, QueryVariant, SourceResult
from tractor.core.scoring import rank_results
from tractor.network.client import NetworkClient, NetworkPolicyError
from tractor.settings import Settings, validate_web_endpoint
from tractor.sources.base import SearchContext
from tractor.sources.news import GDELTNews
from tractor.sources.web import SearxNG
from tractor.storage.atomic import atomic_text
from tractor.storage.database import Database
from tractor.storage.migrations import MIGRATIONS


def test_doi_matching_across_providers_retains_distinct_doi_records():
    a = SourceResult(
        "Study",
        "https://doi.org/10.1000/test",
        "DOCUMENT",
        "crossref",
        original_text="Research evidence. " * 50,
        metadata={"doi": "10.1000/test"},
    )
    b = SourceResult(
        "Alternate title",
        "https://europepmc.org/article/123",
        "DOCUMENT",
        "europe_pmc",
        metadata={"doi": "https://doi.org/10.1000/TEST"},
    )
    c = SourceResult(
        "Different study",
        "https://doi.org/10.1000/other",
        "DOCUMENT",
        "crossref",
        original_text=a.original_text,
        metadata={"doi": "10.1000/other"},
    )
    for record in (a, b, c):
        normalize_result(record)
    index = DuplicateIndex([a])
    assert index.find(b) == (a.id, "stable_identifier:doi")
    assert index.find(c) is None


def test_foreign_candidate_ranking_requires_recorded_query_match():
    candidate = QueryVariant("開放街圖", language="zh")
    linked = SourceResult(
        "開放街圖", "https://example.org/zh", "WEB", "test", matched_queries=[candidate.value]
    )
    unlinked = SourceResult("開放街圖", "https://example.org/other", "WEB", "test")
    inv = Investigation(
        "OpenStreetMap", QueryPlan("OpenStreetMap", [candidate]), results=[linked, unlinked]
    )
    rank_results(inv)
    assert linked.relevance_score > unlinked.relevance_score + 40
    assert linked.metadata["ranking"]["query_state"] == "discovered"
    assert linked.metadata["ranking"]["query"] == candidate.value
    assert sum(linked.score_breakdown.values()) == pytest.approx(linked.relevance_score)


def test_full_text_history_handles_literals_and_indexes_collected_text(database, investigation):
    investigation.results[0].original_text = "An international cartography archive."
    database.save(investigation)
    assert database.history(search="cartogr")[0]["id"] == investigation.id
    assert database.history(search='"cartography" OR [missing]') == []
    assert database.history(search="' ; --")
    assert database.history(search="unrelated") == []
    investigation.results[0].original_text = "A revised geospatial source."
    database.save(investigation)
    assert database.history(search="cartography") == []
    assert database.history(search="geospatial")


def test_version_one_database_migrates_and_backfills_history(tmp_path, investigation):
    path = tmp_path / "old.sqlite3"
    old = investigation.to_dict()
    for field in ("pending_tasks", "source_ids", "runs", "limits", "previous_investigation"):
        old.pop(field)
    old["schema_version"] = 1
    with sqlite3.connect(path) as connection:
        connection.executescript(MIGRATIONS[0] + "PRAGMA user_version=1;")
        connection.execute(
            "INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?)",
            (
                investigation.id,
                investigation.query,
                investigation.created_at,
                investigation.updated_at,
                investigation.status,
                json.dumps(old),
            ),
        )
    with Database(path) as database:
        assert database.history(search="annual")[0]["id"] == investigation.id
        loaded = database.load(investigation.id)
        assert loaded.results[0].title == investigation.results[0].title
        assert loaded.pending_tasks == []
        assert database.connection.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_atomic_export_failure_leaves_original_file(tmp_path):
    path = tmp_path / "export.txt"
    path.write_text("complete original")
    with pytest.raises(RuntimeError):
        with atomic_text(path) as file:
            file.write("partial new content")
            raise RuntimeError("disk or application failure")
    assert path.read_text() == "complete original"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.org",
        "https://user:pass@example.org",
        "https://example.org/?secret=123",
        "https://private.onion",
        "file:///tmp/server",
    ],
)
def test_web_endpoint_rejects_unintended_routes(endpoint):
    with pytest.raises(ValueError):
        validate_web_endpoint(endpoint)


def test_settings_roundtrip_and_existing_source_preferences(tmp_path):
    Settings(["github", "searxng"], "http://127.0.0.1:8080/").save(tmp_path)
    loaded = Settings.load(tmp_path)
    assert loaded.sources == ["github", "searxng"]
    assert loaded.allowed_origins == frozenset({"http://127.0.0.1:8080"})
    (tmp_path / "settings.json").write_text('{"sources":["github"]}')
    assert Settings.load(tmp_path).sources == ["github"]


async def test_explicit_web_origin_does_not_authorize_other_ports_or_redirects():
    calls = []

    def response(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1:9090/private"})

    async with NetworkClient(
        allowed_origins=frozenset({"http://127.0.0.1:8080"}),
        transport=httpx.MockTransport(response),
    ) as client:
        with pytest.raises(NetworkPolicyError):
            await client.get_json("http://127.0.0.1:8080/search")
    assert len(calls) == 1


async def test_web_pagination_does_not_skip_long_provider_pages():
    calls = []

    def response(request):
        calls.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": f"Page record {i}",
                        "url": f"https://example.org/{i}",
                        "content": "A snippet",
                    }
                    for i in range(4)
                ]
            },
        )

    async with NetworkClient(
        allowed_origins=frozenset({"https://search.example"}),
        transport=httpx.MockTransport(response),
    ) as client:

        async def no_wait(*_):
            pass

        client.limiter.wait = no_wait
        source = SearxNG("https://search.example")
        first = await source.search(QueryVariant("Acme"), SearchContext(client, limit=3))
        second = await source.search(
            QueryVariant("Acme"), SearchContext(client, limit=3, cursor=first.next_cursor)
        )
    assert len(first.results + second.results) == 4
    assert first.next_cursor == "1:3"
    assert second.next_cursor == "2:0"
    assert [c["pageno"] for c in calls] == ["1", "1"]
    assert calls[0]["language"] == "all"


async def test_news_observation_timestamp_is_not_reported_as_publication_date():
    from tests.test_adapters import api_fixture

    async with NetworkClient(transport=httpx.MockTransport(api_fixture)) as client:
        batch = await GDELTNews().search(QueryVariant("Acme"), SearchContext(client))
    assert batch.results[0].published_at is None
    assert batch.results[0].metadata["provider_seen_at"] == "2024-09-17T12:00:00+00:00"


def test_title_phrase_requires_whole_tokens():
    from tractor.core.scoring import score_result

    result = SourceResult("Cartography", "https://example.org/atlas", "WEB", "test")
    score_result(result, "art")
    assert result.score_breakdown["title_phrase"] == 0


def test_metadata_poor_duplicate_cannot_bridge_conflicting_identifiers():
    text = "Public research metadata. " * 20
    first = SourceResult(
        "First study",
        "https://example.org/first",
        "DOCUMENT",
        "test",
        original_text=text,
        metadata={"doi": "10.1000/first"},
    )
    copy = SourceResult(
        "Metadata copy",
        "https://example.org/copy",
        "DOCUMENT",
        "test",
        original_text=text,
        duplicate_of=first.id,
    )
    other = SourceResult(
        "Other study",
        "https://example.org/other",
        "DOCUMENT",
        "test",
        original_text=text,
        metadata={"doi": "10.1000/other"},
    )
    for record in (first, copy, other):
        normalize_result(record)
    assert DuplicateIndex([first, copy]).find(other) is None
