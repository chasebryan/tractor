from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from pathlib import Path

from tractor.core.models import Investigation, now
from tractor.storage.migrations import migrate


class Database:
    """One connection per owning thread; all UI storage goes through this interface."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(str(path), timeout=10)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        migrate(self.connection)

    def save(self, inv: Investigation) -> None:
        inv.updated_at = now()
        data = inv.to_dict()
        with self.connection:
            self.connection.execute(
                """INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,
                status=excluded.status, snapshot=excluded.snapshot""",
                (
                    inv.id,
                    inv.query,
                    inv.created_at,
                    inv.updated_at,
                    inv.status,
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            groups = {
                "query": inv.plan.variants,
                "result": inv.results,
                "entity": inv.entities,
                "edge": inv.edges,
                "source_status": inv.attempts,
            }
            records = [
                (
                    inv.id,
                    kind,
                    getattr(item, "id", str(index)),
                    json.dumps(asdict(item), ensure_ascii=False),
                )
                for kind, items in groups.items()
                for index, item in enumerate(items)
            ]
            self.connection.executemany(
                "INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)", records
            )
            self.connection.execute(
                "DELETE FROM investigation_search WHERE investigation_id=?", (inv.id,)
            )
            self.connection.execute(
                "INSERT INTO investigation_search VALUES (?, ?)",
                (
                    inv.id,
                    inv.query
                    + "\n"
                    + "\n".join(r.title + " " + r.original_text[:12000] for r in inv.results),
                ),
            )

    def load(self, investigation_id: str) -> Investigation:
        row = self.connection.execute(
            "SELECT snapshot FROM investigations WHERE id=?", (investigation_id,)
        ).fetchone()
        if not row:
            raise KeyError(investigation_id)
        inv = Investigation.from_dict(json.loads(row[0]))
        if inv.status == "running":
            inv.status = "interrupted"
            inv.stop_reason = "The application stopped before this investigation completed."
        return inv

    def history(self, limit: int = 100, search: str = "") -> list[dict]:
        terms = re.findall(r"\w+", search, flags=re.UNICODE)[:30]
        where = ""
        parameters: list = []
        if terms:
            where = (
                "WHERE id IN (SELECT investigation_id FROM investigation_search "
                "WHERE investigation_search MATCH ?) "
            )
            parameters.append(" AND ".join('"' + term + '"*' for term in terms))
        parameters.append(limit)
        rows = self.connection.execute(
            "SELECT id, query, created_at, status, updated_at, "
            "COALESCE(json_extract(snapshot, '$.coverage.unique_results'), 0) "
            "FROM investigations " + where + "ORDER BY updated_at DESC LIMIT ?",
            parameters,
        ).fetchall()
        return [
            dict(
                zip(
                    ("id", "query", "created_at", "status", "updated_at", "results"),
                    row,
                    strict=True,
                )
            )
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
