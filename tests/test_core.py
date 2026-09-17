import copy

import pytest

from tractor.analysis.relationships import correlate
from tractor.core.convergence import Budget, convergence_reason
from tractor.core.deduplication import find_duplicate, normalize_result, normalize_url
from tractor.core.entities import normalize_identifier
from tractor.core.filtering import ResultFilter
from tractor.core.models import AliasState, QueryVariant
from tractor.core.provenance import record_discovery
from tractor.core.query import add_variant, build_plan, normalize_query
from tractor.core.scoring import score_result
from tractor.language.detect import detect_language
from tractor.language.translate import Translation, translate_result


def test_query_normalization_and_seed():
    assert normalize_query("  Ａcme    Mining  ") == "Acme Mining"
    assert normalize_query("Acme\nMining\tReport") == "Acme Mining Report"
    plan = build_plan("Acme Ltd")
    assert plan.seed == "Acme Ltd"
    assert plan.variants[0].state == AliasState.SEED
    assert plan.variants[1].value == "Acme Limited"
    assert plan.variants[1].state == AliasState.DISCOVERED


@pytest.mark.parametrize("value", ["", " \t\n", "a" * 241])
def test_bad_queries(value):
    with pytest.raises(ValueError):
        normalize_query(value)


def test_alias_dedup_keeps_evidence_but_does_not_invent_corroboration():
    plan = build_plan("Acme")
    assert add_variant(plan, QueryVariant("Acme Holdings", evidence_urls=["https://a.org"]))
    assert not add_variant(plan, QueryVariant("ACME HOLDINGS", evidence_urls=["https://b.org"]))
    assert plan.variants[-1].state == "discovered"
    assert len(plan.variants[-1].evidence_urls) == 2
    assert not add_variant(plan, QueryVariant("Refuted", state="rejected"))


def test_transliteration_is_a_hypothesis():
    plan = build_plan("Газпром")
    assert len(plan.variants) == 2
    assert plan.variants[1].source == "transliteration"
    assert plan.variants[1].state == "discovered"


def test_url_normalization_preserves_semantics():
    assert normalize_url("HTTPS://ExAmple.org:443/Report?utm_source=x&a=1#part") == (
        "https://example.org/Report?a=1"
    )
    assert normalize_url("https://x.org/a") != normalize_url("https://x.org/a/")
    assert normalize_url("https://x.org/?x=2&x=1").endswith("?x=2&x=1")
    assert normalize_url("https://[2001:db8::1]:443/") == "https://[2001:db8::1]/"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/a", "https://u:p@a.org", "/x"])
def test_unsafe_source_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_duplicates_retain_representative_and_ignore_empty_metadata(result):
    normalize_result(result)
    copy_result = copy.deepcopy(result)
    copy_result.id = "copy"
    copy_result.url += "?utm_campaign=mail"
    normalize_result(copy_result)
    assert find_duplicate(copy_result, [result]) == (result.id, "canonical_url")
    copy_result.url = "https://another.org/report"
    copy_result.original_text = result.original_text = ""
    normalize_result(result)
    normalize_result(copy_result)
    assert find_duplicate(copy_result, [result]) is None


def test_hash_and_near_duplicate_detection(result):
    result.original_text = "A documented finding with substantial original evidence. " * 10
    normalize_result(result)
    mirror = copy.deepcopy(result)
    mirror.id = "mirror"
    mirror.url = "https://mirror.org/copy"
    normalize_result(mirror)
    assert find_duplicate(mirror, [result])[1] == "content_hash"
    mirror.original_text += " Additional note."
    normalize_result(mirror)
    assert find_duplicate(mirror, [result])[1] == "near_duplicate_text"


def test_ranking_is_explainable_and_relevant(result):
    result.discovery_path = ["seed", "query", result.id]
    score_result(result, "Northstar Mining")
    relevant = result.relevance_score
    assert relevant == sum(result.score_breakdown.values())
    score_result(result, "Unrelated Subject")
    assert relevant > result.relevance_score
    assert result.evidence_score == 100


def test_identifiers_do_not_casefold_email_local_part():
    assert normalize_identifier("domain", "EXAMPLE.ORG.") == "example.org"
    assert normalize_identifier("doi", "https://doi.org/10.123/ABC") == "10.123/abc"
    assert normalize_identifier("email", "Person@EXAMPLE.ORG") == "Person@example.org"


def test_recursive_provenance_and_observed_relationships(investigation, result):
    initial = QueryVariant("Northstar Mining", state="seed")
    record_discovery(investigation, initial, result)
    second = copy.deepcopy(result)
    second.id = "child"
    pivot = QueryVariant("Northstar Mining Limited", parent_result=result.id)
    record_discovery(investigation, pivot, second)
    assert second.discovery_path == [investigation.id, initial.id, result.id, pivot.id, "child"]
    correlate(investigation, result)
    correlate(investigation, second)
    assert len(investigation.entities) == 1
    assert investigation.entities[0].evidence_results == [result.id, "child"]
    assert all(edge.kind != "same_person" for edge in investigation.edges)


def test_convergence_budgets_and_frontier():
    budget = Budget()
    assert convergence_reason(1, 20, 2, 4, budget) is None
    assert "No new" in convergence_reason(2, 0, 2, 8, budget)
    assert "No unsearched" in convergence_reason(1, 10, 0, 4, budget)
    assert "budget" in convergence_reason(3, 5, 1, 48, budget)
    with pytest.raises(ValueError):
        Budget(concurrency=0)


def test_result_filters(investigation, result):
    assert ResultFilter(source_type="DOCUMENT", domain="example.org").apply(investigation)
    assert not ResultFilter(domain="ample.org").apply(investigation)
    assert not ResultFilter(after="2025-01-01").apply(investigation)
    assert not ResultFilter(language="de").apply(investigation)
    assert ResultFilter(text="northstar").apply(investigation)


def test_partial_dates_and_invalid_filters(investigation, result):
    result.published_at = "2024-03"
    assert ResultFilter(after="2024-03-15", before="2024-03-20").apply(investigation)
    assert not ResultFilter(after="2024-04-01").apply(investigation)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        ResultFilter(after="yesterday").apply(investigation)
    with pytest.raises(ValueError, match="start date"):
        ResultFilter(after="2025-01-01", before="2024-01-01").apply(investigation)


def test_unknown_language_is_not_guessed_from_short_names():
    assert detect_language("Northstar Mining") == "und"
    assert (
        detect_language("This is a lengthy English document describing a public research study.")
        == "en"
    )


async def test_translation_preserves_original(result):
    class Backend:
        async def translate(self, text, source, target):
            return Translation("Translated " + text, source, target, "test", 0.8)

    original = copy.deepcopy(result)
    await translate_result(result, Backend())
    assert result.original_text == original.original_text
    assert result.title == original.title
    assert result.translated_text.startswith("Translated ")
    assert result.metadata["translation"]["machine_translated"]
