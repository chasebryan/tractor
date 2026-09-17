"""Indexed duplicate grouping with explicit, inspectable matching reasons."""

import hashlib
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tractor.core.entities import normalize_identifier
from tractor.core.models import SourceResult

TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}
IDENTIFIERS = ("doi", "wikidata", "repository", "pmid")


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
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))


def normalize_result(result: SourceResult) -> None:
    result.canonical_url = normalize_url(result.url)
    result.original_title = result.original_title or result.title
    result.original_text = result.original_text or result.excerpt
    result.content_hash = hashlib.sha256(result.original_text.encode()).hexdigest()
    result.excerpt = result.excerpt or result.original_text[:420]


def fingerprint_text(result: SourceResult) -> str:
    return " ".join(re.findall(r"\w+", result.original_text.casefold()))


def identifiers(result: SourceResult) -> dict[str, str]:
    return {
        kind: normalize_identifier(kind, str(result.metadata[kind])).casefold()
        for kind in IDENTIFIERS
        if result.metadata.get(kind)
    }


def shingles(text: str) -> tuple[bytes, ...]:
    words = text[:12000].split()[:2000]
    return tuple(
        sorted(
            {
                hashlib.blake2b(" ".join(words[i : i + 5]).encode(), digest_size=8).digest()
                for i in range(max(0, len(words) - 4))
            }
        )[:16]
    )


class DuplicateIndex:
    def __init__(self, results: list[SourceResult] | None = None):
        self.urls: dict[str, SourceResult] = {}
        self.hashes: dict[str, list[SourceResult]] = defaultdict(list)
        self.hash_common_identifiers: dict[str, set[str]] = {}
        self.record_identifiers: dict[str, dict[str, str]] = {}
        self.identifiers: dict[tuple[str, str], SourceResult] = {}
        self.buckets: dict[bytes, set[str]] = defaultdict(set)
        self.records: dict[str, SourceResult] = {}
        self.texts: dict[str, str] = {}
        for result in results or []:
            self.add(result)

    def add(self, result: SourceResult) -> None:
        self.urls.setdefault(result.canonical_url, result)
        text = fingerprint_text(result)
        self.records[result.id] = result
        self.texts[result.id] = text
        values = identifiers(result)
        self.record_identifiers[result.id] = values
        for item in values.items():
            self.identifiers.setdefault(item, result)
        if len(text) >= 160:
            self.hashes[result.content_hash].append(result)
            self.hash_common_identifiers.setdefault(
                result.content_hash, set(values)
            ).intersection_update(values)
        if len(text) >= 250:
            for shingle in shingles(text):
                self.buckets[shingle].add(result.id)

    @staticmethod
    def match(result: SourceResult, reason: str) -> tuple[str, str]:
        return result.duplicate_of or result.id, reason

    def find(self, result: SourceResult) -> tuple[str, str] | None:
        values = identifiers(result)

        def compatible(other: SourceResult) -> bool:
            previous = self.record_identifiers[other.id]
            if any(values[key] != previous[key] for key in values.keys() & previous.keys()):
                return False
            # A metadata-poor copy must not bridge conflicting identifiers into one group.
            representative = self.record_identifiers.get(other.duplicate_of or other.id, previous)
            return all(
                values[key] == representative[key] for key in values.keys() & representative.keys()
            )

        if result.canonical_url in self.urls:
            return self.match(self.urls[result.canonical_url], "canonical_url")
        for identifier in values.items():
            other = self.identifiers.get(identifier)
            if other and compatible(other):
                return self.match(other, "stable_identifier:" + identifier[0])
        text = fingerprint_text(result)
        common = self.hash_common_identifiers.get(result.content_hash, set()) & values.keys()
        impossible = any((key, values[key]) not in self.identifiers for key in common)
        if len(text) >= 160 and not impossible:
            for other in self.hashes.get(result.content_hash, []):
                if compatible(other):
                    return self.match(other, "content_hash")
        if len(text) < 250:
            return None
        candidates = Counter(record_id for key in shingles(text) for record_id in self.buckets[key])
        # At most 32 expensive comparisons; exact identifiers and hashes have no candidate cap.
        for record_id, count in candidates.most_common(32):
            other = self.records[record_id]
            other_text = self.texts[record_id]
            if count < 2 or not compatible(other):
                continue
            if min(len(text), len(other_text)) / max(len(text), len(other_text)) < 0.88:
                continue
            if SequenceMatcher(None, text[:12000], other_text[:12000]).ratio() >= 0.94:
                return self.match(other, "near_duplicate_text")
        return None


def find_duplicate(result: SourceResult, existing: list[SourceResult]) -> tuple[str, str] | None:
    return DuplicateIndex(existing).find(result)
