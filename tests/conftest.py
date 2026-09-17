import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpcore
import pytest

from tractor.core.models import Investigation, QueryPlan, SourceResult
from tractor.storage.database import Database


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch, request):
    if request.node.get_closest_marker("integration"):
        return

    async def reject(*args, **kwargs):
        raise AssertionError("Unit tests must use a mocked HTTP transport")

    monkeypatch.setattr(httpcore.AsyncConnectionPool, "handle_async_request", reject)


@pytest.fixture
def database(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        yield db


@pytest.fixture
def result():
    return SourceResult(
        "Northstar Mining annual report",
        "https://example.org/report",
        "DOCUMENT",
        "test",
        original_text="Northstar Mining annual report, 2024.",
        published_at="2024-01-01",
        original_language="en",
    )


@pytest.fixture
def investigation(result):
    inv = Investigation("Northstar Mining", QueryPlan("Northstar Mining"), status="complete")
    inv.results.append(result)
    return inv
