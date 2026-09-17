from dataclasses import dataclass, field
from typing import Protocol

from tractor.core.models import QueryVariant, SourceResult
from tractor.network.client import NetworkClient, RequestStats


@dataclass
class SearchContext:
    client: NetworkClient
    limit: int = 15
    stats: RequestStats = field(default_factory=RequestStats)
    search_language: str | None = None
    languages: tuple[str, ...] = ("en", "es", "fr", "de", "ru", "ar", "zh", "ja", "pt", "uk")


@dataclass
class SearchBatch:
    results: list[SourceResult] = field(default_factory=list)
    variants: list[QueryVariant] = field(default_factory=list)
    truncated: bool = False


class SourceAdapter(Protocol):
    id: str
    name: str
    description: str

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch: ...
