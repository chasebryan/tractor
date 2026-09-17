import asyncio
import threading

from tractor.core.convergence import Budget
from tractor.core.engine import InvestigationEngine
from tractor.core.models import QueryVariant, SourceResult
from tractor.network.client import NetworkClient
from tractor.sources.base import SearchBatch


class FixtureAdapter:
    id = "fixture"
    name = "Fixture"
    description = "Offline test source"

    async def search(self, query, context):
        await asyncio.sleep(0)
        result = SourceResult(
            query.value,
            "https://example.org/" + query.value.replace(" ", "-"),
            "DATASET",
            self.id,
            original_text="Documented source metadata.",
        )
        variants = []
        if query.source == "seed":
            variants = [
                QueryVariant(
                    "Northstar international",
                    source="entity_discovery",
                    language="fr",
                    parent_result=result.id,
                    evidence_urls=[result.url],
                    reason="Candidate label in a source.",
                )
            ]
        return SearchBatch([result], variants)


async def test_end_to_end_stream_pivot_store_reopen(database):
    snapshots = []
    async with NetworkClient() as client:
        engine = InvestigationEngine(
            [FixtureAdapter()],
            client,
            database,
            on_event=lambda kind, data: snapshots.append((kind, data)),
        )
        inv = await engine.run("Northstar")
    assert inv.status == "complete"
    assert inv.passes == 2
    assert len(inv.unique_results) == 2
    assert inv.coverage["secondary_pivots"] == 1
    assert inv.coverage["languages_searched"] == ["fr"]
    assert any(
        kind == "snapshot" and data["status"] == "running" and data["results"]
        for kind, data in snapshots
    )
    reopened = database.load(inv.id)
    assert reopened.to_dict() == inv.to_dict()
    child = next(r for r in inv.results if r.parent_result)
    assert len(child.discovery_path) == 5


async def test_provider_failure_preserves_other_sources(database):
    class Broken(FixtureAdapter):
        id = "broken"

        async def search(self, query, context):
            raise RuntimeError("secret-token-that-must-not-appear")

    async with NetworkClient() as client:
        inv = await InvestigationEngine([FixtureAdapter(), Broken()], client, database).run("Acme")
    assert inv.status == "partial"
    assert inv.results
    assert inv.coverage["sources_unavailable"] == 1
    assert "secret-token" not in str(inv.to_dict())


async def test_duplicates_kept_with_evidence(database):
    class Mirror(FixtureAdapter):
        id = "mirror"

    async with NetworkClient() as client:
        inv = await InvestigationEngine([FixtureAdapter(), Mirror()], client, database).run("Acme")
    assert len(inv.results) == 4
    assert len(inv.unique_results) == 2
    assert sum(e.kind == "duplicate_of" for e in inv.edges) == 2


async def test_cancellation_is_prompt_and_saves_partial(database):
    cancelled = threading.Event()

    class Slow(FixtureAdapter):
        id = "slow"

        async def search(self, query, context):
            await asyncio.sleep(60)

    def events(kind, data):
        if kind == "snapshot" and data["results"]:
            cancelled.set()

    async with NetworkClient() as client:
        inv = await asyncio.wait_for(
            InvestigationEngine(
                [FixtureAdapter(), Slow()], client, database, on_event=events, cancelled=cancelled
            ).run("Acme"),
            timeout=2,
        )
    assert inv.status == "cancelled"
    assert len(inv.results) == 1
    assert database.load(inv.id).status == "cancelled"
    assert next(a for a in inv.attempts if a.provider == "slow").status == "cancelled"


async def test_time_and_query_budgets(database):
    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            [FixtureAdapter()], client, database, budget=Budget(max_jobs=1)
        ).run("Acme")
    assert len(inv.attempts) == 1
    assert inv.stop_reason == "Query budget reached"

    class Slow(FixtureAdapter):
        async def search(self, query, context):
            await asyncio.sleep(60)

    async with NetworkClient() as client:
        inv = await asyncio.wait_for(
            InvestigationEngine([Slow()], client, database, budget=Budget(max_seconds=0.05)).run(
                "Acme"
            ),
            timeout=2,
        )
    assert inv.status == "partial"
    assert "Time budget" in inv.stop_reason


async def test_unattributed_pivots_are_not_searched(database):
    class Unattributed(FixtureAdapter):
        async def search(self, query, context):
            batch = await super().search(query, context)
            batch.variants = [QueryVariant("Unverified alias", parent_result="nonexistent")]
            return batch

    async with NetworkClient() as client:
        inv = await InvestigationEngine([Unattributed()], client, database).run("Acme")
    assert len(inv.plan.variants) == 1
