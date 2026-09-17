import re

from tractor.core.models import SourceResult


def score_result(result: SourceResult, seed: str) -> None:
    tokens = set(re.findall(r"\w+", seed.casefold()))
    title = set(re.findall(r"\w+", result.title.casefold()))
    body = set(re.findall(r"\w+", result.original_text.casefold()))
    overlap = lambda words: len(tokens & words) / max(len(tokens), 1)  # noqa: E731
    result.matched_keywords = sorted(tokens & (title | body))
    result.score_breakdown = {
        "title_token_overlap": round(40 * overlap(title), 2),
        "text_token_overlap": round(25 * overlap(body), 2),
        "exact_phrase_in_title": 20.0 if seed.casefold() in result.title.casefold() else 0.0,
        "stable_identifier": 5.0
        if any(result.metadata.get(k) for k in ("doi", "wikidata", "repository"))
        else 0.0,
        "traceable_discovery": 5.0 if result.discovery_path else 0.0,
        "original_record": 5.0 if not result.duplicate_of else 0.0,
    }
    result.relevance_score = round(sum(result.score_breakdown.values()), 2)
    # Evidence completeness is not a truth probability or an identity confidence.
    result.evidence_score = float(
        40 * bool(result.url)
        + 30 * bool(result.discovery_path)
        + 20 * bool(result.original_text)
        + 10 * bool(result.published_at)
    )
