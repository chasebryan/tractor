from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tractor.core.models import Investigation
from tractor.core.query import normalize_query
from tractor.export.csv_export import export_csv
from tractor.export.json_export import export_json
from tractor.export.report import export_markdown
from tractor.settings import Settings, validate_web_endpoint
from tractor.sources import default_adapters
from tractor.storage.database import Database
from tractor.ui.investigation_view import InvestigationView
from tractor.ui.results_view import ResultsView
from tractor.ui.search_view import SearchView
from tractor.ui.source_view import SourceView
from tractor.ui.theme import STYLE, label
from tractor.ui.worker import InvestigationWorker


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path):
        super().__init__()
        self.data_dir = data_dir
        self.db_path = data_dir / "investigations.sqlite3"
        self.database = Database(self.db_path)
        self.settings = Settings.load(data_dir)
        self.enabled_sources = self.settings.sources
        self.inv: Investigation | None = None
        self.worker: InvestigationWorker | None = None
        self.closing = False
        self.setWindowTitle("Global Intelligence Search")
        self.setWindowIcon(QIcon(str(Path(__file__).parents[1] / "assets" / "icon.svg")))
        self.resize(1180, 830)
        self.setMinimumSize(850, 640)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(36, 20, 30, 14)
        self.home_button = QPushButton("← New search")
        self.home_button.setObjectName("quiet")
        self.home_button.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        bar.addWidget(self.home_button)
        bar.addStretch()
        self.history_button = QPushButton("History")
        self.history_button.setObjectName("quiet")
        self.history_button.clicked.connect(self.show_history)
        bar.addWidget(self.history_button)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("quiet")
        self.settings_button.clicked.connect(self.show_settings)
        bar.addWidget(self.settings_button)
        layout.addLayout(bar)
        self.pages = QStackedWidget()
        self.home = SearchView()
        self.results = ResultsView()
        self.pages.addWidget(self.home)
        self.pages.addWidget(self.results)
        self.pages.currentChanged.connect(lambda index: self.home_button.setVisible(index != 0))
        self.home_button.hide()
        layout.addWidget(self.pages, 1)
        self.home.search.submitted.connect(self.search)
        self.results.search.submitted.connect(self.search)
        self.results.cancel_requested.connect(self.cancel)
        self.results.continue_requested.connect(self.continue_search)
        self.results.refresh_requested.connect(self.refresh_search)
        self.results.coverage_requested.connect(self.show_coverage)
        self.results.export_requested.connect(self.export)
        self.results.evidence_requested.connect(self.show_evidence)
        self.results.related_requested.connect(lambda rid: self.show_evidence(rid, True))
        for key, callback in (
            ("Ctrl+L", self.focus_search),
            ("Escape", self.cancel),
            ("Ctrl+E", self.export),
            ("Ctrl+H", self.show_history),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        QTimer.singleShot(0, self.home.search.input.setFocus)

    def focus_search(self) -> None:
        search = self.home.search if self.pages.currentIndex() == 0 else self.results.search
        search.input.setFocus()
        search.input.selectAll()

    @Slot(str)
    def search(self, query: str) -> None:
        self.start_search(query)

    def start_search(
        self, query: str, *, resume_id: str | None = None, previous_id: str | None = None
    ) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            query = normalize_query(query)
        except ValueError as exc:
            self.home.error.setText(str(exc))
            self.results.status.setText(str(exc))
            return
        self.home.error.clear()
        if not resume_id:
            self.inv = None
            self.results.reset()
        self.results.search.input.setText(query)
        self.pages.setCurrentIndex(1)
        self.set_busy(True)
        self.results.status.setText("Preparing investigation…")
        self.worker = InvestigationWorker(
            query,
            self.db_path,
            list(self.enabled_sources),
            self,
            web_endpoint=self.settings.web_endpoint,
            resume_id=resume_id,
            previous_id=previous_id,
        )
        self.worker.event.connect(self.on_event)
        self.worker.failed.connect(self.show_failure)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def continue_search(self) -> None:
        if self.inv and self.inv.pending_tasks:
            if not any(t.provider in self.enabled_sources for t in self.inv.pending_tasks):
                QMessageBox.information(
                    self,
                    "Sources disabled",
                    "Enable a provider with remaining work in Settings "
                    "to continue this investigation.",
                )
                return
            self.start_search(self.inv.query, resume_id=self.inv.id)

    def refresh_search(self) -> None:
        if self.inv:
            self.start_search(self.inv.query, previous_id=self.inv.id)

    def set_busy(self, busy: bool) -> None:
        for widget in (
            self.home.search,
            self.results.search,
            self.history_button,
            self.settings_button,
            self.home_button,
        ):
            widget.setEnabled(not busy)
        self.results.progress.setVisible(busy)
        self.results.cancel_button.setVisible(busy)
        self.results.cancel_button.setEnabled(busy)
        self.results.cancel_button.setText("Stop")
        self.results.continue_button.setEnabled(not busy)
        self.results.refresh_button.setEnabled(not busy and self.inv is not None)

    @Slot(str, object)
    def on_event(self, kind: str, payload: object) -> None:
        if kind == "snapshot":
            self.inv = Investigation.from_dict(payload)
            self.results.update_investigation(self.inv)
        elif kind == "status":
            if self.inv and self.inv.status != "running":
                self.results.status.setText(f"{self.inv.status.title()} · {payload}")
            else:
                self.results.status.setText(str(payload))
        elif kind == "activity" and isinstance(payload, dict):
            from tractor.ui.result_card import PROVIDERS

            provider = str(payload.get("provider", ""))
            self.results.status.setText(
                f"Searching {PROVIDERS.get(provider, provider)} · "
                f"Page {payload.get('page', 1)} · "
                f"Discovery pass {payload.get('pass', 1)}"
            )

    @Slot()
    def cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.results.cancel_button.setText("Stopping…")
            self.results.cancel_button.setEnabled(False)

    @Slot(str)
    def show_failure(self, message: str) -> None:
        self.results.status.setText(message)

    @Slot()
    def worker_finished(self) -> None:
        self.set_busy(False)
        if self.inv:
            self.results.update_investigation(self.inv)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.closing:
            QTimer.singleShot(0, self.close)

    def show_evidence(self, result_id: str, related: bool = False) -> None:
        if self.inv:
            result = next((r for r in self.inv.results if r.id == result_id), None)
            if result:
                SourceView(self.inv, result, self, related).exec()

    def show_coverage(self) -> None:
        if self.inv:
            InvestigationView(self.inv, self).exec()

    def show_history(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("TRACTOR · Local history")
        dialog.resize(680, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Your investigations", "heading"))
        layout.addWidget(
            label("Search subjects and collected source text. Saved on this device.", "muted")
        )
        search = QLineEdit()
        search.setPlaceholderText("Search history…")
        search.setAccessibleName("Search local history")
        layout.addWidget(search)
        listing = QListWidget()
        layout.addWidget(listing)
        empty = label("", "muted")
        layout.addWidget(empty)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Close
        )
        layout.addWidget(buttons)

        def populate() -> None:
            listing.clear()
            for entry in self.database.history(search=search.text()):
                state = "interrupted" if entry["status"] == "running" else entry["status"]
                item = QListWidgetItem(
                    f"{entry['query']}\n{entry['updated_at'][:16]} UTC  ·  "
                    f"{state}  ·  {entry['results']} results"
                )
                item.setData(Qt.ItemDataRole.UserRole, entry["id"])
                listing.addItem(item)
            empty.setText("" if listing.count() else "No saved investigations match this search.")
            if listing.count():
                listing.setCurrentRow(0)
            buttons.button(QDialogButtonBox.StandardButton.Open).setEnabled(bool(listing.count()))

        debounce = QTimer(dialog)
        debounce.setSingleShot(True)
        debounce.setInterval(150)
        debounce.timeout.connect(populate)
        search.textChanged.connect(lambda: debounce.start())
        populate()

        def reopen(item: QListWidgetItem) -> None:
            if item is None:
                return
            try:
                self.inv = self.database.load(item.data(Qt.ItemDataRole.UserRole))
            except (KeyError, ValueError):
                QMessageBox.warning(
                    dialog, "Cannot reopen", "This investigation could not be read."
                )
                return
            self.results.reset()
            self.results.search.input.setText(self.inv.query)
            self.results.update_investigation(self.inv)
            self.pages.setCurrentIndex(1)
            dialog.accept()

        listing.itemActivated.connect(reopen)
        buttons.accepted.connect(lambda: reopen(listing.currentItem()))
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def show_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("TRACTOR · Settings")
        dialog.resize(720, 730)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.addWidget(label("Public data sources", "heading"))
        layout.addWidget(
            label(
                "Enabled providers receive your query and discovered search variants. "
                "They may log requests under their own policies. All investigations "
                "use the same bounded, iterative search pipeline.",
                "muted",
                True,
            )
        )
        checks: dict[str, QCheckBox] = {}
        for adapter in default_adapters():
            check = QCheckBox(adapter.name)
            check.setChecked(adapter.id in self.enabled_sources)
            layout.addWidget(check)
            layout.addWidget(label(adapter.description, "muted", True))
            checks[adapter.id] = check
        web = QCheckBox("SearxNG · General web search")
        web.setChecked("searxng" in self.enabled_sources)
        checks["searxng"] = web
        layout.addWidget(web)
        endpoint = QLineEdit(self.settings.web_endpoint)
        endpoint.setPlaceholderText("https://your-search-server.example")
        endpoint.setAccessibleName("SearxNG server URL")
        layout.addWidget(endpoint)
        layout.addWidget(
            label(
                "Use a SearxNG server you operate or trust, with JSON search enabled. "
                "Its upstream engines also receive searches. HTTP is supported for "
                "a local server only.",
                "muted",
                True,
            )
        )
        layout.addSpacing(15)
        layout.addWidget(label("Local storage: " + str(self.data_dir), "muted", True))
        layout.addWidget(
            label(
                "No telemetry. No stored API credentials. Tor providers are not enabled "
                "in this release. Machine translation requires an added backend.",
                "muted",
                True,
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )

        def save() -> None:
            selected = [key for key, check in checks.items() if check.isChecked()]
            if not selected:
                QMessageBox.information(dialog, "Enable a source", "Select at least one provider.")
                return
            try:
                url = validate_web_endpoint(endpoint.text())
                if "searxng" in selected and not url:
                    raise ValueError("Enter a server URL to enable web search.")
                settings = Settings(selected, url)
                settings.save(self.data_dir)
            except ValueError as exc:
                QMessageBox.information(dialog, "Check server URL", str(exc))
                return
            except OSError:
                QMessageBox.warning(
                    dialog, "Could not save", "The settings directory is not writable."
                )
                return
            self.enabled_sources = selected
            self.settings = settings
            dialog.accept()

        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(buttons)
        dialog.exec()

    def export(self) -> None:
        if not self.inv:
            return
        path, format_name = QFileDialog.getSaveFileName(
            self,
            "Export investigation",
            f"tractor-{self.inv.id[:8]}.json",
            "JSON (*.json);;Markdown (*.md);;CSV (*.csv)",
        )
        if not path:
            return
        function, suffix = (
            (export_json, ".json")
            if format_name.startswith("JSON")
            else (
                (export_markdown, ".md")
                if format_name.startswith("Markdown")
                else (export_csv, ".csv")
            )
        )
        output = Path(path)
        if output.suffix.lower() != suffix:
            output = output.with_suffix(suffix)
            if (
                output.exists()
                and QMessageBox.question(
                    self, "Replace export?", f"Replace the existing file {output.name}?"
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        try:
            function(self.inv, output)
        except OSError:
            QMessageBox.warning(self, "Export failed", "Could not write to the selected location.")
            return
        self.results.status.setText("Export saved to " + str(output))

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.cancel()
            event.ignore()
        else:
            self.database.close()
            event.accept()
