import asyncio
import threading

from tractor.core.convergence import Budget
from tractor.core.engine import InvestigationEngine
from tractor.core.models import SourceResult
from tractor.network.client import NetworkClient, SourceUnavailable
from tractor.sources.base import SearchBatch


class Pages:
    id = "pages"

    def __init__(self, count=5):
        self.count = count
        self.visited = []

    async def search(self, query, context):
        page = int(context.cursor or 1)
        self.visited.append(page)
        await asyncio.sleep(0)
        return SearchBatch(
            [SourceResult(f"Acme page {page}", f"https://example.org/{page}", "DOCUMENT", self.id)],
            truncated=page < self.count,
            next_cursor=str(page + 1) if page < self.count else None,
        )


async def test_page_budget_persists_and_resumes_after_reopening(database):
    source = Pages()
    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            [source], client, database, budget=Budget(max_pages_per_query=2)
        ).run("Acme")
        assert source.visited == [1, 2]
        assert inv.status == "partial"
        assert inv.pending_tasks[0].cursor == "3"
        original_ids = {r.id for r in inv.results}
        resumed = await InvestigationEngine([source], client, database).run(
            "", resume=database.load(inv.id)
        )
    assert source.visited == [1, 2, 3, 4, 5]
    assert resumed.id == inv.id and resumed.runs == 2
    assert resumed.status == "complete" and not resumed.pending_tasks
    assert len(resumed.unique_results) == 5
    assert original_ids.issubset({r.id for r in resumed.results})
    assert [a.run_number for a in resumed.attempts] == [1, 1, 2, 2, 2]


async def test_failed_source_is_retried_without_repeating_successful_sources(database):
    healthy = Pages(1)

    class Flaky(Pages):
        id = "flaky"
        failing = True

        async def search(self, query, context):
            if self.failing:
                raise SourceUnavailable("HTTP 503")
            return await super().search(query, context)

    flaky = Flaky(1)
    async with NetworkClient() as client:
        inv = await InvestigationEngine([healthy, flaky], client, database).run("Acme")
        assert inv.status == "partial"
        assert {t.provider for t in inv.pending_tasks} == {"flaky"}
        flaky.failing = False
        inv = await InvestigationEngine([healthy, flaky], client, database).run("", resume=inv)
    assert inv.status == "complete"
    assert healthy.visited == [1]
    assert flaky.visited == [1]
    assert inv.coverage["sources_unavailable"] == 0
    assert inv.coverage["sources_with_errors"] == 1


async def test_cancelled_work_is_recovered_with_its_cursor(database):
    source = Pages()
    cancelled = threading.Event()

    def events(kind, value):
        if kind == "snapshot" and value["results"]:
            cancelled.set()

    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            [source], client, database, on_event=events, cancelled=cancelled
        ).run("Acme")
        assert inv.status == "cancelled"
        assert inv.pending_tasks[0].cursor == "2"
        resumed = await InvestigationEngine(
            [source], client, database, budget=Budget(max_pages_per_query=10)
        ).run("", resume=database.load(inv.id))
    assert resumed.status == "complete"
    assert source.visited == [1, 2, 3, 4, 5]


async def test_repeated_provider_pages_stop_with_explained_limit(database):
    class Repeating(Pages):
        async def search(self, query, context):
            batch = await super().search(query, context)
            batch.results[0].url = "https://example.org/repeated"
            return batch

    source = Repeating(100)
    async with NetworkClient() as client:
        inv = await InvestigationEngine([source], client, database).run("Acme")
    assert source.visited == [1, 2]
    assert len(inv.unique_results) == 1
    assert not inv.pending_tasks
    assert any("repeated page" in note for note in inv.limits)


async def test_one_active_request_per_provider_without_starving_other_sources(database):
    active = set()
    order = []

    class Fair(Pages):
        async def search(self, query, context):
            assert self.id not in active
            active.add(self.id)
            order.append(self.id)
            await asyncio.sleep(0.005)
            batch = await super().search(query, context)
            active.remove(self.id)
            return batch

    sources = [Fair(2), Fair(2), Fair(2)]
    for i, source in enumerate(sources):
        source.id = f"source{i}"
    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            sources, client, database, budget=Budget(concurrency=2)
        ).run("Acme")
    assert inv.status == "complete"
    assert set(order[:3]) == {s.id for s in sources}
    assert all(s.visited == [1, 2] for s in sources)


async def test_record_limit_retains_unfinished_page(database):
    source = Pages(10)
    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            [source], client, database, budget=Budget(max_results=2)
        ).run("Acme")
    assert len(inv.results) == 2
    assert inv.stop_reason == "Record budget reached"
    assert inv.pending_tasks[0].page == 3


async def test_invalid_urls_are_skipped_without_losing_valid_page_records(database):
    class Mixed(Pages):
        async def search(self, query, context):
            batch = await super().search(query, context)
            batch.results.append(SourceResult("Bad URL", "file:///etc/passwd", "WEB", self.id))
            return batch

    async with NetworkClient() as client:
        inv = await InvestigationEngine([Mixed(1)], client, database).run("Acme")
    assert len(inv.results) == 1
    assert inv.coverage["invalid_records_skipped"] == 1


async def test_refresh_has_separate_history_and_old_snapshots_survive(database):
    async with NetworkClient() as client:
        original = await InvestigationEngine([Pages(1)], client, database).run("Acme")
        refreshed = await InvestigationEngine([Pages(1)], client, database).run(
            "Acme", previous_id=original.id
        )
    assert original.id != refreshed.id
    assert refreshed.previous_investigation == original.id
    assert len(database.history()) == 2


async def test_changed_server_never_receives_saved_page_cursor(database):
    source = Pages(3)
    source.identity = "https://first.example/search"
    async with NetworkClient() as client:
        inv = await InvestigationEngine(
            [source], client, database, budget=Budget(max_pages_per_query=1)
        ).run("Acme")
        source.identity = "https://second.example/search"
        inv = await InvestigationEngine([source], client, database).run("", resume=inv)
    assert source.visited == [1]
    assert inv.pending_tasks[0].cursor == "2"
    assert "reconfigured" in inv.stop_reason
    assert any("configuration changed" in note for note in inv.limits)
