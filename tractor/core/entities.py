import hashlib
import re
import unicodedata
from urllib.parse import urlsplit

from tractor.core.models import Entity, SourceResult


def normalize_identifier(kind: str, value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    if kind == "domain":
        return value.lower().rstrip(".").encode("idna").decode("ascii")
    if kind == "doi":
        return re.sub(r"^(https?://(dx\.)?doi.org/|doi:\s*)", "", value, flags=re.I).lower()
    if kind == "email":
        local, domain = value.rsplit("@", 1)
        return local + "@" + domain.lower()
    return value


def make_entity(kind: str, value: str, result_id: str) -> Entity:
    normalized = normalize_identifier(kind, value)
    key = hashlib.sha256(f"{kind}:{normalized}".encode()).hexdigest()[:24]
    return Entity(f"entity:{key}", kind, value, normalized, [result_id])


def extract_entities(result: SourceResult) -> list[Entity]:
    identifiers = [("domain", urlsplit(result.url).hostname or "")]
    for kind in ("doi", "wikidata", "repository"):
        if result.metadata.get(kind):
            identifiers.append((kind, str(result.metadata[kind])))
    # These observations are exact identifiers, never inferred person identities.
    for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", result.original_text):
        identifiers.append(("email", email))
    return [
        make_entity(kind, value, result.id) for kind, value in dict.fromkeys(identifiers) if value
    ]
