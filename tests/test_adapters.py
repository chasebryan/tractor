import httpx

from tractor.core.models import QueryVariant
from tractor.network.client import NetworkClient
from tractor.sources import default_adapters
from tractor.sources.base import SearchContext
from tractor.sources.parsing import plain_text
from tractor.sources.registries import Wikidata


def api_fixture(request):
    host = request.url.host
    if host == "api.gdeltproject.org":
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "title": "Acme news",
                        "url": "https://example.org/news",
                        "language": "English",
                        "sourcecountry": "United Kingdom",
                        "seendate": "20240917T120000Z",
                    }
                ]
            },
        )
    if host == "www.ebi.ac.uk":
        return httpx.Response(
            200,
            json={
                "hitCount": 1,
                "resultList": {
                    "result": [
                        {
                            "title": "Acme study",
                            "source": "MED",
                            "id": "123",
                            "pmid": "123",
                            "abstractText": "<p>Acme research.</p>",
                            "doi": "10.1000/acme",
                            "language": "eng",
                        }
                    ]
                },
            },
        )
    if host == "api.github.com":
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "full_name": "acme/research",
                        "html_url": "https://github.com/acme/research",
                        "description": "Acme studies",
                    }
                ],
            },
        )
    if host == "api.crossref.org":
        return httpx.Response(
            200,
            json={
                "message": {
                    "total-results": 1,
                    "items": [
                        {
                            "DOI": "10.1000/acme",
                            "title": ["Acme study"],
                            "abstract": "<p>Study</p>",
                            "published": {"date-parts": [[2024, 3]]},
                        }
                    ],
                }
            },
        )
    if host == "archive.org":
        return httpx.Response(
            200,
            json={
                "response": {
                    "numFound": 1,
                    "docs": [
                        {"identifier": "acme-report", "title": "Acme", "description": ["Report"]}
                    ],
                }
            },
        )
    if request.url.params["action"] == "wbsearchentities":
        return httpx.Response(
            200,
            json={
                "search": [{"id": "Q123", "label": "Acme", "description": "Example organization"}]
            },
        )
    return httpx.Response(
        200,
        json={
            "entities": {
                "Q123": {
                    "labels": {
                        "en": {"language": "en", "value": "Acme"},
                        "ja": {"language": "ja", "value": "アクメ企業"},
                    },
                    "aliases": {"en": [{"language": "en", "value": "Acme Corporation"}]},
                }
            }
        },
    )


async def test_all_adapters_return_normalized_contract():
    async with NetworkClient(transport=httpx.MockTransport(api_fixture)) as client:
        for adapter in default_adapters():
            batch = await adapter.search(QueryVariant("Acme"), SearchContext(client))
            assert len(batch.results) == 1
            result = batch.results[0]
            assert result.source_provider == adapter.id
            assert result.url.startswith("https://")
            assert result.metadata["api_record"]


async def test_multilingual_candidates_retain_evidence_and_state():
    async with NetworkClient(transport=httpx.MockTransport(api_fixture)) as client:
        batch = await Wikidata().search(QueryVariant("Acme"), SearchContext(client))
    japanese = next(v for v in batch.variants if v.language == "ja")
    assert japanese.state == "discovered"
    assert japanese.parent_result == batch.results[0].id
    assert japanese.evidence_urls == [batch.results[0].url]
    assert "unverified" in japanese.reason


async def test_unmatched_records_do_not_create_aliases():
    async with NetworkClient(transport=httpx.MockTransport(api_fixture)) as client:
        batch = await Wikidata().search(QueryVariant("Different Acme"), SearchContext(client))
    assert batch.results
    assert not batch.variants


def test_extracted_html_is_inert():
    assert plain_text("<p>Safe &amp; sound</p><script>alert(1)</script>") == "Safe & sound"


async def test_default_multilingual_labels_produce_foreign_candidates():
    def response(request):
        if request.url.params["action"] == "wbsearchentities":
            return httpx.Response(200, json={"search": [{"id": "Q936", "label": "OpenStreetMap"}]})
        assert "mul" in request.url.params["languages"].split("|")
        return httpx.Response(
            200,
            json={
                "entities": {
                    "Q936": {
                        "labels": {
                            "mul": {"language": "mul", "value": "OpenStreetMap"},
                            "zh": {"language": "zh", "value": "開放街圖"},
                            "ja": {"language": "ja", "value": "オープンストリートマップ"},
                        }
                    }
                }
            },
        )

    async with NetworkClient(transport=httpx.MockTransport(response)) as client:
        batch = await Wikidata().search(QueryVariant("OpenStreetMap"), SearchContext(client))
    assert {v.language for v in batch.variants} == {"zh", "ja", "und"}
    assert all(v.state == "discovered" for v in batch.variants)
