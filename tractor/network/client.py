from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from tractor.core.deduplication import normalize_url
from tractor.network.throttling import RateLimiter
from tractor.storage.cache import ResponseCache

USER_AGENT = "TRACTOR/0.3 (+https://github.com/chasebryan/tractor; public research)"
API_HOSTS = frozenset(
    {
        "api.github.com",
        "api.crossref.org",
        "archive.org",
        "www.wikidata.org",
        "www.ebi.ac.uk",
        "api.gdeltproject.org",
    }
)


class NetworkPolicyError(ValueError):
    pass


class SourceUnavailable(RuntimeError):
    """A provider could not be queried; messages never contain request bodies or secrets."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RequestStats:
    network: int = 0
    cached: int = 0
    redirects: list[str] = field(default_factory=list)


class NetworkContext(Protocol):
    tor: bool

    async def get_json(
        self, url: str, params=None, *, interval=1.0, ttl=3600, stats=None
    ) -> Any: ...

    async def get_text(
        self, url: str, params=None, *, interval=2.0, ttl=900, stats=None
    ) -> str: ...


class NetworkClient:
    def __init__(
        self,
        cache: ResponseCache | None = None,
        *,
        allowed_hosts: frozenset[str] = API_HOSTS,
        allowed_origins: frozenset[str] = frozenset(),
        transport: httpx.AsyncBaseTransport | None = None,
        proxy: str | None = None,
        tor: bool = False,
        timeout: httpx.Timeout | None = None,
    ):
        self.cache = cache
        self.allowed_hosts = allowed_hosts
        self.allowed_origins = allowed_origins
        self.tor = tor
        if tor and (not proxy or not proxy.startswith("socks5h://")):
            raise NetworkPolicyError("Tor requires an explicit socks5h proxy with remote DNS.")
        self.limiter = RateLimiter()
        self.http = httpx.AsyncClient(
            timeout=timeout or httpx.Timeout(15, connect=8),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            proxy=proxy if transport is None else None,
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
        if not self.tor and f"{parts.scheme}://{parts.netloc}" in self.allowed_origins:
            return normalized
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
        body, _ = await self._get(
            url,
            params,
            interval=interval,
            ttl=ttl,
            stats=stats,
            kind="json",
            accepted={"application/json", "text/json"},
            max_bytes=4 * 1024 * 1024,
        )
        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeError):
            raise SourceUnavailable("Invalid JSON response") from None

    async def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        interval: float = 2.0,
        ttl: float = 900,
        stats: RequestStats | None = None,
    ) -> str:
        if not self.tor:
            raise NetworkPolicyError("HTML retrieval requires an explicit Tor source context.")
        body, headers = await self._get(
            url,
            params,
            interval=interval,
            ttl=ttl,
            stats=stats,
            kind="text",
            accepted={"text/html", "text/plain", "application/xhtml+xml"},
            max_bytes=2 * 1024 * 1024,
        )
        response = httpx.Response(
            200, content=body, headers={"content-type": headers.get("content-type", "text/plain")}
        )
        return response.text

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None,
        *,
        interval: float,
        ttl: float,
        stats: RequestStats | None,
        kind: str,
        accepted: set[str],
        max_bytes: int,
    ) -> tuple[bytes, dict[str, str]]:
        stats = stats if stats is not None else RequestStats()
        url = self.validate(str(httpx.URL(url, params=params)))
        key = hashlib.sha256(f"{'tor' if self.tor else 'clear'}:{kind}:{url}".encode()).hexdigest()
        cached = self.cache.get(key) if self.cache else None
        if cached:
            stats.cached += 1
            return cached.body, cached.headers
        current = url
        for _redirect in range(5):
            self.validate(current)
            for attempt in range(3):
                await self.limiter.wait(urlsplit(current).hostname or "", interval)
                try:
                    stats.network += 1
                    async with self.http.stream(
                        "GET", current, headers={"Accept": ", ".join(sorted(accepted))}
                    ) as response:
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
                        if content_type.lower().strip() not in accepted:
                            raise SourceUnavailable("Provider returned an unsupported content type")
                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                raise SourceUnavailable("Response exceeded the source size limit")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                        if kind == "json":
                            json.loads(body)
                        if self.cache:
                            self.cache.put(key, body, dict(response.headers), ttl)
                        return body, dict(response.headers)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.ProxyError) as exc:
                    if attempt == 2:
                        raise SourceUnavailable(type(exc).__name__) from None
                    await asyncio.sleep(2**attempt)
                except httpx.HTTPStatusError as exc:
                    raise SourceUnavailable(
                        f"HTTP {exc.response.status_code}", status_code=exc.response.status_code
                    ) from None
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
