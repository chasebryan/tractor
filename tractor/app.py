import argparse
import asyncio
from pathlib import Path

from platformdirs import user_data_path

from tractor.core.engine import InvestigationEngine
from tractor.export.json_export import export_json
from tractor.logging_config import configure_logging
from tractor.network.client import NetworkClient
from tractor.settings import Settings
from tractor.sources import default_adapters
from tractor.sources.web import SearxNG
from tractor.storage.cache import ResponseCache
from tractor.storage.database import Database


async def headless(
    query: str,
    data_dir: Path,
    output: Path | None,
    *,
    resume_id: str | None = None,
    sources: list[str] | None = None,
) -> int:
    settings = Settings.load(data_dir)
    selected = sources if sources is not None else settings.sources
    adapters = default_adapters()
    if settings.web_endpoint:
        adapters.append(SearxNG(settings.web_endpoint))
    if "searxng" in selected and not settings.web_endpoint:
        raise ValueError(
            "Configure a SearxNG server in desktop Settings before enabling web search."
        )
    with Database(data_dir / "investigations.sqlite3") as database:
        resume = database.load(resume_id) if resume_id else None
        async with NetworkClient(
            ResponseCache(database.connection), allowed_origins=settings.allowed_origins
        ) as client:
            engine = InvestigationEngine(
                [a for a in adapters if a.id in selected], client, database
            )
            inv = await engine.run(query, resume=resume)
            if output:
                export_json(inv, output)
            print(f"{inv.status}: {len(inv.unique_results)} unique results · {inv.stop_reason}")
            print(f"Investigation: {inv.id} · {len(inv.pending_tasks)} searches pending")
            return 1 if inv.status == "failed" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TRACTOR · Global Intelligence Search")
    parser.add_argument("--data-dir", type=Path, default=user_data_path("TRACTOR", appauthor=False))
    parser.add_argument("--debug", action="store_true", help="Enable structured debug logging")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--search", help="Run the same investigation engine without the GUI")
    action.add_argument("--resume", help="Continue a saved investigation by its full ID")
    action.add_argument(
        "--history", nargs="?", const="", metavar="TEXT", help="Search local history"
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=[a.id for a in default_adapters()] + ["searxng"],
        help="Override saved provider choices for this headless run",
    )
    parser.add_argument("--export-json", type=Path, help="Export a headless investigation")
    args = parser.parse_args()
    configure_logging(args.debug)
    if args.search or args.resume:
        try:
            return asyncio.run(
                headless(
                    args.search or "",
                    args.data_dir,
                    args.export_json,
                    resume_id=args.resume,
                    sources=args.sources,
                )
            )
        except KeyError:
            parser.exit(1, "No saved investigation has that ID. Use --history to list IDs.\n")
        except (ValueError, OSError) as exc:
            parser.exit(1, f"Could not start: {exc}\n")
        except KeyboardInterrupt:
            parser.exit(
                130, "Stopped. Collected evidence and remaining work are saved in History.\n"
            )
    if args.export_json or args.sources:
        parser.error("--export-json and --sources require --search or --resume")
    if args.history is not None:
        with Database(args.data_dir / "investigations.sqlite3") as database:
            for item in database.history(search=args.history):
                print(
                    f"{item['id']}  {item['query']}  [{item['status']}; {item['results']} results]"
                )
        return 0
    from PySide6.QtWidgets import QApplication

    from tractor.ui.main_window import MainWindow

    app = QApplication([])
    app.setApplicationName("TRACTOR")
    app.setOrganizationName("TRACTOR")
    window = MainWindow(args.data_dir)
    window.show()
    return app.exec()
