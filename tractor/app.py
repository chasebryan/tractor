import argparse
import asyncio
from pathlib import Path

from platformdirs import user_data_path

from tractor.core.engine import InvestigationEngine
from tractor.export.json_export import export_json
from tractor.logging_config import configure_logging
from tractor.network.client import NetworkClient
from tractor.sources import default_adapters
from tractor.storage.cache import ResponseCache
from tractor.storage.database import Database


async def headless(query: str, data_dir: Path, output: Path | None) -> int:
    with Database(data_dir / "investigations.sqlite3") as database:
        async with NetworkClient(ResponseCache(database.connection)) as client:
            engine = InvestigationEngine(default_adapters(), client, database)
            inv = await engine.run(query)
            if output:
                export_json(inv, output)
            print(f"{inv.status}: {len(inv.unique_results)} unique results · {inv.stop_reason}")
            return 1 if inv.status == "failed" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TRACTOR · Global Intelligence Search")
    parser.add_argument("--data-dir", type=Path, default=user_data_path("TRACTOR", appauthor=False))
    parser.add_argument("--debug", action="store_true", help="Enable structured debug logging")
    parser.add_argument("--search", help="Run the same investigation engine without the GUI")
    parser.add_argument("--export-json", type=Path, help="Export a headless investigation")
    args = parser.parse_args()
    configure_logging(args.debug)
    if args.search:
        try:
            return asyncio.run(headless(args.search, args.data_dir, args.export_json))
        except (ValueError, OSError) as exc:
            parser.exit(1, f"TRACTOR could not start: {type(exc).__name__}\n")
    if args.export_json:
        parser.error("--export-json requires --search")
    from PySide6.QtWidgets import QApplication

    from tractor.ui.main_window import MainWindow

    app = QApplication([])
    app.setApplicationName("TRACTOR")
    app.setOrganizationName("TRACTOR")
    window = MainWindow(args.data_dir)
    window.show()
    return app.exec()
