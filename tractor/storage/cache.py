import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CachedResponse:
    body: bytes
    headers: dict[str, str]
    fetched_at: float


class ResponseCache:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def get(self, key: str) -> CachedResponse | None:
        row = self.connection.execute(
            "SELECT body, headers, fetched_at FROM cache WHERE key=? AND expires_at>?",
            (key, time.time()),
        ).fetchone()
        return CachedResponse(row[0], json.loads(row[1]), row[2]) if row else None

    def put(self, key: str, body: bytes, headers: dict[str, str], ttl: float) -> None:
        control = headers.get("cache-control", "").lower()
        if "no-store" in control or "no-cache" in control or "private" in control:
            return
        import re

        max_age = re.search(r"max-age=(\d+)", control)
        if max_age:
            ttl = min(ttl, float(max_age.group(1)))
        if ttl <= 0:
            return
        timestamp = time.time()
        safe_headers = {
            k: v
            for k, v in headers.items()
            if k in {"content-type", "cache-control", "etag", "last-modified"}
        }
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    timestamp,
                    timestamp + ttl,
                    hashlib.sha256(body).hexdigest(),
                    json.dumps(safe_headers),
                    body,
                ),
            )
            self.connection.execute("DELETE FROM cache WHERE expires_at<?", (timestamp,))
            # A bounded cache keeps long-lived desktop installs from growing indefinitely.
            self.connection.execute(
                "DELETE FROM cache WHERE key IN (SELECT key FROM cache "
                "ORDER BY fetched_at DESC LIMIT -1 OFFSET 500)"
            )
