import sqlite3

MIGRATIONS = [
    """
    CREATE TABLE investigations (
        id TEXT PRIMARY KEY, query TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, status TEXT NOT NULL, snapshot TEXT NOT NULL
    );
    CREATE TABLE records (
        investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
        kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY (investigation_id, kind, id)
    );
    CREATE INDEX history_updated ON investigations(updated_at DESC);
    CREATE TABLE cache (
        key TEXT PRIMARY KEY, fetched_at REAL NOT NULL, expires_at REAL NOT NULL,
        content_hash TEXT NOT NULL, headers TEXT NOT NULL, body BLOB NOT NULL
    );
    """,
]


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise RuntimeError("This database was created by a newer version of TRACTOR.")
    for index in range(version, len(MIGRATIONS)):
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + MIGRATIONS[index]
            + f"\nPRAGMA user_version={index + 1};\nCOMMIT;"
        )
