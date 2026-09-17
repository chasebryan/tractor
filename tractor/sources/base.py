from dataclasses import dataclass, field
from typing import Protocol

from tractor.core.models import QueryVariant, SourceResult
from tractor.network.client import NetworkContext, RequestStats


@dataclass
class SearchContext:
    client: NetworkContext
    limit: int = 15
    stats: RequestStats = field(default_factory=RequestStats)
    search_language: str | None = None
    cursor: str | None = None
    page: int = 1
    languages: tuple[str, ...] = ("en", "es", "fr", "de", "ru", "ar", "zh", "ja", "pt", "uk")


@dataclass
class SearchBatch:
    results: list[SourceResult] = field(default_factory=list)
    variants: list[QueryVariant] = field(default_factory=list)
    truncated: bool = False
    next_cursor: str | None = None
    total_available: int | None = None


class SourceAdapter(Protocol):
    id: str
    name: str
    description: str

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch: ...
