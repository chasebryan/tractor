"""Onion-only retrieval and an owned, cancellable local Tor runtime."""

import asyncio
import base64
import hashlib
import re
import shutil
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from tractor.core.deduplication import normalize_url
from tractor.network.client import NetworkClient, NetworkPolicyError, SourceUnavailable


def onion_host(value: str) -> str:
    host = (urlsplit(normalize_url(value)).hostname or "").lower()
    if not host.endswith(".onion"):
        raise ValueError("Use a v3 .onion address.")
    name = host.split(".")[-2]
    if not re.fullmatch(r"[a-z2-7]{56}", name):
        raise ValueError("Use a valid 56-character v3 onion address.")
    raw = base64.b32decode(name.upper())
    expected = hashlib.sha3_256(b".onion checksum" + raw[:32] + raw[34:]).digest()[:2]
    if raw[-1] != 3 or raw[32:34] != expected:
        raise ValueError("The onion address checksum is invalid.")
    return host


def validate_proxy(value: str) -> str:
    if not value.strip():
        return ""
    parts = urlsplit(value.strip())
    if (
        parts.scheme != "socks5h"
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
        or not parts.port
    ):
        raise ValueError("Use a local SOCKS proxy, for example socks5h://127.0.0.1:9050.")
    host = "[::1]" if parts.hostname == "::1" else "127.0.0.1"
    return f"socks5h://{host}:{parts.port}"


class TorClient(NetworkClient):
    """A dedicated pool: onion destinations only, remote DNS, no direct fallback."""

    def __init__(
        self,
        onion_hosts: frozenset[str],
        proxy: str = "socks5h://127.0.0.1:9050",
        *,
        cache=None,
        transport=None,
    ):
        if not onion_hosts or any(onion_host("http://" + host) != host for host in onion_hosts):
            raise ValueError("Register explicit v3 onion hosts.")
        super().__init__(
            cache,
            allowed_hosts=onion_hosts,
            proxy=validate_proxy(proxy),
            tor=True,
            timeout=httpx.Timeout(45, connect=25),
            transport=transport,
        )

    def validate(self, url: str) -> str:
        onion_host(url)
        return super().validate(url)


async def probe_socks(proxy: str, timeout: float = 1.5) -> bool:
    """Probe only a local SOCKS greeting; this is not a claim of Tor connectivity."""
    parts = urlsplit(validate_proxy(proxy))
    writer = None
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(parts.hostname, parts.port)
            writer.write(b"\x05\x01\x00")
            await writer.drain()
            return await reader.readexactly(2) == b"\x05\x00"
    except (OSError, TimeoutError, asyncio.IncompleteReadError):
        return False
    finally:
        if writer:
            writer.close()
            with suppress(OSError):
                await writer.wait_closed()


class TorRuntime:
    def __init__(
        self,
        data_dir: Path,
        proxy: str = "",
        autostart: bool = True,
        on_status=None,
        bootstrap_timeout: float = 90,
    ):
        self.data_dir = data_dir
        self.requested_proxy = validate_proxy(proxy)
        self.autostart = autostart
        self.on_status = on_status or (lambda *_: None)
        self.bootstrap_timeout = bootstrap_timeout
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task | None = None
        self.proxy = ""
        self.port = 0
        self.failure = ""
        self.ready = asyncio.Event()
        self.lock = asyncio.Lock()

    async def ensure(self) -> str:
        async with self.lock:
            if self.proxy:
                return self.proxy
            if self.failure:
                raise SourceUnavailable(self.failure)
            try:
                if self.requested_proxy:
                    if not await probe_socks(self.requested_proxy):
                        raise SourceUnavailable(
                            "Tor proxy is not reachable. Start Tor or check its port in Settings."
                        )
                    self.proxy = self.requested_proxy
                    self.on_status("Tor SOCKS proxy connected; contacting onion sources…")
                    return self.proxy
                for port in (9050, 9150):
                    candidate = f"socks5h://127.0.0.1:{port}"
                    if await probe_socks(candidate):
                        self.proxy = candidate
                        self.on_status(f"Using the local Tor SOCKS proxy on port {port}…")
                        return self.proxy
                executable = shutil.which("tor") if self.autostart else None
                if not executable:
                    raise SourceUnavailable(
                        "Tor is not running. Start Tor Browser, or install Tor and enable "
                        "automatic startup in Settings."
                    )
                self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                config = self.data_dir / "tractor-torrc"
                if not config.exists():
                    config.write_text("# Local client configuration.\n", encoding="utf-8")
                self.on_status("Starting Tor and building a connection…")
                self.process = await asyncio.create_subprocess_exec(
                    executable,
                    "-f",
                    str(config.resolve()),
                    "--DataDirectory",
                    str(self.data_dir.resolve()),
                    "--SocksPort",
                    "127.0.0.1:auto",
                    "--ClientOnly",
                    "1",
                    "--AvoidDiskWrites",
                    "1",
                    "--SafeLogging",
                    "1",
                    "--ControlPort",
                    "0",
                    "--Log",
                    "notice stdout",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                self.reader_task = asyncio.create_task(self._read_progress())
                try:
                    await asyncio.wait_for(self.ready.wait(), self.bootstrap_timeout)
                except TimeoutError:
                    raise SourceUnavailable(
                        "Tor did not finish connecting within 90 seconds. Check your "
                        "connection or use a connected Tor Browser."
                    ) from None
                if not self.port or self.process.returncode is not None or self.failure:
                    raise SourceUnavailable(
                        "Tor could not start. Another instance may be using its data "
                        "directory; check your Tor setup."
                    )
                self.proxy = f"socks5h://127.0.0.1:{self.port}"
                return self.proxy
            except SourceUnavailable as exc:
                self.failure = str(exc)
                await self.close()
                raise
            except OSError:
                self.failure = "Tor could not start. Check the executable and local data directory."
                await self.close()
                raise SourceUnavailable(self.failure) from None
            except asyncio.CancelledError:
                await self.close()
                raise

    async def _read_progress(self) -> None:
        assert self.process and self.process.stdout
        while line := await self.process.stdout.readline():
            text = line.decode("utf-8", errors="replace")
            port = re.search(r"Opened Socks listener.*127\.0\.0\.1:(\d+)", text)
            if port:
                self.port = int(port[1])
            progress = re.search(r"Bootstrapped (\d+)%", text)
            if progress:
                percent = int(progress[1])
                self.on_status(f"Tor connection bootstrap: {percent}%")
                if percent == 100:
                    self.ready.set()
        if not self.ready.is_set():
            self.failure = "Tor exited before it connected."
        self.ready.set()

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
            except ProcessLookupError:
                pass
        if self.reader_task and self.reader_task is not asyncio.current_task():
            self.reader_task.cancel()
            await asyncio.gather(self.reader_task, return_exceptions=True)
        self.proxy = ""


class TorNetwork:
    """Lazy startup lets ordinary sources run while Tor bootstraps."""

    tor = True

    def __init__(self, onion_hosts: frozenset[str], runtime: TorRuntime, cache=None):
        self.hosts, self.runtime, self.cache = onion_hosts, runtime, cache
        self.client: TorClient | None = None
        self.lock = asyncio.Lock()
        self.requests = asyncio.Semaphore(2)

    def validate(self, url: str) -> str:
        host = onion_host(url)
        if host not in self.hosts:
            raise NetworkPolicyError("Onion host is not registered for this investigation.")
        normalized = normalize_url(url)
        if urlsplit(normalized).port not in (None, 80, 443):
            raise NetworkPolicyError("Onion sources must use standard HTTP(S) ports.")
        return normalized

    async def _client(self) -> TorClient:
        async with self.lock:
            if not self.client:
                proxy = await self.runtime.ensure()
                self.client = TorClient(self.hosts, proxy, cache=self.cache)
            return self.client

    async def _get(self, method: str, url: str, *args, **kwargs):
        self.validate(url)
        client = await self._client()
        async with self.requests:
            try:
                async with asyncio.timeout(75):
                    return await getattr(client, method)(url, *args, **kwargs)
            except TimeoutError:
                raise SourceUnavailable(
                    "Onion source timed out through Tor; no direct fallback was used."
                ) from None

    async def get_json(self, url: str, *args, **kwargs):
        return await self._get("get_json", url, *args, **kwargs)

    async def get_text(self, url: str, *args, **kwargs):
        return await self._get("get_text", url, *args, **kwargs)

    async def close(self) -> None:
        if self.client:
            await self.client.close()
        await self.runtime.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
