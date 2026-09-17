import re
import unicodedata

from tractor.core.models import AliasState, QueryPlan, QueryVariant
from tractor.language.detect import detect_language
from tractor.language.script import detect_script
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
    if candidate.source != "seed" and candidate.kind == "seed":
        candidate.kind = "discovered_alias" if candidate.parent_result else "mechanical_variant"
        candidate.origin = candidate.source
    candidate.script = detect_script(candidate.value)
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
                script=detect_script(seed),
            )
        ],
    )
    # Reserve at least half of the normal frontier for actual source-backed discoveries.
    limit = min(limit, max(2, limit // 2), 6)
    romanized = transliterate(seed)
    if romanized.casefold() != seed.casefold():
        add_variant(
            plan,
            QueryVariant(
                romanized,
                source="transliteration",
                language=language,
                reason="Mechanical Latin-script transliteration; an unverified spelling candidate.",
                transliteration_of=plan.variants[0].id,
            ),
            limit,
        )
    for pattern, replacement in (
        (r"\bLtd\.?$", "Limited"),
        (r"\bLimited$", "Ltd"),
        (r"\bCorp\.?$", "Corporation"),
        (r"\bCorporation$", "Corp"),
        (r"\bInc\.?$", "Incorporated"),
        (r"\bIncorporated$", "Inc"),
        (r"\bLLC$", "Limited Liability Company"),
        (r"\bGmbH$", "Gesellschaft mit beschränkter Haftung"),
        (r"\bS\.?A\.?$", "SA"),
        (r"\bPte\.? Ltd\.?$", "Private Limited"),
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
    candidates = []
    if romanized.casefold() != seed.casefold():
        alternate = re.sub(r"kh", "h", romanized, flags=re.IGNORECASE)
        candidates.append((alternate, "Alternative mechanical romanization; not a verified alias."))
    if not re.match(r"https?://", seed):
        punctuation = re.sub(r"[.‐‑–—'’]", " ", seed)
        candidates.append((punctuation, "Punctuation spacing candidate; identity unverified."))
    if re.fullmatch(r"@[\w.-]{2,64}", seed):
        candidates.append((seed[1:], "Handle without its prefix; a search hypothesis."))
    words = seed.split()
    if 2 <= len(words) <= 5 and all(word[:1].isupper() and word.isalpha() for word in words):
        candidates.append(
            (
                " ".join([word[0] + "." for word in words[:-1]] + words[-1:]),
                "Initials candidate; not evidence of a shared identity.",
            )
        )
        if len(words) >= 3:
            candidates.append(
                (
                    "".join(word[0] for word in words),
                    "Acronym candidate; may refer to unrelated subjects.",
                )
            )
    for candidate, reason in candidates:
        add_variant(
            plan,
            QueryVariant(candidate, source="mechanical", language=language, reason=reason),
            limit,
        )
    if 2 <= len(words) <= 8 and not any(char in seed for char in '"/:@'):
        add_variant(
            plan,
            QueryVariant(
                '"' + seed + '"',
                source="quoted_phrase",
                language=language,
                kind="provider_hint",
                origin="query_planner",
                reason="Exact-phrase hint, issued only to supporting providers.",
            ),
            limit,
        )
    return plan
