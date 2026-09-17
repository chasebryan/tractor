from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchBatch
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import SearchProvider, contract, position, timestamp


class MojeekSearch(SearchProvider):
    id, name = "mojeek", "Mojeek"
    description = "Independent web index. Requires an API key with permission to retain results."
    endpoint = "https://www.mojeek.com/search"
    index_family = "mojeek"
    capabilities = ProviderCapabilities(
        web=True,
        pagination=True,
        languages=True,
        regions=True,
        freshness=True,
        site_filter=True,
        quoted_queries=True,
        requires_credentials=True,
        independent_index=True,
    )

    async def search(self, query, context):
        if not self.options.mojeek_storage_allowed:
            raise SourceUnavailable(
                "Confirm that your Mojeek plan permits result storage in Settings",
                category="configuration",
            )
        start, _ = position(context.cursor)
        count = min(context.limit, 10)
        language = self.language(query, context)
        params = {"q": query.value, "s": start, "t": count, "fmt": "json", "date": 1, "cdate": 1}
        if language != "all":
            params.update(lb=language.split("-")[0].upper(), lbb=100)
        if self.options.region:
            params.update(rb=self.options.region.upper(), rbb=10)
        freshness = self.options.freshness
        if freshness in {"day", "month", "year"}:
            params["since"] = freshness
        elif freshness == "custom":
            params.update(
                since=self.options.after.replace("-", ""),
                before=self.options.before.replace("-", ""),
            )
        if getattr(query, "target_domain", ""):
            params["site"] = query.target_domain
        data = await context.client.get_json(
            self.endpoint,
            params,
            interval=1.2,
            ttl=900,
            stats=context.stats,
            auth=self.auth("https://www.mojeek.com", query_parameter="api_key"),
            provider=self.id,
        )
        contract(isinstance(data, dict) and isinstance(data.get("response"), dict))
        response = data["response"]
        status = response.get("status")
        if status != "OK":
            lowered = str(status).lower()
            category = (
                "rate_limited"
                if "limit" in lowered
                else "credential"
                if "key" in lowered
                else "unavailable"
            )
            raise SourceUnavailable("Mojeek reported an API error", category=category)
        contract(
            isinstance(response.get("results"), list) and isinstance(response.get("head"), dict)
        )
        items = response["results"]
        contract(len(items) <= count, "Mojeek ignored the requested result count")
        results = []
        for i, item in enumerate(items):
            result = self.result(
                item,
                query=query,
                page=context.page,
                rank=start + i,
                snippet="desc",
                source_modified_at=timestamp(item.get("timestamp")),
                provider_seen_at=timestamp(item.get("cdatetimestamp")),
                request_language=language,
                request_region=self.options.region,
                provider_score=item.get("score"),
            )
            result.published_at = timestamp(item.get("pdate"))
            results.append(result)
        total = response["head"].get("results")
        more = bool(items) and (
            start + len(items) <= total if isinstance(total, int) else len(items) >= count
        )
        return SearchBatch(
            results, truncated=more, next_cursor=str(start + len(items)) if more else None
        )
