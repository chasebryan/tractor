"""Shared desktop and command-line routing, with deterministic connection cleanup."""

from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from tractor.network.client import NetworkClient
from tractor.network.tor import TorNetwork, TorRuntime
from tractor.settings import Settings
from tractor.sources.catalog import catalog


def configured_adapters(settings: Settings, base: list, selected: list[str]) -> list:
    adapters = catalog(settings, base)
    missing = set(selected) - {a.id for a in adapters}
    if missing:
        raise ValueError(
            "Configure a server in Settings before enabling " + ", ".join(sorted(missing))
        )
    return [adapter for adapter in adapters if adapter.id in selected]


@asynccontextmanager
async def network_session(
    settings: Settings, adapters: list, data_dir: Path, cache=None, on_status=None
):
    async with AsyncExitStack() as stack:
        direct = await stack.enter_async_context(
            NetworkClient(cache, allowed_origins=settings.allowed_origins)
        )
        contexts = {}
        onions = frozenset(
            host
            for adapter in adapters
            if getattr(adapter, "network", "clearnet") == "tor"
            for host in adapter.onion_hosts
        )
        if onions:
            runtime = TorRuntime(
                data_dir / "tor", settings.tor_proxy, settings.tor_autostart, on_status
            )
            contexts["tor"] = await stack.enter_async_context(TorNetwork(onions, runtime, cache))
        yield direct, contexts
