"""Shared API contracts, bounded metadata, and provider-specific query preparation."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime

from tractor.core.models import SourceResult, SourceType
from tractor.credentials import Credentials, RequestAuth
from tractor.network.client import SourceUnavailable
from tractor.sources.base import SearchOptions
from tractor.sources.parsing import plain_text


def contract(condition, message="Provider returned a malformed search response"):
    if not condition:
        raise SourceUnavailable(message, category="contract")


def position(cursor, *, initial=1):
    try:
        parts = (cursor or str(initial)).split(":")
        page, offset = int(parts[0]), int(parts[1]) if len(parts) == 2 else 0
        if len(parts) > 2 or page < initial or page > 10000 or offset < 0 or offset > 100000:
            raise ValueError
        return page, offset
    except (TypeError, ValueError):
        raise SourceUnavailable("Saved provider cursor is invalid", category="cursor") from None


def page_window(cursor, limit, *, first=1, maximum=100):
    if cursor is None:
        return first, 0, min(limit, maximum)
    try:
        page, offset, size = map(int, cursor.split(":"))
        if not first <= page <= 10000 or not 0 <= offset < size <= maximum:
            raise ValueError
        return page, offset, size
    except (ValueError, TypeError):
        raise SourceUnavailable("Saved provider cursor is invalid", category="cursor") from None


def timestamp(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, UTC).isoformat()
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    return None


def raw_metadata(item):
    encoded = json.dumps(item, ensure_ascii=False)
    if len(encoded.encode()) <= 65536:
        return {"api_record": item}
    # The extracted fields below still retain their own bounded values.
    return {
        "api_record_truncated": True,
        "api_record_size": len(encoded.encode()),
        "api_record_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
    }


class SearchProvider:
    network = "clearnet"
    group = "Web search"
    index_family = ""
    endpoint = ""

    def __init__(self, options=None, credentials=None):
        self.options = options or SearchOptions()
        self.credentials = credentials or Credentials()
        self.credential = self.credentials.get(self.id)

    @property
    def identity(self):
        # An opaque identity invalidates saved cursors after account/configuration changes.
        value = [
            self.endpoint,
            asdict(self.options),
            hashlib.sha256(self.credential.value.encode()).hexdigest() if self.credential else "",
        ]
        return (
            self.id + ":" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        )

    def auth(self, origin, header="Authorization", prefix="", query_parameter=""):
        if not self.credential:
            raise SourceUnavailable(
                f"Credential missing: set TRACTOR_{self.id.upper()}_API_KEY",
                category="credential_missing",
            )
        return RequestAuth(origin, self.credential, header, prefix, query_parameter)

    def language(self, query, context):
        language = query.language if self.options.language == "auto" else self.options.language
        context.search_language = (
            language if language not in {"und", "mul", "auto", "all"} else "all"
        )
        return context.search_language

    def routing_notes(self, query):
        notes = []
        options = self.options
        supported = {
            "brave": {"day", "week", "month", "year", "custom"},
            "mojeek": {"day", "month", "year", "custom"},
            "kagi": {"day", "week", "month", "custom"},
            "searxng": {"day", "month", "year"},
            "onion_searxng": {"day", "month", "year"},
        }.get(self.id, set())
        if options.freshness != "any" and options.freshness not in supported:
            notes.append(
                f"{self.name}: requested freshness is unsupported; results are unfiltered."
            )
        if options.language not in {"auto", "all"} and not self.capabilities.languages:
            notes.append(f"{self.name}: API does not expose a language filter.")
        if options.region and not self.capabilities.regions:
            notes.append(f"{self.name}: API does not expose a region hint.")
        if options.category != "general" and not self.capabilities.news:
            notes.append(f"{self.name}: standard web workflow used; no news category filter.")
        if self.id == "brave" and (
            options.language == "all"
            or options.language == "auto"
            and query.language in {"und", "mul"}
        ):
            notes.append(
                "Brave: no supported language inferred; the provider's default language applies."
            )
        return notes

    def result(self, item, *, query, page, rank, snippet="description", language="und", **metadata):
        contract(isinstance(item, dict) and isinstance(item.get("url"), str))
        return SourceResult(
            title=plain_text(item.get("title") or item["url"]),
            url=item["url"],
            source_type=SourceType.WEB,
            source_provider=self.id,
            original_text=plain_text(item.get(snippet) or ""),
            original_language=language,
            metadata={
                **raw_metadata(item),
                "provider_rank": rank,
                "search_page": page,
                "search_engine": self.id,
                "index_family": self.index_family,
                "lineage": "search_engine_snippet",
                "discovery": {
                    "provider": self.id,
                    "provider_rank": rank,
                    "query_variant": query.id,
                    "page": page,
                },
                "scope": "Web search snippet; destination page not retrieved or verified",
                **metadata,
            },
        )
