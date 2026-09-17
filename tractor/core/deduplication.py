import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tractor.core.models import SourceResult

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username:
        raise ValueError("Source URLs must use HTTP(S) without credentials.")
    host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    port = parts.port
    if ":" in host:
        host = f"[{host}]"
    if port and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
        host += f":{port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING
    ]
    # Preserve path case, slash semantics, and parameter order (including repeated keys).
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))


def normalize_result(result: SourceResult) -> None:
    result.canonical_url = normalize_url(result.url)
    result.original_title = result.original_title or result.title
    result.original_text = result.original_text or result.excerpt
    result.content_hash = hashlib.sha256(result.original_text.encode()).hexdigest()
    result.excerpt = result.excerpt or result.original_text[:420]


def fingerprint_text(result: SourceResult) -> str:
    return " ".join(re.findall(r"\w+", result.original_text.casefold()))


def find_duplicate(result: SourceResult, existing: list[SourceResult]) -> tuple[str, str] | None:
    text = fingerprint_text(result)
    for other in existing:
        representative = other.duplicate_of or other.id
        if result.canonical_url == other.canonical_url:
            return representative, "canonical_url"
        # Tiny metadata snippets must not collapse unrelated documents.
        if len(text) >= 160 and result.content_hash == other.content_hash:
            return representative, "content_hash"
        other_text = fingerprint_text(other)
        if len(text) >= 250 and len(other_text) >= 250:
            if SequenceMatcher(None, text[:12000], other_text[:12000]).ratio() >= 0.94:
                return representative, "near_duplicate_text"
    return None
