from tractor.core.entities import extract_entities
from tractor.core.models import Edge, Investigation, SourceResult


def correlate(inv: Investigation, result: SourceResult) -> None:
    by_id = {e.id: e for e in inv.entities}
    for entity in extract_entities(result):
        if entity.id in by_id:
            existing = by_id[entity.id]
            if result.id not in existing.evidence_results:
                existing.evidence_results.append(result.id)
        else:
            inv.entities.append(entity)
        result.entities.append(entity.id)
        kind = "hosted_at" if entity.kind == "domain" else "mentions_identifier"
        inv.edges.append(
            Edge(
                result.id,
                entity.id,
                kind,
                [result.id],
                explanation=(
                    "Shared identifiers connect records; "
                    "they do not establish a shared person or owner."
                ),
            )
        )
