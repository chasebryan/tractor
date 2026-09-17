import asyncio
import gzip
import json
from dataclasses import asdict
from html import escape
from unittest.mock import AsyncMock

import httpx
import pytest

from tractor.core.convergence import Budget
from tractor.core.engine import InvestigationEngine
from tractor.core.models import Investigation, QueryVariant, SourceResult
from tractor.network.client import NetworkClient, RequestStats, SourceUnavailable
from tractor.network.session import configured_adapters, network_session
from tractor.network.tor import TorClient, TorNetwork, TorRuntime, onion_host, validate_proxy
from tractor.settings import Settings, validate_onion_endpoint
from tractor.sources import default_adapters
from tractor.sources.base import SearchBatch, SearchContext
from tractor.sources.onion import TORCH_HOST, TORCH_URL, OnionSearxNG, TorchSearch, safe_onion_url
from tractor.storage.cache import ResponseCache

HOME = '<form name=P><input name=P value=""><input type=hidden name=tkn value=token></form>'


def page(query, offset=0, limit=2, *, more=True, invalid=False):
    rows = "".join(
        '<tr><td>rank</td><td><a href="'
        + ("https://example.org/" if invalid else TORCH_URL + f"/result/{i}")
        + '"><b>Research '
        + str(i)
        + "</b></a><small>Public <b>text</b> preview</small></td></tr>"
        for i in range(offset, offset + limit)
    )
    return (
        f'<form name=P><input name=P value="{escape(query, quote=True)}">'
        "<input type=hidden name=tkn value=token><input type=hidden name=xP value=parsed>"
        f"{offset + 1}-{offset + limit} of about 1,000 matches<table>{rows}</table>"
        + ('<input type=submit name="&gt;" value=Next>' if more else "")
        + '<script>doNotExecute()</script><iframe src="https://example.org/advert"></iframe></form>'
    )


class Index:
    def __init__(self, robots=404, policy="", output=None):
        self.calls = []
        self.robots = robots
        self.policy = policy
        self.output = output

    def __call__(self, request):
        self.calls.append(request)
        assert request.url.host == TORCH_HOST
        if request.url.path == "/robots.txt":
            return httpx.Response(self.robots, text=self.policy)
        params = request.url.params
        if not params.get("P"):
            return httpx.Response(200, text=HOME, headers={"content-type": "text/html"})
        assert params["tkn"] == "token"
        offset = int(params["TOPDOC"])
        if offset:
            assert params["xP"] == "parsed"
        html = (
            self.output
            if self.output is not None
            else page(params["P"], offset, int(params["HITSPERPAGE"]))
        )
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})


def client_for(handler, cache=None):
    client = TorClient(frozenset({TORCH_HOST}), transport=httpx.MockTransport(handler), cache=cache)
    client.limiter.wait = AsyncMock()
    return client


async def test_torch_real_form_contract_pagination_and_fresh_resume():
    index = Index()
    query = QueryVariant('privacy & "public"')
    async with client_for(index) as client:
        source = TorchSearch()
        first = await source.search(query, SearchContext(client, limit=2))
        resumed = await TorchSearch().search(
            query, SearchContext(client, limit=2, cursor=first.next_cursor)
        )
    assert first.next_cursor == "2" and resumed.next_cursor == "4"
    assert {r.url for r in first.results}.isdisjoint(r.url for r in resumed.results)
    assert all(r.source_type == "ONION" for r in first.results + resumed.results)
    assert all(r.original_text == "Public text preview" for r in first.results)
    assert all("destination page not retrieved" in r.metadata["scope"] for r in first.results)
    assert {r.url.path for r in index.calls} == {"/robots.txt", "/cgi-bin/omega/omega"}
    assert [r.url.params["TOPDOC"] for r in index.calls if "P" in r.url.params] == ["0", "0", "2"]


@pytest.mark.parametrize(
    "robots,policy",
    [
        (200, "User-agent: *\nDisallow: /cgi-bin/"),
        (200, "User-agent: *\nDisallow: /*?"),
        (403, ""),
        (500, ""),
        (200, "<html>challenge</html>"),
    ],
)
async def test_robots_denial_and_unavailable_policy_never_send_query(robots, policy, monkeypatch):
    monkeypatch.setattr("tractor.network.client.asyncio.sleep", AsyncMock())
    index = Index(robots, policy)
    async with client_for(index) as client:
        with pytest.raises(SourceUnavailable):
            await TorchSearch().search(QueryVariant("private query"), SearchContext(client))
    assert all(r.url.path == "/robots.txt" for r in index.calls)


@pytest.mark.parametrize(
    "output",
    [
        HOME,
        "<html>Log in</html>",
        '<form name=P><input name=P value="topic">Challenge</form>',
        page("topic", offset=5),
        page("topic", invalid=True),
    ],
)
async def test_torch_rejects_challenges_wrong_pages_and_non_onion_links(output):
    async with client_for(Index(output=output)) as client:
        with pytest.raises(SourceUnavailable):
            await TorchSearch().search(QueryVariant("topic"), SearchContext(client, limit=2))


async def test_torch_recognizes_empty_results_and_honors_crawl_delay():
    html = '<form name=P><input name=P value="topic">No documents match your query</form>'
    async with client_for(Index(200, "User-agent: *\nCrawl-delay: 6", output=html)) as client:
        batch = await TorchSearch().search(QueryVariant("topic"), SearchContext(client, limit=2))
        assert not batch.results and not batch.next_cursor and batch.total_available == 0
        assert any(call.args[1] == 6 for call in client.limiter.wait.call_args_list)


@pytest.mark.parametrize(
    "value",
    [
        "http://example.org",
        "http://short.onion",
        "http://" + "a" * 56 + ".onion",
        TORCH_URL + ":8080",
        "http://user:password@" + TORCH_HOST,
        "javascript:alert(1)",
    ],
)
def test_invalid_onion_urls_cannot_be_enabled(value):
    assert safe_onion_url(value) is None
    with pytest.raises(ValueError):
        validate_onion_endpoint(value)


def test_valid_onion_checksum_and_local_proxy_only():
    assert onion_host(TORCH_URL) == TORCH_HOST
    assert validate_onion_endpoint(TORCH_URL + "/") == TORCH_URL
    assert validate_proxy("socks5h://localhost:9150") == "socks5h://127.0.0.1:9150"
    for proxy in (
        "socks5://127.0.0.1:9050",
        "socks5h://remote.example:9050",
        "http://127.0.0.1:9050",
        "socks5h://user:pass@localhost:9050",
    ):
        with pytest.raises(ValueError):
            validate_proxy(proxy)


async def test_tor_redirect_cannot_escape_onion_allowlist():
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://api.github.com/test"})

    async with client_for(reply) as client:
        with pytest.raises(ValueError):
            await client.get_text(TORCH_URL)
    assert len(calls) == 1


async def test_compressed_html_cache_and_size_bound(database):
    calls = []

    def reply(request):
        calls.append(request)
        return httpx.Response(
            200,
            content=gzip.compress("<p>公開情報</p>".encode()),
            headers={"content-type": "text/html; charset=utf-8", "content-encoding": "gzip"},
        )

    stats = RequestStats()
    async with client_for(reply, ResponseCache(database.connection)) as client:
        assert await client.get_text(TORCH_URL, stats=stats) == "<p>公開情報</p>"
        assert await client.get_text(TORCH_URL, stats=stats) == "<p>公開情報</p>"
    assert len(calls) == stats.network == stats.cached == 1
    async with client_for(
        lambda _: httpx.Response(
            200, content=b"x" * (2 * 1024 * 1024 + 1), headers={"content-type": "text/html"}
        )
    ) as client:
        with pytest.raises(SourceUnavailable, match="size limit"):
            await client.get_text(TORCH_URL)


async def test_onion_metasearch_filters_before_local_pagination():
    def reply(request):
        assert request.url.params["categories"] == "onions"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": "https://example.org", "title": "Exclude"},
                    *[{"url": TORCH_URL + f"/{i}", "title": f"<b>Page {i}</b>"} for i in range(3)],
                ]
            },
        )

    async with client_for(reply) as client:
        source = OnionSearxNG(TORCH_URL)
        first = await source.search(QueryVariant("topic"), SearchContext(client, limit=2))
        second = await source.search(
            QueryVariant("topic"), SearchContext(client, limit=2, cursor=first.next_cursor)
        )
    assert len(first.results) == 2 and len(second.results) == 1
    assert first.next_cursor == "1:2" and second.next_cursor == "2:0"
    assert all("<b>" not in r.title for r in first.results)


def test_tor_defaults_migrate_unchanged_settings_and_preserve_optout(tmp_path):
    assert "torch" in Settings().sources
    (tmp_path / "settings.json").write_text(
        json.dumps({"sources": [a.id for a in default_adapters()]})
    )
    assert "torch" in Settings.load(tmp_path).sources
    custom = Settings(["github"], tor_proxy="socks5h://127.0.0.1:9150", tor_autostart=False)
    custom.save(tmp_path)
    assert Settings.load(tmp_path) == custom
    assert "torch" not in Settings.load(tmp_path).sources


async def test_existing_proxy_is_used_without_starting_or_stopping_process(tmp_path, monkeypatch):
    monkeypatch.setattr("tractor.network.tor.probe_socks", AsyncMock(return_value=True))
    spawn = AsyncMock()
    monkeypatch.setattr("tractor.network.tor.asyncio.create_subprocess_exec", spawn)
    runtime = TorRuntime(tmp_path)
    assert await runtime.ensure() == "socks5h://127.0.0.1:9050"
    await runtime.close()
    spawn.assert_not_called()
    assert runtime.process is None


class FakeTor:
    def __init__(self, bootstrap=True):
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(b"Opened Socks listener connection (ready) on 127.0.0.1:19800\n")
        if bootstrap:
            self.stdout.feed_data(b"Bootstrapped 100% (done): Done\n")
        self.returncode = None
        self.stopped = asyncio.Event()

    def terminate(self):
        self.returncode = 0
        self.stdout.feed_eof()
        self.stopped.set()

    def kill(self):
        self.terminate()

    async def wait(self):
        await self.stopped.wait()
        return self.returncode


@pytest.mark.parametrize("cancel", [False, True])
async def test_owned_tor_startup_and_cancellation_cleanup(tmp_path, monkeypatch, cancel):
    process = FakeTor(not cancel)
    monkeypatch.setattr("tractor.network.tor.probe_socks", AsyncMock(return_value=False))
    monkeypatch.setattr("tractor.network.tor.shutil.which", lambda _: "/usr/bin/tor")
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr("tractor.network.tor.asyncio.create_subprocess_exec", spawn)
    statuses = []
    runtime = TorRuntime(tmp_path / "tor", on_status=statuses.append)
    task = asyncio.create_task(runtime.ensure())
    if cancel:
        while runtime.reader_task is None:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        assert await task == "socks5h://127.0.0.1:19800"
        assert "Tor connection bootstrap: 100%" in statuses
    await runtime.close()
    assert process.returncode == 0
    assert "--ClientOnly" in spawn.call_args.args
    assert "shell" not in spawn.call_args.kwargs


async def test_missing_tor_fails_closed_without_touching_direct_network(tmp_path, monkeypatch):
    monkeypatch.setattr("tractor.network.tor.probe_socks", AsyncMock(return_value=False))
    monkeypatch.setattr("tractor.network.tor.shutil.which", lambda _: None)
    async with TorNetwork(frozenset({TORCH_HOST}), TorRuntime(tmp_path)) as client:
        with pytest.raises(SourceUnavailable, match="Start Tor Browser"):
            await client.get_text(TORCH_URL)
        assert client.client is None


async def test_engine_persists_tor_failures_and_direct_results_separately(database):
    class Direct:
        id, name, description = "direct", "Direct", "Fixture"

        async def search(self, query, context):
            assert context.client is direct
            return SearchBatch([SourceResult("topic", "https://example.org", "WEB", self.id)])

    class Onion:
        id, name, description, network = "onion", "Onion", "Fixture", "tor"

        async def search(self, query, context):
            assert context.client is tor
            raise SourceUnavailable("Tor unavailable for this test")

    direct, tor = object(), object()
    engine = InvestigationEngine(
        [Direct(), Onion()],
        direct,
        database,
        budget=Budget(max_variants=1),
        network_contexts={"tor": tor},
    )
    inv = await engine.run("topic")
    assert inv.unique_results and any(t.provider == "onion" for t in inv.pending_tasks)
    restored = database.load(inv.id)
    assert restored.coverage["tor_sources_attempted"] == 1
    assert restored.coverage["tor_sources_successful"] == 0
    assert any(
        a.network == "tor" and a.error == "Tor unavailable for this test" for a in restored.attempts
    )
    legacy = inv.to_dict()
    for attempt in legacy["attempts"]:
        attempt.pop("network")
    assert all(a.network == "clearnet" for a in Investigation.from_dict(legacy).attempts)


async def test_disabling_onion_sources_never_initializes_tor(tmp_path, monkeypatch):
    ensure = AsyncMock(side_effect=AssertionError("Tor must remain stopped"))
    monkeypatch.setattr(TorRuntime, "ensure", ensure)
    settings = Settings(["github"])
    adapters = configured_adapters(settings, default_adapters(), settings.sources)
    async with network_session(settings, adapters, tmp_path) as (direct, contexts):
        assert isinstance(direct, NetworkClient) and not direct.tor
        assert contexts == {}
    ensure.assert_not_called()


def test_onion_result_survives_serialization():
    result = SourceResult("Title", TORCH_URL, "ONION", "torch", metadata={"network": "tor"})
    assert SourceResult(**asdict(result)) == result


async def test_ui_displays_saved_onion_coverage_without_repeating_wordmark(qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel

    from tractor.core.models import Attempt, QueryPlan
    from tractor.ui.main_window import MainWindow

    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert (
        sum(
            label.text() == "TRACTOR" and label.isVisible() for label in window.findChildren(QLabel)
        )
        == 1
    )
    record = SourceResult("Public onion source", TORCH_URL, "ONION", "torch")
    inv = Investigation(
        "topic",
        QueryPlan("topic"),
        status="partial",
        results=[record],
        attempts=[
            Attempt("torch", "q", "topic", "en", 1, status="success", result_count=1, network="tor")
        ],
    )
    window.results.update_investigation(inv)
    window.pages.setCurrentIndex(1)
    window.resize(850, 640)
    qtbot.wait(20)
    assert window.width() == 850
    assert "1 unique onion results" in window.results.tor_status.text()
    card = window.results.card_widgets[record.id]
    assert card.badge.text() == "ONION"
    assert card.domain.toolTip() == TORCH_URL
    window.close()
