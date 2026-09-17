import re

from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchBatch, SearchContext


class Wikidata:
    id = "wikidata"
    name = "Wikidata"
    description = (
        "Public knowledge records and multilingual label candidates; not a company registry."
    )

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        language = query.language if query.language in context.languages else "en"
        context.search_language = language
        data = await context.client.get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbsearchentities",
                "format": "json",
                "search": query.value,
                "language": language,
                "uselang": language,
                "limit": min(context.limit, 10),
                **({"continue": context.cursor} if context.cursor else {}),
            },
            stats=context.stats,
        )
        if "error" in data:
            raise SourceUnavailable("Wikidata search API error")
        hits = data["search"]
        ids = [h["id"] for h in hits if re.fullmatch(r"Q\d+", h["id"])]
        if not ids:
            return SearchBatch()
        details = await context.client.get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(ids),
                "props": "labels|aliases|descriptions",
                # Many proper names are stored once under the default `mul` language.
                "languages": "|".join((*context.languages, "mul")),
            },
            stats=context.stats,
        )
        if "error" in details:
            raise SourceUnavailable("Wikidata entity API error")
        batch = SearchBatch(
            truncated="search-continue" in data,
            next_cursor=str(data["search-continue"]) if "search-continue" in data else None,
        )
        for hit in hits:
            if hit["id"] not in ids:
                continue
            detail = details["entities"].get(hit["id"], {})
            result = SourceResult(
                title=hit.get("label", hit["id"]),
                url="https://www.wikidata.org/wiki/" + hit["id"],
                source_type=SourceType.DATASET,
                source_provider=self.id,
                original_language=language,
                original_text=hit.get("description", ""),
                metadata={
                    "wikidata": hit["id"],
                    "api_record": detail,
                    "search_record": hit,
                    "scope": "knowledge record; subject match is unverified",
                },
            )
            batch.results.append(result)
            labels = list(detail.get("labels", {}).values())
            aliases = [a for group in detail.get("aliases", {}).values() for a in group]
            # Exact textual agreement permits a candidate pivot, never an identity assertion.
            match_values = [v["value"] for v in labels + aliases]
            match_values += [hit.get("label", ""), hit.get("match", {}).get("text", "")]
            if not any(value.casefold() == query.value.casefold() for value in match_values):
                continue
            for candidate in labels + aliases:
                if len(candidate["value"]) < 4:
                    continue
                batch.variants.append(
                    QueryVariant(
                        candidate["value"],
                        source="entity_discovery",
                        language=(
                            "und" if candidate["language"] == "mul" else candidate["language"]
                        ),
                        parent_result=result.id,
                        evidence_urls=[result.url],
                        reason=(
                            f"Label or alias on {hit['id']}, whose label matches the query. "
                            "This record may describe a different subject; identity is unverified."
                        ),
                    )
                )
        # Prefer language diversity over exhausting one record's English aliases.
        batch.variants.sort(key=lambda v: (v.language == language, len(v.value)))
        diverse: list[QueryVariant] = []
        remainder: list[QueryVariant] = []
        seen_languages: set[str] = set()
        for variant in batch.variants:
            if variant.language not in seen_languages:
                diverse.append(variant)
                seen_languages.add(variant.language)
            else:
                remainder.append(variant)
        batch.variants = diverse + remainder
        return batch
