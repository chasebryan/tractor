from urllib.parse import quote

from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.parsing import plain_text

LANGUAGES = {
    "eng": "en",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "deu": "de",
    "spa": "es",
    "por": "pt",
    "rus": "ru",
    "jpn": "ja",
    "chi": "zh",
    "zho": "zh",
    "ita": "it",
    "kor": "ko",
    "ara": "ar",
    "pol": "pl",
    "dut": "nl",
    "nld": "nl",
}


class EuropePMC:
    id = "europe_pmc"
    name = "Europe PMC"
    description = "Life-sciences publications and abstracts, with DOI and publication identifiers."

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        term = query.value.replace('"', " ").replace("\\", " ")
        data = await context.client.get_json(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            {
                "query": f'"{term}"',
                "format": "json",
                "resultType": "core",
                "pageSize": context.limit,
                "cursorMark": context.cursor or "*",
            },
            stats=context.stats,
            interval=1.0,
        )
        results = []
        for item in data["resultList"]["result"]:
            source, identifier = str(item["source"]), str(item["id"])
            results.append(
                SourceResult(
                    title=plain_text(item.get("title", identifier)),
                    url="https://europepmc.org/article/"
                    f"{quote(source, safe='')}/{quote(identifier, safe='')}",
                    source_type=SourceType.DOCUMENT,
                    source_provider=self.id,
                    original_text=plain_text(item.get("abstractText", "")),
                    author=item.get("authorString"),
                    published_at=item.get("firstPublicationDate"),
                    original_language=LANGUAGES.get(
                        item.get("language"), item.get("language") or "und"
                    ),
                    metadata={
                        "doi": item.get("doi"),
                        "pmid": item.get("pmid"),
                        "scope": "publication metadata and abstract",
                        "api_record": item,
                    },
                )
            )
        cursor = data.get("nextCursorMark")
        more = bool(results and cursor and cursor != (context.cursor or "*"))
        return SearchBatch(
            results,
            truncated=more,
            next_cursor=cursor if more else None,
            total_available=data.get("hitCount"),
        )
