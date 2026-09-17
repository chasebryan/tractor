from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    max_passes: int = 3
    max_variants: int = 12
    max_jobs: int = 48
    max_results_per_query: int = 15
    max_seconds: float = 180
    concurrency: int = 4

    def __post_init__(self) -> None:
        if any(
            v <= 0
            for v in (
                self.max_passes,
                self.max_variants,
                self.max_jobs,
                self.max_results_per_query,
                self.max_seconds,
                self.concurrency,
            )
        ):
            raise ValueError("Investigation budgets must be positive.")


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
