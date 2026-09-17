from tractor.core.models import Edge, Investigation, QueryVariant, SourceResult


def record_discovery(inv: Investigation, variant: QueryVariant, result: SourceResult) -> None:
    result.matched_queries = list(dict.fromkeys([*result.matched_queries, variant.value]))
    result.parent_result = variant.parent_result
    result.discovery_path = [inv.id, variant.id, result.id]
    if variant.parent_result:
        parent = next((r for r in inv.results if r.id == variant.parent_result), None)
        if parent:
            result.discovery_path = [*parent.discovery_path, variant.id, result.id]
    inv.edges.append(
        Edge(
            variant.id,
            result.id,
            "discovered_via",
            [result.id],
            explanation=f"Returned by {result.source_provider}.",
        )
    )
