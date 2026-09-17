import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from tractor.core.deduplication import normalize_url
from tractor.sources import default_adapters
from tractor.storage.atomic import atomic_text


def validate_web_endpoint(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Use a server URL without credentials, query parameters, or fragments.")
    normalized = normalize_url(value)
    parts = urlsplit(normalized)
    if (parts.hostname or "").endswith(".onion"):
        raise ValueError("This setting accepts clearnet servers. Onion routing is separate.")
    if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS, or HTTP for a server running on this computer.")
    return normalized.rstrip("/")


def endpoint_origin(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


@dataclass
class Settings:
    sources: list[str] = field(default_factory=lambda: [a.id for a in default_adapters()])
    web_endpoint: str = ""

    @classmethod
    def load(cls, data_dir: Path) -> "Settings":
        try:
            data = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
            endpoint = validate_web_endpoint(data.get("web_endpoint", ""))
            valid = {a.id for a in default_adapters()} | ({"searxng"} if endpoint else set())
            selected = [key for key in data.get("sources", []) if key in valid]
            return cls(selected or [a.id for a in default_adapters()], endpoint)
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, data_dir: Path) -> None:
        self.web_endpoint = validate_web_endpoint(self.web_endpoint)
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with atomic_text(data_dir / "settings.json") as file:
            json.dump(asdict(self), file, indent=2)

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset({endpoint_origin(self.web_endpoint)} if self.web_endpoint else set())
