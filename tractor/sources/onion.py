"""Public onion index adapters. Result destinations are never fetched automatically."""

import re
from urllib.parse import urlencode, urlsplit

from bs4 import BeautifulSoup
from protego import Protego

from tractor.core.deduplication import normalize_url
from tractor.core.models import QueryVariant, SourceResult, SourceType
from tractor.network.client import SourceUnavailable
from tractor.network.tor import onion_host
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.capabilities import ProviderCapabilities
from tractor.sources.search.searxng import SearxNG

TORCH_HOST = "xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion"
TORCH_URL = "http://" + TORCH_HOST


def safe_onion_url(value: str) -> str | None:
    try:
        onion_host(value)
        normalized = normalize_url(value)
        if urlsplit(normalized).port not in (None, 80, 443):
            return None
        return normalized
    except (ValueError, UnicodeError, TypeError, AttributeError):
        return None


class TorchSearch:
    id = "torch"
    name = "Torch · Tor onion index"
    description = (
        "Searches a public onion index through Tor; returns text snippets and onion links."
    )
    network = "tor"
    identity = TORCH_URL
    onion_hosts = frozenset({TORCH_HOST})

    def __init__(self):
        self.robots: Protego | None = None
        self.interval = 2.0
        self.robots_basis = ""
        self.forms: dict[str, dict[str, str]] = {}

    async def check_robots(self, context: SearchContext, url: str) -> None:
        if self.robots is None:
            try:
                text = await context.client.get_text(
                    TORCH_URL + "/robots.txt", ttl=3600, stats=context.stats
                )
                if "<html" in text[:500].lower() or "<!doctype" in text[:500].lower():
                    raise SourceUnavailable("The onion index returned an unreadable robots policy.")
                self.robots_basis = "robots.txt retrieved through Tor"
            except SourceUnavailable as exc:
                if exc.status_code not in {404, 410}:
                    raise SourceUnavailable(
                        "Could not verify the onion index robots policy; search was not sent."
                    ) from None
                text = ""
                self.robots_basis = f"No robots file published (HTTP {exc.status_code})"
            self.robots = Protego.parse(text)
            rate = self.robots.request_rate("TRACTOR")
            self.interval = max(
                2,
                self.robots.crawl_delay("TRACTOR") or 0,
                rate.seconds / rate.requests if rate and rate.requests else 0,
            )
        if not self.robots.can_fetch(url, "TRACTOR"):
            raise SourceUnavailable("The onion index disallows automated searching in robots.txt.")

    @staticmethod
    def form_fields(soup: BeautifulSoup) -> dict[str, str]:
        # Only ordinary search-form state is replayed, always to the fixed registered URL.
        form = soup.find("form", attrs={"name": "P"})
        allowed = {"DB", "FMT", "xDB", "xFILTERS", "xP", "tkn"}
        return (
            {
                node["name"]: str(node.get("value", "")).strip()[:4096]
                for node in form.select('input[type="hidden"][name]')
                if node["name"] in allowed
            }
            if form
            else {}
        )

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch:
        if not context.client.tor:
            raise SourceUnavailable("This source requires the separate Tor connection.")
        try:
            offset = int(context.cursor or "0")
        except ValueError:
            raise SourceUnavailable("The saved onion page cursor is invalid.") from None
        if offset < 0 or offset > 10000:
            raise SourceUnavailable("The onion index page cursor is outside its retrieval limit.")
        url = TORCH_URL + "/cgi-bin/omega/omega"
        policy_url = url + "?" + urlencode({"P": query.value})
        await self.check_robots(context, url)
        await self.check_robots(context, policy_url)
        if query.value not in self.forms:
            home = await context.client.get_text(
                url, interval=self.interval, ttl=0, stats=context.stats
            )
            soup = BeautifulSoup(home, "html.parser")
            fields = self.form_fields(soup)
            if not soup.select_one('input[name="P"]') or not fields.get("tkn"):
                raise SourceUnavailable(
                    "The onion index search form is unavailable or requires an interactive "
                    "challenge."
                )
            self.forms[query.value] = fields
        # Omega resets an offset unless xP contains its own previous parsed query.
        # On resume, rebuild that state from page one before requesting the saved offset.
        positions = [0, offset] if offset and not self.forms[query.value].get("xP") else [offset]
        for position in positions:
            parameters = {
                **self.forms[query.value],
                "P": query.value,
                "DEFAULTOP": "and",
                "TOPDOC": position,
                "HITSPERPAGE": context.limit,
            }
            await self.check_robots(context, url + "?" + urlencode(parameters))
            html = await context.client.get_text(
                url, parameters, interval=self.interval, ttl=900, stats=context.stats
            )
            soup = BeautifulSoup(html, "html.parser")
            entered = soup.select_one('input[name="P"]')
            if not entered or entered.get("value", "") != query.value:
                self.forms.pop(query.value, None)
                raise SourceUnavailable(
                    "The onion index did not accept the search. Retry later; no zero-match "
                    "result was recorded."
                )
            self.forms[query.value] = self.form_fields(soup)
        for node in soup(["script", "style", "noscript", "iframe"]):
            node.decompose()
        text = soup.get_text(" ", strip=True)
        page_range = re.search(
            r"(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)\s+of\s+(?:about\s+)?([\d,]+)\s+matches", text
        )
        no_matches = bool(re.search(r"no (?:documents? )?match(?:es| your query)", text, re.I))
        if not page_range and not no_matches:
            raise SourceUnavailable(
                "The onion index returned unrecognized results; its search interface "
                "may have changed."
            )
        start, end, total = (
            tuple(int(value.replace(",", "")) for value in page_range.groups())
            if page_range
            else (0, 0, 0)
        )
        if page_range and start != offset + 1:
            raise SourceUnavailable(
                "The onion index did not honor the saved page offset; retry this page later."
            )
        results = []
        seen = set()
        for row in soup.select("table tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            cell = cells[1]
            link = cell.find("a", href=True)
            title = cell.find("b")
            if not link or not title:
                continue
            address = safe_onion_url(link.get("href", ""))
            if not address or address in seen:
                continue
            seen.add(address)
            snippet = cell.find("small")
            snippet_text = snippet.get_text(" ", strip=True) if snippet else ""
            results.append(
                SourceResult(
                    title=title.get_text(" ", strip=True) or address,
                    url=address,
                    source_type=SourceType.ONION,
                    source_provider=self.id,
                    original_text=snippet_text,
                    metadata={
                        "network": "tor",
                        "index_url": self.identity,
                        "index_offset": offset,
                        "robots_policy": self.robots_basis,
                        "scope": "Onion search-index snippet; destination page not retrieved",
                    },
                )
            )
        if page_range and not results:
            raise SourceUnavailable(
                "The onion index returned matches but no usable v3 onion links."
            )
        if len(results) > context.limit or end - start + 1 > context.limit:
            raise SourceUnavailable(
                "The onion index ignored the requested page size; no records were skipped."
            )
        more = bool(soup.select_one('input[name=">"]:not([disabled])'))
        return SearchBatch(
            results,
            truncated=more,
            total_available=total,
            next_cursor=str(end) if more and end < 10000 else None,
        )


class OnionSearxNG(SearxNG):
    id = "onion_searxng"
    name = "SearxNG · Tor onion metasearch"
    description = "Searches the onions category of your onion-hosted SearxNG server."
    network = "tor"
    capabilities = ProviderCapabilities(onion=True, pagination=True, languages=True, freshness=True)

    def __init__(self, endpoint, options=None, credentials=None):
        super().__init__(endpoint, options, credentials)
        self.onion_hosts = frozenset({onion_host(self.endpoint)})

    async def search(self, query, context):
        if not context.client.tor:
            raise SourceUnavailable("This source requires the separate Tor connection.")
        return await super().search(query, context)
