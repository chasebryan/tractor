from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict

from tractor.analysis.relationships import correlate
from tractor.core.convergence import Budget, convergence_reason
from tractor.core.deduplication import find_duplicate, normalize_result
from tractor.core.models import Attempt, Edge, Investigation, QueryVariant
from tractor.core.provenance import record_discovery
from tractor.core.query import add_variant, build_plan
from tractor.core.scoring import score_result
from tractor.language.detect import detect_language
from tractor.network.client import NetworkClient
from tractor.sources.base import SearchBatch, SearchContext, SourceAdapter
from tractor.storage.database import Database

logger = logging.getLogger("tractor.investigation")
EventHandler = Callable[[str, object], None]


class InvestigationEngine:
    def __init__(
        self,
        adapters: list[SourceAdapter],
        client: NetworkClient,
        database: Database,
        budget: Budget | None = None,
        on_event: EventHandler | None = None,
        cancelled: threading.Event | None = None,
    ):
        if not adapters:
            raise ValueError("Enable at least one source.")
        if len({a.id for a in adapters}) != len(adapters):
            raise ValueError("Source IDs must be unique.")
        self.adapters = adapters
        self.client = client
        self.database = database
        self.budget = budget or Budget()
        self.on_event = on_event or (lambda *_: None)
        self.cancelled = cancelled or threading.Event()
        self._semaphore = asyncio.Semaphore(self.budget.concurrency)

    async def _search(
        self, adapter: SourceAdapter, query: QueryVariant, inv: Investigation
    ) -> tuple[Attempt, SearchBatch]:
        async with self._semaphore:
            attempt = Attempt(adapter.id, query.id, query.value, query.language, inv.passes)
            context = SearchContext(self.client, self.budget.max_results_per_query)
            inv.attempts.append(attempt)
            started = time.monotonic()
            try:
                batch = await adapter.search(query, context)
                attempt.status = "success"
                attempt.result_count = len(batch.results)
                attempt.truncated = batch.truncated
                return attempt, batch
            except asyncio.CancelledError:
                attempt.status = "cancelled"
                raise
            except Exception as exc:
                attempt.status = "error"
                # Never log URLs, headers, credentials, or raw provider error bodies.
                from tractor.network.client import SourceUnavailable

                attempt.error = (
                    str(exc) if isinstance(exc, SourceUnavailable) else type(exc).__name__
                )
                return attempt, SearchBatch()
            finally:
                attempt.language = context.search_language or query.language
                attempt.duration_ms = int((time.monotonic() - started) * 1000)
                attempt.cached_requests = context.stats.cached
                attempt.network_requests = context.stats.network
                logger.info(
                    "source_attempt",
                    extra={
                        "investigation_id": inv.id,
                        "adapter": adapter.id,
                        "query_variant": query.id,
                        "duration_ms": attempt.duration_ms,
                        "result_count": attempt.result_count,
                        "error_category": attempt.error,
                        "status": attempt.status,
                    },
                )

    def _accept(self, inv: Investigation, query: QueryVariant, batch: SearchBatch) -> None:
        accepted_ids: set[str] = set()
        for result in batch.results[: self.budget.max_results_per_query]:
            try:
                normalize_result(result)
            except (ValueError, UnicodeError):
                continue
            accepted_ids.add(result.id)
            record_discovery(inv, query, result)
            if result.original_language == "und":
                result.original_language = detect_language(result.original_text)
            duplicate = find_duplicate(result, inv.results)
            if duplicate:
                result.duplicate_of, reason = duplicate
                inv.edges.append(
                    Edge(
                        result.id,
                        result.duplicate_of,
                        "duplicate_of",
                        [result.id],
                        confidence=0.94 if reason == "near_duplicate_text" else 1.0,
                        state="inference" if reason == "near_duplicate_text" else "observation",
                        explanation=reason,
                    )
                )
                original = next(r for r in inv.results if r.id == result.duplicate_of)
                original.matched_queries = list(
                    dict.fromkeys(original.matched_queries + result.matched_queries)
                )
            score_result(result, inv.query)
            inv.results.append(result)
            correlate(inv, result)
        for variant in batch.variants:
            if variant.parent_result not in accepted_ids or not variant.evidence_urls:
                continue
            if add_variant(inv.plan, variant, self.budget.max_variants):
                inv.edges.append(
                    Edge(
                        variant.parent_result,
                        variant.id,
                        "candidate_alias",
                        [variant.parent_result],
                        confidence=0.5,
                        state="inference",
                        explanation=variant.reason,
                    )
                )

    def _checkpoint(self, inv: Investigation) -> None:
        self.database.save(inv)
        self.on_event("snapshot", inv.to_dict())

    async def run(self, value: str) -> Investigation:
        plan = build_plan(value, self.budget.max_variants)
        inv = Investigation(plan.seed, plan, budget=asdict(self.budget))
        for variant in plan.variants:
            inv.edges.append(Edge(inv.id, variant.id, "search_variant", explanation=variant.reason))
        self._checkpoint(inv)
        started = time.monotonic()
        searched: set[str] = set()
        pending: set[asyncio.Task] = set()
        try:
            for pass_number in range(1, self.budget.max_passes + 1):
                inv.passes = pass_number
                self.on_event("status", f"Searching public sources · pass {pass_number}")
                frontier = [
                    v for v in plan.variants if v.id not in searched and v.state != "rejected"
                ]
                jobs = [(adapter, query) for query in frontier for adapter in self.adapters]
                jobs = jobs[: max(0, self.budget.max_jobs - len(inv.attempts))]
                query_map = {query.id: query for _, query in jobs}
                before = len(inv.unique_results)
                pending = {
                    asyncio.create_task(self._search(adapter, query, inv))
                    for adapter, query in jobs
                }
                while pending:
                    if self.cancelled.is_set():
                        inv.status = "cancelled"
                        inv.stop_reason = "Cancelled by user; collected evidence retained"
                        break
                    if time.monotonic() - started >= self.budget.max_seconds:
                        inv.status = "partial"
                        inv.stop_reason = "Time budget reached; collected evidence retained"
                        break
                    done, pending = await asyncio.wait(
                        pending, timeout=0.15, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        attempt, batch = task.result()
                        self._accept(inv, query_map[attempt.query_id], batch)
                        self._checkpoint(inv)
                if inv.stop_reason:
                    break
                searched.update(query_map)
                new_count = len(inv.unique_results) - before
                inv.pass_yields.append(new_count)
                reason = convergence_reason(
                    pass_number,
                    new_count,
                    sum(v.id not in searched and v.state != "rejected" for v in plan.variants),
                    len(inv.attempts),
                    self.budget,
                )
                if reason:
                    inv.stop_reason = reason
                    break
            if inv.status == "running":
                successes = sum(a.status == "success" for a in inv.attempts)
                errors = sum(a.status == "error" for a in inv.attempts)
                inv.status = "failed" if not successes else "partial" if errors else "complete"
        except asyncio.CancelledError:
            inv.status = "cancelled"
            inv.stop_reason = "Investigation interrupted; collected evidence retained"
            raise
        except Exception:
            inv.status = "failed"
            inv.stop_reason = "Unexpected investigation error"
            raise
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self._checkpoint(inv)
        self.on_event("status", inv.stop_reason)
        return inv
