import math
from dataclasses import dataclass

BUDGET_LIMITS = {
    "max_passes": (1, 8),
    "max_variants": (1, 100),
    "max_jobs": (1, 1000),
    "max_results_per_query": (1, 100),
    "max_seconds": (0.01, 3600),
    "concurrency": (1, 12),
    "max_pages_per_query": (1, 100),
    "max_results": (1, 10000),
}


@dataclass(frozen=True)
class Budget:
    max_passes: int = 3
    max_variants: int = 12
    max_jobs: int = 72
    max_results_per_query: int = 15
    max_seconds: float = 240
    concurrency: int = 6
    max_pages_per_query: int = 3
    max_results: int = 3000

    def __post_init__(self) -> None:
        for name, (low, high) in BUDGET_LIMITS.items():
            value = getattr(self, name)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
                or name != "max_seconds"
                and type(value) is not int
            ):
                raise ValueError(f"{name} must be positive and between {low} and {high}.")


def convergence_reason(
    pass_number: int, new_results: int, pending: int, jobs: int, budget: Budget
) -> str | None:
    if jobs >= budget.max_jobs:
        return "Query budget reached"
    if pass_number >= budget.max_passes:
        return "Pass budget reached"
    if pending == 0:
        return "No unsearched, evidence-backed variants remain"
    if new_results == 0:
        return "No new unique results in the last pass"
    return None
