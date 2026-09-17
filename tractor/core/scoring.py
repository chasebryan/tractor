"""Transparent, corpus-aware ranking, including traceable foreign-language matches."""

import math
import re
import unicodedata
from collections import Counter

from tractor.core.models import Investigation, QueryVariant, SourceResult


def tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.findall(r"[\u3400-\u9fff\u3040-\u30ff]|[^\W_]+", value)


def _rank(results: list[SourceResult], seed: str, variants: list[QueryVariant]) -> None:
    corpus = [r for r in results if not r.duplicate_of]
    documents = {r.id: tokens(r.title + " " + r.original_text[:12000]) for r in results}
    frequency = Counter(t for r in corpus for t in set(documents[r.id]))
    average_length = sum(len(documents[r.id]) for r in corpus) / max(1, len(corpus)) or 1
    candidates = [(seed, "seed", 1.0)] + [
        (v.value, v.state, 0.85)
        for v in variants
        if v.value != seed and v.state not in {"seed", "rejected"}
    ]
    for result in results:
        title = set(tokens(result.title))
        body = set(tokens(result.original_text[:12000]))
        counts = Counter(documents[result.id])
        best: tuple[float, dict[str, float], str, str, set[str]] | None = None
        for query, state, strength in candidates:
            if state != "seed" and query not in result.matched_queries:
                continue
            terms = set(tokens(query))
            if not terms:
                continue
            title_overlap = len(title & terms) / len(terms)
            body_overlap = len(body & terms) / len(terms)
            bm25 = 0.0
            for term in terms:
                n = frequency[term]
                idf = math.log(1 + (len(corpus) - n + 0.5) / (n + 0.5))
                tf = counts[term]
                bm25 += (
                    idf
                    * (tf * 2.2)
                    / (tf + 1.2 * (0.25 + 0.75 * len(documents[result.id]) / average_length))
                )
            phrase = (
                " " + " ".join(tokens(query)) + " " in " " + " ".join(tokens(result.title)) + " "
            )
            components = {
                "title_relevance": round(35 * title_overlap * strength, 2),
                "text_relevance": round(20 * body_overlap * strength, 2),
                "title_phrase": round(20 * phrase * strength, 2),
                "term_rarity_bm25": round(15 * (1 - math.exp(-bm25 / len(terms))) * strength, 2),
                "traceable_discovery": 5.0 if result.discovery_path else 0.0,
                "stable_identifier": 5.0
                if any(result.metadata.get(k) for k in ("doi", "wikidata", "repository", "pmid"))
                else 0.0,
            }
            score = round(sum(components.values()), 2)
            candidate = (score, components, query, state, terms & (title | body))
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best:
            result.relevance_score, result.score_breakdown, basis, state, matched = best
            result.matched_keywords = sorted(matched)
            result.metadata["ranking"] = {
                "version": 2,
                "query": basis,
                "query_state": state,
                "note": "Candidate query matches are discounted; relevance is not a truth score.",
            }
        result.evidence_score = float(
            40 * bool(result.url)
            + 30 * bool(result.discovery_path)
            + 20 * bool(result.original_text)
            + 10 * bool(result.published_at)
        )


def rank_results(inv: Investigation) -> None:
    _rank(inv.results, inv.query, inv.plan.variants)


def score_result(result: SourceResult, seed: str) -> None:
    _rank([result], seed, [])
