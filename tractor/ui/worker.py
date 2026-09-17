import asyncio
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from tractor.core.engine import InvestigationEngine
from tractor.network.session import configured_adapters, network_session
from tractor.settings import Settings
from tractor.sources import default_adapters
from tractor.storage.cache import ResponseCache
from tractor.storage.database import Database


class InvestigationWorker(QThread):
    event = Signal(str, object)
    failed = Signal(str)

    def __init__(
        self,
        query: str,
        db_path: Path,
        enabled_sources: list[str],
        parent=None,
        *,
        web_endpoint: str = "",
        tor_proxy: str = "",
        tor_autostart: bool = True,
        onion_endpoint: str = "",
        resume_id: str | None = None,
        previous_id: str | None = None,
    ):
        super().__init__(parent)
        self.query = query
        self.db_path = db_path
        self.enabled_sources = enabled_sources
        self.web_endpoint = web_endpoint
        self.tor_proxy = tor_proxy
        self.tor_autostart = tor_autostart
        self.onion_endpoint = onion_endpoint
        self.resume_id = resume_id
        self.previous_id = previous_id
        self.cancelled = threading.Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def run(self) -> None:
        try:
            asyncio.run(self.investigate())
        except Exception as exc:
            self.failed.emit(
                f"Investigation stopped ({type(exc).__name__}). "
                "Previously saved evidence is available in History."
            )

    async def investigate(self) -> None:
        with Database(self.db_path) as database:
            settings = Settings(
                self.enabled_sources,
                self.web_endpoint,
                self.tor_proxy,
                self.tor_autostart,
                self.onion_endpoint,
            )
            adapters = configured_adapters(settings, default_adapters(), self.enabled_sources)
            async with network_session(
                settings,
                adapters,
                self.db_path.parent,
                None if self.previous_id else ResponseCache(database.connection),
                on_status=lambda message: self.event.emit("tor_status", message),
            ) as (client, contexts):
                engine = InvestigationEngine(
                    [a for a in adapters if a.id in self.enabled_sources],
                    client,
                    database,
                    on_event=self.event.emit,
                    cancelled=self.cancelled,
                    network_contexts=contexts,
                )
                await engine.run(
                    self.query,
                    resume=database.load(self.resume_id) if self.resume_id else None,
                    previous_id=self.previous_id,
                )
