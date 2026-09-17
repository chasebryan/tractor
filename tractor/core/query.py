import re
import unicodedata

from tractor.core.models import AliasState, QueryPlan, QueryVariant
from tractor.language.detect import detect_language
from tractor.language.transliterate import transliterate


def normalize_query(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        " " if c.isspace() else c
        for c in value
        if c.isspace() or not unicodedata.category(c).startswith("C")
    )
    value = " ".join(value.split()).strip()
    if not value:
        raise ValueError("Enter a subject to investigate.")
    if len(value) > 240:
        raise ValueError("Use a query of 240 characters or fewer.")
    return value


def add_variant(plan: QueryPlan, candidate: QueryVariant, limit: int = 12) -> bool:
    try:
        candidate.value = normalize_query(candidate.value)
    except ValueError:
        return False
    existing = next(
        (v for v in plan.variants if v.value.casefold() == candidate.value.casefold()), None
    )
    if existing:
        existing.evidence_urls = list(
            dict.fromkeys(existing.evidence_urls + candidate.evidence_urls)
        )
        # Multiple URLs alone do not establish independent corroboration.
        return False
    if len(plan.variants) >= limit or candidate.state == AliasState.REJECTED:
        return False
    plan.variants.append(candidate)
    return True


def build_plan(value: str, limit: int = 12) -> QueryPlan:
    seed = normalize_query(value)
    language = detect_language(seed)
    plan = QueryPlan(
        seed,
        [
            QueryVariant(
                seed,
                language=language,
                state=AliasState.SEED,
                reason="User-supplied search subject.",
            )
        ],
    )
    romanized = transliterate(seed)
    if romanized.casefold() != seed.casefold():
        add_variant(
            plan,
            QueryVariant(
                romanized,
                source="transliteration",
                language=language,
                reason="Mechanical Latin-script transliteration; an unverified spelling candidate.",
            ),
            limit,
        )
    for pattern, replacement in (
        (r"\bLtd\.?$", "Limited"),
        (r"\bLimited$", "Ltd"),
        (r"\bCorp\.?$", "Corporation"),
    ):
        expanded = re.sub(pattern, replacement, seed, flags=re.IGNORECASE)
        if expanded != seed:
            add_variant(
                plan,
                QueryVariant(
                    expanded,
                    source="spelling_variant",
                    language=language,
                    reason="Expanded legal suffix; a search hypothesis, not a confirmed alias.",
                ),
                limit,
            )
    return plan
