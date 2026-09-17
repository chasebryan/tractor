from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.sources.base import SearchBatch, SearchContext


class GitHubRepositories:
    id = "github"
    name = "GitHub"
    description = "Public repository names and descriptions; no authenticated code search."

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        # Treat punctuation as ordinary search text, not provider-specific operators.
        term = query.value.replace('"', " ").replace(":", " ")
        data = await context.client.get_json(
            "https://api.github.com/search/repositories",
            {"q": f'"{term}"', "per_page": context.limit},
            interval=6.2,
            stats=context.stats,
        )
        results = [
            SourceResult(
                title=item["full_name"],
                url=item["html_url"],
                source_type=SourceType.CODE,
                source_provider=self.id,
                original_text=item.get("description") or "",
                published_at=item.get("created_at"),
                author=item.get("owner", {}).get("login"),
                metadata={
                    "repository": item["full_name"],
                    "stars": item.get("stargazers_count", 0),
                    "scope": "repository metadata",
                    "api_record": item,
                },
            )
            for item in data["items"]
        ]
        return SearchBatch(
            results,
            truncated=(
                bool(data.get("incomplete_results")) or data.get("total_count", 0) > len(results)
            ),
        )
