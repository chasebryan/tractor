from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tractor.core.filtering import ResultFilter
from tractor.core.models import Investigation
from tractor.ui.result_card import ResultCard
from tractor.ui.search_view import SearchBox
from tractor.ui.theme import label


class ResultsView(QWidget):
    evidence_requested = Signal(str)
    related_requested = Signal(str)
    coverage_requested = Signal()
    export_requested = Signal()
    cancel_requested = Signal()

    def __init__(self):
        super().__init__()
        self.inv: Investigation | None = None
        self.visible_limit = 60
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 10, 35, 15)
        layout.setSpacing(13)
        self.search = SearchBox()
        layout.addWidget(self.search)
        status_row = QHBoxLayout()
        self.status = label("Searching public sources…", "muted")
        status_row.addWidget(self.status, 1)
        self.cancel_button = QPushButton("Stop")
        self.cancel_button.clicked.connect(self.cancel_requested)
        status_row.addWidget(self.cancel_button)
        coverage = QPushButton("Coverage and evidence")
        coverage.clicked.connect(self.coverage_requested)
        status_row.addWidget(coverage)
        export = QPushButton("Export")
        export.clicked.connect(self.export_requested)
        status_row.addWidget(export)
        layout.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.summary = label("Collecting records. Results will appear as sources respond.", "muted")
        layout.addWidget(self.summary)
        filters = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Filter collected results…")
        self.text.setAccessibleName("Filter result text")
        self.text.textChanged.connect(self.render)
        filters.addWidget(self.text, 2)
        self.types = QComboBox()
        self.languages = QComboBox()
        for box, caption in ((self.types, "All source types"), (self.languages, "All languages")):
            box.addItem(caption, "")
            box.setAccessibleName(caption)
            box.currentIndexChanged.connect(self.render)
            filters.addWidget(box)
        more = QPushButton("More filters")
        more.setCheckable(True)
        filters.addWidget(more)
        layout.addLayout(filters)
        self.advanced = QWidget()
        advanced = QGridLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        self.providers = QComboBox()
        self.regions = QComboBox()
        self.entities = QComboBox()
        for column, (box, caption) in enumerate(
            (
                (self.providers, "All providers"),
                (self.regions, "All regions"),
                (self.entities, "All entity types"),
            )
        ):
            box.addItem(caption, "")
            box.setAccessibleName(caption)
            box.currentIndexChanged.connect(self.render)
            advanced.addWidget(box, 0, column)
        self.domain = QLineEdit()
        self.domain.setPlaceholderText("Domain, e.g. archive.org")
        self.after = QLineEdit()
        self.after.setPlaceholderText("After YYYY-MM-DD")
        self.before = QLineEdit()
        self.before.setPlaceholderText("Before YYYY-MM-DD")
        for column, edit in enumerate((self.domain, self.after, self.before)):
            edit.setAccessibleName(edit.placeholderText())
            edit.textChanged.connect(self.render)
            advanced.addWidget(edit, 1, column)
        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100)
        self.minimum.setPrefix("Min relevance: ")
        self.minimum.setAccessibleName("Minimum relevance")
        self.minimum.valueChanged.connect(self.render)
        advanced.addWidget(self.minimum, 0, 3)
        clear = QPushButton("Clear filters")
        clear.clicked.connect(self.clear_filters)
        advanced.addWidget(clear, 1, 3)
        self.advanced.hide()
        more.toggled.connect(self.advanced.setVisible)
        layout.addWidget(self.advanced)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards = QWidget()
        self.card_layout = QVBoxLayout(self.cards)
        self.card_layout.setContentsMargins(0, 0, 9, 0)
        self.card_layout.setSpacing(12)
        self.scroll.setWidget(self.cards)
        layout.addWidget(self.scroll, 1)

    def clear_filters(self) -> None:
        for edit in (self.text, self.domain, self.after, self.before):
            edit.clear()
        for box in (self.types, self.languages, self.providers, self.regions, self.entities):
            box.setCurrentIndex(0)
        self.minimum.setValue(0)

    @staticmethod
    def populate(box: QComboBox, values: set[str]) -> None:
        selected = box.currentData()
        caption = box.itemText(0)
        box.blockSignals(True)
        box.clear()
        box.addItem(caption, "")
        for value in sorted(values):
            box.addItem(value, value)
        box.setCurrentIndex(max(0, box.findData(selected)))
        box.blockSignals(False)

    def update_investigation(self, inv: Investigation) -> None:
        self.inv = inv
        self.populate(self.types, {r.source_type for r in inv.results})
        self.populate(self.languages, {r.original_language for r in inv.results})
        self.populate(self.providers, {r.source_provider for r in inv.results})
        self.populate(
            self.regions,
            {str(r.metadata["region"]) for r in inv.results if r.metadata.get("region")},
        )
        self.populate(self.entities, {e.kind for e in inv.entities})
        running = inv.status == "running"
        self.progress.setVisible(running)
        self.cancel_button.setVisible(running)
        if not running:
            self.status.setText(f"{inv.status.title()} · {inv.stop_reason}")
        self.render()

    def render(self, *_: object) -> None:
        if self.inv is None:
            return
        inv = self.inv
        filters = ResultFilter(
            text=self.text.text(),
            source_type=self.types.currentData() or "",
            language=self.languages.currentData() or "",
            provider=self.providers.currentData() or "",
            region=self.regions.currentData() or "",
            entity_type=self.entities.currentData() or "",
            domain=self.domain.text(),
            after=self.after.text(),
            before=self.before.text(),
            min_relevance=self.minimum.value(),
        )
        try:
            filtered = filters.apply(inv)
        except ValueError as exc:
            self.summary.setText(str(exc))
            return
        c = inv.coverage
        self.summary.setText(
            f"{len(filtered)} results   ·   {c['sources_successful']} sources responded"
            f"   ·   {c['duplicates_removed']} duplicates grouped"
            f"   ·   Pass {inv.passes}"
        )
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not filtered:
            message = (
                "Waiting for sources…"
                if inv.status == "running"
                else (
                    "No matching records. Review the coverage panel for provider errors or limits."
                )
            )
            self.card_layout.addWidget(label(message, "muted", True))
        for result in filtered[: self.visible_limit]:
            card = ResultCard(result)
            card.evidence_requested.connect(self.evidence_requested)
            card.related_requested.connect(self.related_requested)
            self.card_layout.addWidget(card)
        if len(filtered) > self.visible_limit:
            more = QPushButton(f"Show more · {len(filtered) - self.visible_limit} remaining")
            more.clicked.connect(self.show_more)
            self.card_layout.addWidget(more)
        self.card_layout.addStretch()

    def show_more(self) -> None:
        self.visible_limit += 60
        self.render()
