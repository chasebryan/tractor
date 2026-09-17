from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.parsing import plain_text


class SearxNG:
    id = "searxng"
    name = "SearxNG · Web search"
    description = "General web results from your configured SearxNG server. JSON must be enabled."

    def __init__(self, endpoint: str):
        self.endpoint = endpoint.rstrip("/") + "/search"
        self.identity = self.endpoint

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        position = (context.cursor or "1:0").split(":")
        page, offset = int(position[0]), int(position[1]) if len(position) > 1 else 0
        context.search_language = query.language if query.language != "und" else "all"
        data = await context.client.get_json(
            self.endpoint,
            {
                "q": query.value,
                "format": "json",
                "pageno": page,
                "language": context.search_language,
                "categories": "general",
            },
            interval=1.5,
            ttl=900,
            stats=context.stats,
        )
        results = [
            SourceResult(
                title=plain_text(item.get("title", "Untitled web result")),
                url=item.get("url", ""),
                source_type=SourceType.WEB,
                source_provider=self.id,
                original_text=plain_text(item.get("content", "")),
                published_at=item.get("publishedDate"),
                metadata={
                    "api_record": item,
                    "search_engines": item.get("engines", []),
                    "scope": "Search snippets; full pages have not been downloaded",
                },
            )
            for item in data.get("results", [])[offset : offset + context.limit]
        ]
        # SearxNG offers page numbers, but no consistent total or last-page indicator.
        # An empty or repeated page ends retrieval; engine budgets bound other responses.
        more_on_page = offset + context.limit < len(data.get("results", []))
        next_cursor = f"{page}:{offset + context.limit}" if more_on_page else f"{page + 1}:0"
        return SearchBatch(
            results, truncated=bool(results), next_cursor=next_cursor if results else None
        )
