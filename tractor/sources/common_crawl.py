"""CDX metadata discovery only; no WARC or arbitrary document retrieval."""

import json
import re
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit

from tractor.core.deduplication import normalize_url
from tractor.core.models import SourceResult, SourceType
from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchBatch, SearchOptions
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.base import contract


class CommonCrawl:
    id, name = "common_crawl", "Common Crawl"
    description = "Historical capture metadata for a known URL or domain; not keyword web search."
    capabilities = ProviderCapabilities(
        archive=True, historical=True, pagination=True, independent_index=True
    )
    index_family = "common-crawl"

    def __init__(self, options=None):
        self.options = options or SearchOptions()
        self.collections = None

    @property
    def identity(self):
        return "common_crawl:" + (self.options.common_crawl_collection or "latest-at-start")

    def prepare_query(self, query):
        value = query.value.strip()
        explicit_url = value.startswith(("https://", "http://"))
        if not explicit_url and not re.fullmatch(r"[\w.-]+\.[a-zA-Z]{2,63}", value):
            return None
        try:
            normalized = normalize_url(value if explicit_url else "https://" + value)
            host = urlsplit(normalized).hostname or ""
        except ValueError:
            return None
        if host.endswith(".onion") or "." not in host or host in {"localhost", "127.0.0.1"}:
            return None
        return (normalized, "exact") if explicit_url else (host, "domain")

    async def search(self, query, context):
        target = self.prepare_query(query)
        if target is None:
            return SearchBatch(
                skipped_reason=(
                    "Common Crawl requires a known HTTP(S) URL or domain; "
                    "keyword search is unsupported."
                )
            )
        if self.collections is None:
            data = await context.client.get_json(
                "https://index.commoncrawl.org/collinfo.json", stats=context.stats
            )
            contract(isinstance(data, list) and bool(data))
            self.collections = [
                item["id"]
                for item in data
                if isinstance(item, dict)
                and re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", str(item.get("id", "")))
            ]
            contract(bool(self.collections))
        if context.cursor:
            try:
                saved = json.loads(context.cursor)
                collection, page, offset = (
                    saved["collection"],
                    int(saved["page"]),
                    int(saved["offset"]),
                )
                if saved["target"] != list(target) or page < 0 or offset < 0:
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise SourceUnavailable(
                    "Saved Common Crawl cursor is invalid", category="cursor"
                ) from None
        else:
            collection = self.options.common_crawl_collection or self.collections[0]
            page, offset = 0, 0
        if collection not in self.collections:
            raise SourceUnavailable(
                "The selected crawl collection is not available", category="configuration"
            )
        endpoint = "https://index.commoncrawl.org/" + collection + "-index"
        params = {"url": target[0], "matchType": target[1], "pageSize": 1}
        try:
            counts = await context.client.get_json(
                endpoint,
                {**params, "showNumPages": "true"},
                interval=2,
                ttl=3600,
                stats=context.stats,
            )
        except SourceUnavailable as exc:
            if exc.status_code == 404 and str(exc.details.get("message", "")).startswith(
                "No Captures found"
            ):
                return SearchBatch()
            raise
        contract(isinstance(counts, dict) and isinstance(counts.get("pages"), int))
        pages = counts["pages"]
        if pages == 0:
            return SearchBatch()
        if page >= pages:
            raise SourceUnavailable(
                "Crawl index pagination changed; refresh this source", category="cursor"
            )
        # Do not apply a line limit and then skip to the next index block. Read a bounded
        # block and consume it in local chunks, preserving every remaining row in the cursor.
        rows = await context.client.get_ndjson(
            endpoint,
            {**params, "page": page, "output": "json"},
            interval=2,
            ttl=3600,
            stats=context.stats,
        )
        if offset and offset >= len(rows):
            raise SourceUnavailable(
                "Crawl index block changed; refresh this source", category="cursor"
            )
        results = []
        for item in rows[offset : offset + context.limit]:
            contract(
                isinstance(item, dict)
                and isinstance(item.get("url"), str)
                and re.fullmatch(r"\d{14}", str(item.get("timestamp", "")))
            )
            try:
                capture_time = (
                    datetime.strptime(item["timestamp"], "%Y%m%d%H%M%S")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )
            except ValueError:
                raise SourceUnavailable("Invalid capture timestamp", category="contract") from None
            metadata_url = (
                endpoint
                + "?"
                + urlencode(
                    {
                        "url": item["url"],
                        "matchType": "exact",
                        "filter": "timestamp:" + item["timestamp"],
                        "output": "json",
                    }
                )
            )
            results.append(
                SourceResult(
                    title="Archived capture · " + (urlsplit(item["url"]).hostname or item["url"]),
                    url=metadata_url,
                    source_type=SourceType.ARCHIVE,
                    source_provider=self.id,
                    original_text=(
                        f"URL: {item['url']}\nCaptured: {capture_time}\n"
                        f"MIME: {item.get('mime', 'unknown')}\n"
                        f"HTTP status: {item.get('status', 'unknown')}"
                    ),
                    metadata={
                        "api_record": item,
                        "original_url": item["url"],
                        "capture_time": capture_time,
                        "crawl_collection": collection,
                        "mime": item.get("mime"),
                        "status": item.get("status"),
                        "digest": item.get("digest"),
                        "index_family": self.index_family,
                        "lineage": "archive_index_record",
                        "scope": "Capture metadata only; archived content has not been retrieved",
                    },
                )
            )
        local_more = offset + context.limit < len(rows)
        next_page, next_offset = (page, offset + context.limit) if local_more else (page + 1, 0)
        more = local_more or next_page < pages
        cursor = json.dumps(
            {"collection": collection, "page": next_page, "offset": next_offset, "target": target}
        )
        return SearchBatch(results, truncated=more, next_cursor=cursor if more else None)
