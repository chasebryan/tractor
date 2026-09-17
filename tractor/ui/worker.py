import asyncio
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from tractor.core.engine import InvestigationEngine
from tractor.network.client import NetworkClient
from tractor.sources import default_adapters
from tractor.storage.cache import ResponseCache
from tractor.storage.database import Database


class InvestigationWorker(QThread):
    event = Signal(str, object)
    failed = Signal(str)

    def __init__(self, query: str, db_path: Path, enabled_sources: list[str], parent=None):
        super().__init__(parent)
        self.query = query
        self.db_path = db_path
        self.enabled_sources = enabled_sources
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
            async with NetworkClient(ResponseCache(database.connection)) as client:
                engine = InvestigationEngine(
                    [a for a in default_adapters() if a.id in self.enabled_sources],
                    client,
                    database,
                    on_event=self.event.emit,
                    cancelled=self.cancelled,
                )
                await engine.run(self.query)
