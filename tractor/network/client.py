from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from tractor.core.deduplication import normalize_url
from tractor.network.throttling import RateLimiter
from tractor.storage.cache import ResponseCache

USER_AGENT = "TRACTOR/0.1 (+https://github.com/chasebryan/tractor; public research)"
API_HOSTS = frozenset({"api.github.com", "api.crossref.org", "archive.org", "www.wikidata.org"})


class NetworkPolicyError(ValueError):
    pass


class SourceUnavailable(RuntimeError):
    """A provider could not be queried; messages never contain request bodies or secrets."""


@dataclass
class RequestStats:
    network: int = 0
    cached: int = 0
    redirects: list[str] = field(default_factory=list)


class NetworkClient:
    def __init__(
        self,
        cache: ResponseCache | None = None,
        *,
        allowed_hosts: frozenset[str] = API_HOSTS,
        transport: httpx.AsyncBaseTransport | None = None,
        proxy: str | None = None,
        tor: bool = False,
    ):
        self.cache = cache
        self.allowed_hosts = allowed_hosts
        self.tor = tor
        if tor and (not proxy or not proxy.startswith("socks5h://")):
            raise NetworkPolicyError("Tor requires an explicit socks5h proxy with remote DNS.")
        self.limiter = RateLimiter()
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(15, connect=8),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            proxy=proxy,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "en",
            },
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    def validate(self, url: str) -> str:
        normalized = normalize_url(url)
        parts = urlsplit(normalized)
        host = parts.hostname or ""
        onion = host.endswith(".onion")
        if self.tor != onion:
            raise NetworkPolicyError("Onion and clearnet requests require separate clients.")
        if host not in self.allowed_hosts:
            raise NetworkPolicyError("Host is not registered in this network context.")
        if parts.port not in (None, 80, 443):
            raise NetworkPolicyError("Nonstandard remote ports are not allowed.")
        if not self.tor and parts.scheme != "https":
            raise NetworkPolicyError("Public API requests require HTTPS.")
        return normalized

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        interval: float = 1.0,
        ttl: float = 3600,
        stats: RequestStats | None = None,
    ) -> Any:
        stats = stats if stats is not None else RequestStats()
        url = self.validate(str(httpx.URL(url, params=params)))
        key = hashlib.sha256(f"{'tor' if self.tor else 'clear'}:{url}".encode()).hexdigest()
        cached = self.cache.get(key) if self.cache else None
        if cached:
            stats.cached += 1
            return json.loads(cached.body)
        current = url
        for _redirect in range(5):
            self.validate(current)
            for attempt in range(3):
                await self.limiter.wait(urlsplit(current).hostname or "", interval)
                try:
                    stats.network += 1
                    async with self.http.stream("GET", current) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise SourceUnavailable("Redirect without a destination")
                            current = self.validate(urljoin(current, location))
                            stats.redirects.append(current)
                            break
                        if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                            retry = response.headers.get("retry-after", "")
                            delay = float(retry) if retry.isdigit() else 2**attempt
                            if delay > 20:
                                raise SourceUnavailable("Provider requested a longer cooldown")
                            await asyncio.sleep(max(delay, 2**attempt))
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").split(";")[0]
                        if content_type not in {"application/json", "text/json"}:
                            raise SourceUnavailable("Provider did not return JSON metadata")
                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 4 * 1024 * 1024:
                                raise SourceUnavailable("Response exceeded the 4 MiB safety limit")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        value = json.loads(body)
                        if self.cache:
                            self.cache.put(key, body, dict(response.headers), ttl)
                        return value
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt == 2:
                        raise SourceUnavailable(type(exc).__name__) from None
                    await asyncio.sleep(2**attempt)
                except httpx.HTTPStatusError as exc:
                    raise SourceUnavailable(f"HTTP {exc.response.status_code}") from None
                except (json.JSONDecodeError, UnicodeError, httpx.DecodingError):
                    raise SourceUnavailable("Invalid JSON response") from None
            else:
                raise SourceUnavailable("Request retry limit reached")
        raise SourceUnavailable("Redirect limit reached")

    async def close(self) -> None:
        await self.http.aclose()

    async def __aenter__(self) -> NetworkClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
