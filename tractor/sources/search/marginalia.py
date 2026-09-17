from tractor.sources.base import SearchBatch
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import SearchProvider, contract, page_window


class MarginaliaSearch(SearchProvider):
    id, name = "marginalia", "Marginalia"
    description = (
        "Independent small-web index. A shared development key is available with rate limits."
    )
    endpoint = "https://api2.marginalia-search.com/search"
    index_family = "marginalia"
    capabilities = ProviderCapabilities(web=True, pagination=True, independent_index=True)

    async def search(self, query, context):
        page, offset, count = page_window(context.cursor, context.limit)
        data = await context.client.get_json(
            self.endpoint,
            {
                "query": query.value,
                "count": count,
                "dc": self.options.results_per_domain,
                "page": page,
            },
            interval=2.5,
            ttl=900,
            stats=context.stats,
            auth=self.auth("https://api2.marginalia-search.com", "API-Key"),
            provider=self.id,
        )
        contract(isinstance(data, dict) and isinstance(data.get("results"), list))
        items = data["results"]
        contract(len(items) <= count, "Marginalia ignored the requested result count")
        results = [
            self.result(
                item,
                query=query,
                page=page,
                rank=(page - 1) * count + offset + i + 1,
                license=data.get("license"),
                results_per_domain=self.options.results_per_domain,
                shared_development_key=self.credential.source == "shared development key",
            )
            for i, item in enumerate(items[offset : offset + context.limit])
        ]
        contract(not offset or offset < len(items), "Marginalia page changed; refresh this source")
        local_more = offset + context.limit < len(items)
        more = len(items) >= count
        cursor = (
            f"{page}:{offset + context.limit}:{count}" if local_more else f"{page + 1}:0:{count}"
        )
        warnings = (
            ["Marginalia uses a shared development key; availability and rate limits are shared."]
            if self.credential.source == "shared development key"
            else []
        )
        return SearchBatch(
            results,
            truncated=local_more or more,
            next_cursor=cursor if local_more or more else None,
            warnings=warnings,
        )
