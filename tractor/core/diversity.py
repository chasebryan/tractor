"""Discovery diversity is not factual corroboration or source independence."""

from urllib.parse import urlsplit

# Only explicit, known independent indexes qualify. A metasearch brand is not an index.
INDEPENDENT_INDEXES = frozenset({"brave", "mojeek", "marginalia", "torch"})
UPSTREAM_INDEXES = {"brave": "brave", "mojeek": "mojeek", "marginalia": "marginalia"}


def index_families(result) -> set[str]:
    direct = result.metadata.get("index_family", result.source_provider)
    families = {direct} if direct in INDEPENDENT_INDEXES else set()
    for engine in result.metadata.get("upstream_engines", []):
        if engine in UPSTREAM_INDEXES:
            families.add(UPSTREAM_INDEXES[engine])
    return families


def observation(result) -> dict:
    return {
        "result_id": result.id,
        "provider": result.source_provider,
        "queries": list(result.matched_queries),
        "query_variant": result.metadata.get("discovery", {}).get("query_variant"),
        "url": result.url,
        "discovered_at": result.discovered_at,
        "provider_rank": result.metadata.get("provider_rank"),
        "search_page": result.metadata.get("search_page"),
        "upstream_engines": result.metadata.get("upstream_engines", []),
        "independent_index_families": sorted(index_families(result)),
        "meaning": "Discovery path only; no factual corroboration asserted.",
    }


def diversity(results) -> dict:
    return {
        "providers_represented": sorted({r.source_provider for r in results}),
        "known_independent_search_indexes": sorted(
            {family for result in results for family in index_families(result)}
        ),
        "domains_represented": sorted(
            {urlsplit(r.metadata.get("original_url", r.url)).hostname or "" for r in results} - {""}
        ),
        "source_types_represented": sorted({str(r.source_type) for r in results}),
        "discovery_agreement_is_factual_corroboration": False,
    }
