import re
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from tractor.core.models import QueryVariant, SourceResult
from tractor.network.client import NetworkContext, RequestStats


@dataclass
class SearchContext:
    client: NetworkContext
    limit: int = 15
    stats: RequestStats = field(default_factory=RequestStats)
    search_language: str | None = None
    requested_language: str = "auto"
    cursor: str | None = None
    page: int = 1
    languages: tuple[str, ...] = (
        "en",
        "es",
        "fr",
        "de",
        "ru",
        "ar",
        "zh",
        "ja",
        "pt",
        "uk",
        "hi",
        "bn",
        "ko",
        "it",
        "nl",
        "pl",
        "tr",
        "fa",
        "he",
        "id",
        "vi",
        "th",
        "sv",
        "fi",
        "el",
    )


@dataclass
class SearchBatch:
    results: list[SourceResult] = field(default_factory=list)
    variants: list[QueryVariant] = field(default_factory=list)
    truncated: bool = False
    next_cursor: str | None = None
    total_available: int | None = None
    warnings: list[str] = field(default_factory=list)
    partial: bool = False
    skipped_reason: str = ""


class SourceAdapter(Protocol):
    id: str
    name: str
    description: str

    async def search(self, query: QueryVariant, context: SearchContext) -> SearchBatch: ...


@dataclass(frozen=True)
class SearchOptions:
    language: str = "auto"
    region: str = ""
    category: str = "general"
    freshness: str = "any"
    after: str = ""
    before: str = ""
    results_per_domain: int = 2
    common_crawl_collection: str = ""
    mojeek_storage_allowed: bool = False

    def __post_init__(self):
        if self.language not in {"auto", "all"} and not re.fullmatch(
            r"[a-z]{2,3}(-[a-z]{2,4})?", self.language
        ):
            raise ValueError("Use auto, all, or a language code such as fr or zh-cn.")
        if self.region and not re.fullmatch(r"[A-Za-z]{2}", self.region):
            raise ValueError("Use a two-letter region code, or leave region blank.")
        if self.category not in {"general", "news"}:
            raise ValueError("Category must be general or news.")
        if self.freshness not in {"any", "day", "week", "month", "year", "custom"}:
            raise ValueError("Unsupported freshness choice.")
        if self.freshness == "custom":
            if date.fromisoformat(self.after) >= date.fromisoformat(self.before):
                raise ValueError("The beginning of a date range must precede its end.")
        if type(self.results_per_domain) is not int or not 1 <= self.results_per_domain <= 100:
            raise ValueError("Results per domain must be between 1 and 100.")
        if self.common_crawl_collection and not re.fullmatch(
            r"CC-MAIN-\d{4}-\d{2}", self.common_crawl_collection
        ):
            raise ValueError("Use a Common Crawl collection ID such as CC-MAIN-2025-30.")
        if type(self.mojeek_storage_allowed) is not bool:
            raise ValueError("Mojeek storage eligibility must be a boolean.")
