from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchBatch
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import SearchProvider, contract, position


class KagiSearch(SearchProvider):
    id, name = "kagi", "Kagi"
    description = (
        "Premium search through the current v1 API. Account settings may personalize results."
    )
    endpoint = "https://kagi.com/api/v1/search"
    index_family = "kagi-aggregate"
    capabilities = ProviderCapabilities(
        web=True,
        pagination=True,
        regions=True,
        freshness=True,
        site_filter=True,
        quoted_queries=True,
        requires_credentials=True,
    )

    async def search(self, query, context):
        page, offset = position(context.cursor)
        if page > 10:
            raise SourceUnavailable("Kagi exposes at most ten result pages", category="limit")
        # limit only truncates Kagi's existing page; consume complete pages locally so
        # a small engine budget does not silently skip the rest of a provider page.
        body = {"query": query.value, "workflow": "search", "page": page, "format": "json"}
        if self.options.region:
            body["filters"] = {"region": self.options.region.upper()}
        if self.options.freshness in {"day", "week", "month"}:
            body["lens"] = {"time_relative": self.options.freshness}
        elif self.options.freshness == "custom":
            body.setdefault("filters", {}).update(
                after=self.options.after, before=self.options.before
            )
        if getattr(query, "target_domain", ""):
            body.setdefault("lens", {})["sites_included"] = [query.target_domain]
        data = await context.client.get_json(
            self.endpoint,
            body=body,
            interval=1.5,
            ttl=900,
            stats=context.stats,
            auth=self.auth("https://kagi.com", prefix="Bearer "),
            provider=self.id,
        )
        contract(isinstance(data, dict) and isinstance(data.get("data"), dict))
        contract(isinstance(data["data"].get("search"), list))
        items = data["data"]["search"]
        contract(not offset or offset < len(items), "Kagi result page changed; refresh this source")
        # Only search discoveries are evidence. No answers, summaries or extraction calls.
        results = [
            self.result(
                item,
                query=query,
                page=page,
                rank=offset + i + 1,
                snippet="snippet",
                language=(item.get("props") or {}).get("language") or "und",
                provider_time=item.get("time"),
                date_basis="Provider reports created-or-updated time; not publication",
                account_personalization=True,
                provider_rank_scope="within provider page",
            )
            for i, item in enumerate(items[offset : offset + context.limit])
        ]
        local_more = offset + context.limit < len(items)
        more = local_more or bool(items) and page < 10
        cursor = f"{page}:{offset + context.limit}" if local_more else f"{page + 1}:0"
        return SearchBatch(results, truncated=bool(items), next_cursor=cursor if more else None)
