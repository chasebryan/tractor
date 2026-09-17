from urllib.parse import quote

from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.parsing import plain_text


class Crossref:
    id = "crossref"
    name = "Crossref"
    description = "Publication metadata and DOI records; full text is not automatically fetched."

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        offset = int(context.cursor or "0")
        data = await context.client.get_json(
            "https://api.crossref.org/works",
            {"query.bibliographic": query.value, "rows": context.limit, "offset": offset},
            interval=1.0,
            stats=context.stats,
        )
        results: list[SourceResult] = []
        for item in data["message"]["items"]:
            titles = item.get("title") or [item["DOI"]]
            dates = item.get("published", {}).get("date-parts", [[]])[0]
            published = "-".join(f"{int(part):02d}" for part in dates) if dates else None
            text = plain_text(item.get("abstract") or "")
            authors = [
                " ".join(filter(None, [a.get("given"), a.get("family")]))
                for a in item.get("author", [])
            ]
            results.append(
                SourceResult(
                    title=plain_text(titles[0]),
                    url="https://doi.org/" + quote(item["DOI"], safe="/"),
                    source_type=SourceType.DOCUMENT,
                    source_provider=self.id,
                    original_text=text,
                    published_at=published,
                    original_language=item.get("language", "und"),
                    author=", ".join(authors) or None,
                    organization=item.get("publisher"),
                    metadata={
                        "doi": item["DOI"],
                        "scope": "publication metadata",
                        "api_record": item,
                    },
                )
            )
        total = data["message"].get("total-results", 0)
        more = total > offset + len(results)
        return SearchBatch(
            results,
            truncated=more,
            next_cursor=str(offset + len(results))
            if more and results and offset + len(results) <= 10000
            else None,
            total_available=total,
        )
