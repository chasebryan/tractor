"""Offline self-test used by the native packaging pipeline."""

import tempfile
from pathlib import Path


def run() -> int:
    from PySide6.QtWidgets import QApplication

    from tractor.benchmark.runner import run_benchmark
    from tractor.settings import Settings
    from tractor.ui.main_window import MainWindow
    from tractor.ui.settings_view import SettingsView

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="tractor-smoke-") as directory:
        path = Path(directory)
        window = MainWindow(path)
        window.show()
        app.processEvents()
        if window.grab().isNull():
            raise RuntimeError("Main window did not render")
        dialog = SettingsView(Settings(), path, window.database.connection, window)
        dialog.show()
        app.processEvents()
        if dialog.grab().isNull() or len(dialog.checks) != 14:
            raise RuntimeError("Settings did not initialize")
        dialog.close()
        window.close()
    if not run_benchmark()["passed"]:
        raise RuntimeError("Packaged benchmark failed")
    print("Native GUI, providers, SQLite, assets and benchmark passed offline smoke checks.")
    return 0
