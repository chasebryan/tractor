import re
from urllib.parse import quote

from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.parsing import plain_text, string_value


class InternetArchive:
    id = "internet_archive"
    name = "Internet Archive"
    description = "Archive item catalog metadata; not an exhaustive Wayback crawl."

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        term = re.sub(r'["\\]', " ", query.value)
        data = await context.client.get_json(
            "https://archive.org/advancedsearch.php",
            {
                "q": f'"{term}"',
                "output": "json",
                "rows": context.limit,
                "page": 1,
                "fl[]": ["identifier", "title", "description", "creator", "date", "language"],
            },
            interval=1.5,
            stats=context.stats,
        )
        docs = data["response"]["docs"]
        results = [
            SourceResult(
                title=string_value(item.get("title", item["identifier"])),
                url="https://archive.org/details/" + quote(item["identifier"], safe=""),
                source_type=SourceType.ARCHIVE,
                source_provider=self.id,
                original_text=plain_text(string_value(item.get("description", ""))),
                author=string_value(item.get("creator", "")),
                published_at=item.get("date"),
                metadata={
                    "scope": "item catalog metadata",
                    "api_record": item,
                    "reported_language": item.get("language"),
                },
            )
            for item in docs
        ]
        return SearchBatch(results, truncated=data["response"].get("numFound", 0) > len(results))
