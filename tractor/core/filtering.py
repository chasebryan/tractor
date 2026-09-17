import calendar
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from tractor.core.models import Investigation, SourceResult


def date_bounds(value: str | None) -> tuple[date, date] | None:
    """Keep partial publication dates as ranges instead of inventing an exact day."""
    if not value:
        return None
    try:
        parts = value[:10].split("-")
        year = int(parts[0])
        if len(parts) == 1:
            return date(year, 1, 1), date(year, 12, 31)
        month = int(parts[1])
        if len(parts) == 2:
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        day = date.fromisoformat(value[:10])
        return day, day
    except (ValueError, TypeError):
        return None


@dataclass
class ResultFilter:
    text: str = ""
    source_type: str = ""
    provider: str = ""
    language: str = ""
    domain: str = ""
    region: str = ""
    entity_type: str = ""
    after: str = ""
    before: str = ""
    min_relevance: float = 0

    def apply(self, investigation: Investigation) -> list[SourceResult]:
        try:
            after = date.fromisoformat(self.after) if self.after else None
            before = date.fromisoformat(self.before) if self.before else None
        except ValueError:
            raise ValueError("Enter filter dates as YYYY-MM-DD.") from None
        if after and before and after > before:
            raise ValueError("The start date must be on or before the end date.")
        entity_kinds = {e.id: e.kind for e in investigation.entities}
        matches: list[SourceResult] = []
        for result in investigation.unique_results:
            if self.source_type and result.source_type != self.source_type:
                continue
            if self.provider and result.source_provider != self.provider:
                continue
            if self.language and result.original_language != self.language:
                continue
            host = (urlsplit(result.url).hostname or "").lower()
            domain = self.domain.strip().lower().rstrip(".")
            if domain and host != domain and not host.endswith("." + domain):
                continue
            if self.region and result.metadata.get("region") != self.region:
                continue
            if self.entity_type and not any(
                entity_kinds.get(e) == self.entity_type for e in result.entities
            ):
                continue
            if self.text.casefold() not in (result.title + " " + result.original_text).casefold():
                continue
            if result.relevance_score < self.min_relevance:
                continue
            published = date_bounds(result.published_at)
            if after and (not published or published[1] < after):
                continue
            if before and (not published or published[0] > before):
                continue
            matches.append(result)
        return matches
