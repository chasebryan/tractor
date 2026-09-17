from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchBatch
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import SearchProvider, contract, page_window


class BraveSearch(SearchProvider):
    id, name = "brave", "Brave Search"
    description = "Independent web index. Requires an API key and a plan permitting result storage."
    endpoint = "https://api.search.brave.com/res/v1/web/search"
    index_family = "brave"
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
        page, offset, count = page_window(context.cursor, context.limit, first=0, maximum=20)
        if page > 9:
            raise SourceUnavailable("Brave exposes at most ten result pages", category="limit")
        language = self.language(query, context)
        params = {"q": query.value, "count": count, "offset": page, "extra_snippets": "true"}
        # Unknown language does not become English merely because a query uses Latin script.
        # Brave applies its own default when an explicit language is absent.
        if language == "all":
            context.search_language = "provider_default"
        if language != "all":
            params["search_lang"] = {"zh-cn": "zh-hans", "zh-tw": "zh-hant"}.get(language, language)
        if self.options.region:
            params["country"] = self.options.region.upper()
        if self.options.freshness != "any":
            params["freshness"] = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}.get(
                self.options.freshness, self.options.after + "to" + self.options.before
            )
        if getattr(query, "kind", "") == "domain_pivot" and getattr(query, "target_domain", ""):
            params["q"] = f"site:{query.target_domain} {query.value}"
        data = await context.client.get_json(
            self.endpoint,
            params,
            interval=1.1,
            ttl=900,
            stats=context.stats,
            auth=self.auth("https://api.search.brave.com", "X-Subscription-Token"),
            provider=self.id,
        )
        contract(isinstance(data, dict) and "error" not in data)
        web = data.get("web")
        if web is None:
            contract(
                isinstance(data.get("query"), dict)
                and data["query"].get("more_results_available") is False
            )
            return SearchBatch()
        contract(isinstance(web, dict) and isinstance(web.get("results"), list))
        items = web["results"]
        contract(len(items) <= count, "Brave ignored the requested result count")
        results = [
            self.result(
                item,
                query=query,
                page=page + 1,
                rank=page * count + offset + i + 1,
                provider_age=item.get("age"),
                additional_snippets=item.get("extra_snippets", []),
                provider_language=item.get("language"),
                request_language=language,
                request_region=self.options.region,
            )
            for i, item in enumerate(items[offset : offset + context.limit])
        ]
        contract(
            not offset or offset < len(items), "Brave result page changed; refresh this source"
        )
        local_more = offset + context.limit < len(items)
        more = bool(data.get("query", {}).get("more_results_available"))
        cursor = (
            f"{page}:{offset + context.limit}:{count}"
            if local_more
            else f"{page + 1}:0:{count}"
            if more and page < 9
            else None
        )
        return SearchBatch(results, truncated=local_more or more, next_cursor=cursor)
