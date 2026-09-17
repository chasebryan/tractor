from urllib.parse import urlsplit

from tractor.core.models import SourceType
from tractor.network.client import SourceUnavailable
from tractor.network.tor import onion_host
from tractor.sources.base import SearchBatch
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import SearchProvider, contract, position, timestamp


class SearxNG(SearchProvider):
    id, name = "searxng", "SearxNG · Web search"
    description = (
        "General or news search from your configured server, with upstream-engine reporting."
    )
    capabilities = ProviderCapabilities(
        web=True, news=True, pagination=True, languages=True, freshness=True
    )

    def __init__(self, endpoint, options=None, credentials=None):
        super().__init__(options, credentials)
        self.endpoint = endpoint.rstrip("/") + "/search"

    async def search(self, query, context):
        page, offset = position(context.cursor)
        language = self.language(query, context)
        category = "onions" if self.network == "tor" else self.options.category
        params = {
            "q": query.value,
            "format": "json",
            "pageno": page,
            "language": language,
            "categories": category,
        }
        if self.options.freshness in {"day", "month", "year"}:
            params["time_range"] = self.options.freshness
        data = await context.client.get_json(
            self.endpoint, params, interval=1.5, ttl=900, stats=context.stats
        )
        contract(isinstance(data, dict) and isinstance(data.get("results"), list))
        failures = data.get("unresponsive_engines", [])
        contract(isinstance(failures, list))
        warnings = [
            "Upstream engine unavailable: " + str(item[0])[:100]
            if isinstance(item, list) and item
            else "An upstream search engine failed"
            for item in failures
        ]
        if failures and not data["results"]:
            raise SourceUnavailable(
                "SearxNG upstream engines failed; no successful empty search was recorded",
                category="upstream",
            )
        items = []
        for index, item in enumerate(data["results"]):
            contract(isinstance(item, dict) and isinstance(item.get("url"), str))
            is_onion = (urlsplit(item["url"]).hostname or "").endswith(".onion")
            if self.network == "tor":
                try:
                    onion_host(item["url"])
                    if urlsplit(item["url"]).port not in (None, 80, 443):
                        continue
                except ValueError:
                    continue
            elif is_onion:
                continue
            items.append((index, item))
        if data["results"] and not items:
            raise SourceUnavailable(
                "The server returned no links for its configured network route", category="contract"
            )
        contract(
            not offset or offset < len(items), "SearxNG result page changed; refresh this source"
        )
        results = []
        for index, item in items[offset : offset + context.limit]:
            result = self.result(
                item,
                query=query,
                page=page,
                rank=index + 1,
                snippet="content",
                upstream_engines=item.get("engines", []),
                provider_score=item.get("score"),
                server_identity=self.identity,
                category=category,
                upstream_failures=warnings,
                provider_rank_scope="within provider page",
                network=self.network,
            )
            result.source_type = (
                SourceType.ONION
                if self.network == "tor"
                else SourceType.NEWS
                if category == "news"
                else SourceType.WEB
            )
            result.published_at = timestamp(item.get("publishedDate"))
            results.append(result)
        more_local = offset + context.limit < len(items)
        cursor = f"{page}:{offset + context.limit}" if more_local else f"{page + 1}:0"
        return SearchBatch(
            results,
            truncated=bool(items),
            next_cursor=cursor if items else None,
            warnings=warnings,
            partial=bool(failures),
        )
