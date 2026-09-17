from datetime import datetime

from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.parsing import plain_text

LANGUAGES = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "russian": "ru",
    "arabic": "ar",
    "chinese": "zh",
    "japanese": "ja",
    "portuguese": "pt",
    "ukrainian": "uk",
    "italian": "it",
    "korean": "ko",
    "turkish": "tr",
    "dutch": "nl",
    "polish": "pl",
    "hindi": "hi",
}


class GDELTNews:
    id = "gdelt"
    name = "GDELT News"
    description = "Global news discovery over a recent three-month window; article metadata only."

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        term = query.value.replace('"', " ").replace("\\", " ")
        limit = max(5, min(250, context.limit))
        data = await context.client.get_json(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            {
                "query": f'"{term}"',
                "mode": "artlist",
                "format": "json",
                "sort": "hybridrel",
                "maxrecords": limit,
                "timespan": "3months",
            },
            interval=5.0,
            ttl=900,
            stats=context.stats,
        )
        results = []
        for item in data.get("articles", []):
            observed = item.get("seendate")
            try:
                observed = datetime.strptime(observed, "%Y%m%dT%H%M%SZ").isoformat() + "+00:00"
            except (TypeError, ValueError):
                pass
            title = plain_text(item.get("title", item["url"]))
            language = str(item.get("language", "")).lower()
            results.append(
                SourceResult(
                    title=title,
                    url=item["url"],
                    source_type=SourceType.NEWS,
                    source_provider=self.id,
                    original_language=LANGUAGES.get(language, "und"),
                    # GDELT's seen time is observation time, not the publisher's publication date.
                    metadata={
                        "region": item.get("sourcecountry"),
                        "provider_seen_at": observed,
                        "reported_language": item.get("language"),
                        "api_record": item,
                        "scope": "recent news metadata; full article not retrieved",
                    },
                )
            )
        return SearchBatch(results, truncated=len(results) >= limit)
