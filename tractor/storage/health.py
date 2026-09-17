"""Bounded local attempt history; never transmitted to a provider."""

import statistics


def record_health(connection, investigation_id, attempt):
    if not attempt.finished_at or attempt.status in {"running", "pending", "skipped"}:
        return
    with connection:
        connection.execute(
            """INSERT OR REPLACE INTO provider_health VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                investigation_id,
                attempt.task_id,
                attempt.run_number,
                attempt.provider,
                attempt.status,
                attempt.duration_ms,
                attempt.error_category,
                attempt.rate_limit_events,
                attempt.unique_yield,
                attempt.duplicate_yield,
                attempt.finished_at,
            ),
        )
        connection.execute(
            """DELETE FROM provider_health WHERE provider=? AND rowid NOT IN
            (SELECT rowid FROM provider_health WHERE provider=? ORDER BY finished_at DESC LIMIT 200)
            """,
            (attempt.provider, attempt.provider),
        )


def provider_health(connection) -> dict:
    groups = {}
    for row in connection.execute(
        "SELECT provider, status, duration_ms, error_category, rate_limits, unique_yield, "
        "duplicate_yield, finished_at FROM provider_health ORDER BY finished_at DESC"
    ):
        groups.setdefault(row[0], []).append(row[1:])
    return {
        provider: {
            "attempts": len(rows),
            "success_rate": round(sum(r[0] == "success" for r in rows) / len(rows), 3),
            "median_latency_ms": statistics.median(r[1] for r in rows),
            "last_error_class": next((r[2] for r in rows if r[2]), None),
            "rate_limit_events": sum(r[3] for r in rows),
            "average_unique_yield": round(statistics.mean(r[4] for r in rows), 2),
            "duplicate_yield": sum(r[5] for r in rows),
            "last_success_at": next((r[6] for r in rows if r[0] == "success"), None),
            "last_status": rows[0][0],
        }
        for provider, rows in groups.items()
    }


def scheduling_score(health: dict) -> float:
    """A bounded tie-breaker after the first discovery pass; never an exclusion rule."""
    return round(
        min(1.0, health.get("success_rate", 0.5))
        + min(1.0, health.get("average_unique_yield", 0.0) / 15)
        - min(0.5, health.get("median_latency_ms", 0.0) / 120000),
        3,
    )
