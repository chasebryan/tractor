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
    """
    CREATE VIRTUAL TABLE investigation_search USING fts5(investigation_id UNINDEXED, content);
    INSERT INTO investigation_search(investigation_id, content)
    SELECT id, query || ' ' || COALESCE((
        SELECT group_concat(json_extract(value, '$.title') || ' ' ||
            substr(json_extract(value, '$.original_text'), 1, 12000), ' ')
        FROM json_each(snapshot, '$.results')
    ), '') FROM investigations;
    """,
    """
    CREATE TABLE provider_health (
        investigation_id TEXT NOT NULL, task_id TEXT NOT NULL, run_number INTEGER NOT NULL,
        provider TEXT NOT NULL, status TEXT NOT NULL, duration_ms INTEGER NOT NULL,
        error_category TEXT, rate_limits INTEGER NOT NULL, unique_yield INTEGER NOT NULL,
        duplicate_yield INTEGER NOT NULL, finished_at TEXT NOT NULL,
        PRIMARY KEY (investigation_id, task_id, run_number)
    );
    CREATE INDEX provider_health_recent ON provider_health(provider, finished_at DESC);
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
