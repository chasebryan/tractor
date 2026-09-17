"""In-memory secrets with environment credentials and an injectable secure-store interface."""

import os
import threading
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote, quote_plus

PROVIDER_ENV = {
    name: f"TRACTOR_{name.upper()}_API_KEY" for name in ("brave", "mojeek", "kagi", "marginalia")
}
_SECRETS: set[str] = set()
_LOCK = threading.RLock()


def register_secret(value: str) -> None:
    if value and value != "public":
        with _LOCK:
            _SECRETS.update((value, quote(value, safe=""), quote_plus(value)))


def redact(value):
    """Last-line defense for provider echoes, persisted data, exports and log fields."""
    if isinstance(value, str):
        with _LOCK:
            for secret in sorted(_SECRETS, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {redact(str(k)): redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def redact_bytes(value: bytes) -> bytes:
    # Preserve original response encoding while removing ASCII/UTF-8 token echoes.
    with _LOCK:
        for secret in sorted(_SECRETS, key=len, reverse=True):
            value = value.replace(secret.encode(), b"[REDACTED]")
    return value


class SecureStore(Protocol):
    def get(self, provider: str) -> str | None: ...


@dataclass(frozen=True)
class Credential:
    value: str = field(repr=False)
    source: str = "environment"

    def __post_init__(self):
        register_secret(self.value)


class Credentials:
    def __init__(self, secure_store: SecureStore | None = None):
        self.secure_store = secure_store
        # Register all configured values even when the provider is disabled.
        for name in PROVIDER_ENV.values():
            register_secret(os.environ.get(name, ""))

    def get(self, provider: str) -> Credential | None:
        name = PROVIDER_ENV.get(provider)
        value = os.environ.get(name, "").strip() if name else ""
        if value:
            if "\n" in value or "\r" in value or len(value) > 4096:
                return None
            return Credential(value)
        if self.secure_store:
            try:
                value = self.secure_store.get(provider)
            except Exception:
                value = None
            if value and "\n" not in value and "\r" not in value:
                return Credential(value, "secure store")
        return Credential("public", "shared development key") if provider == "marginalia" else None

    def status(self, provider: str) -> str:
        credential = self.get(provider)
        if not credential:
            return "Credential missing"
        return "Shared development key" if credential.value == "public" else "Configured"


@dataclass(frozen=True)
class RequestAuth:
    origin: str
    credential: Credential = field(repr=False)
    header: str = "Authorization"
    prefix: str = ""
    query_parameter: str = ""
