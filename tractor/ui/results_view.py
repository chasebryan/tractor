from collections import Counter
from datetime import date

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

from tractor.core.filtering import ResultFilter, date_bounds
from tractor.core.models import Investigation
from tractor.ui.result_card import PROVIDERS, ResultCard, language_name
from tractor.ui.search_view import SearchBox
from tractor.ui.theme import label


class ResultsView(QWidget):
    evidence_requested = Signal(str)
    related_requested = Signal(str)
    coverage_requested = Signal()
    export_requested = Signal()
    cancel_requested = Signal()
    continue_requested = Signal()
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        self.inv: Investigation | None = None
        self.visible_limit = 60
        self.card_widgets: dict[str, ResultCard] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 10, 35, 15)
        layout.setSpacing(13)
        self.search = SearchBox()
        layout.addWidget(self.search)
        self.status = label("Searching public sources…", "muted", True)
        layout.addWidget(self.status)
        self.tor_status = label("", "muted", True)
        self.tor_status.hide()
        layout.addWidget(self.tor_status)
        status_row = QHBoxLayout()
        self.summary = label(
            "Collecting records. Results will appear as sources respond.", "muted", True
        )
        status_row.addWidget(self.summary, 1)
        for attr, caption, signal in (
            ("cancel_button", "Stop", self.cancel_requested),
            ("continue_button", "Continue", self.continue_requested),
            ("refresh_button", "Refresh", self.refresh_requested),
            ("coverage_button", "Coverage", self.coverage_requested),
            ("export_button", "Export", self.export_requested),
        ):
            button = QPushButton(caption)
            button.clicked.connect(signal)
            setattr(self, attr, button)
            status_row.addWidget(button)
        self.continue_button.setToolTip(
            "Continue saved pages and retry failed sources with another bounded run."
        )
        self.refresh_button.setToolTip(
            "Start a new investigation with fresh requests. This one stays in History."
        )
        layout.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        filters = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Filter collected results…")
        self.text.setAccessibleName("Filter result text")
        self.text.textChanged.connect(self.filter_changed)
        filters.addWidget(self.text, 2)
        self.types = QComboBox()
        self.languages = QComboBox()
        for box, caption in ((self.types, "All source types"), (self.languages, "All languages")):
            box.addItem(caption, "")
            box.setAccessibleName(caption)
            box.currentIndexChanged.connect(self.filter_changed)
            filters.addWidget(box)
        self.sort = QComboBox()
        self.sort.setAccessibleName("Sort results")
        for caption, key in (
            ("Relevance", "relevance"),
            ("Newest first", "newest"),
            ("Oldest first", "oldest"),
        ):
            self.sort.addItem(caption, key)
        self.sort.currentIndexChanged.connect(self.filter_changed)
        filters.addWidget(self.sort)
        more = QPushButton("Filters")
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
            box.currentIndexChanged.connect(self.filter_changed)
            advanced.addWidget(box, 0, column)
        self.domain = QLineEdit()
        self.domain.setPlaceholderText("Domain, e.g. archive.org")
        self.after = QLineEdit()
        self.after.setPlaceholderText("After YYYY-MM-DD")
        self.before = QLineEdit()
        self.before.setPlaceholderText("Before YYYY-MM-DD")
        for column, edit in enumerate((self.domain, self.after, self.before)):
            edit.setAccessibleName(edit.placeholderText())
            edit.textChanged.connect(self.filter_changed)
            advanced.addWidget(edit, 1, column)
        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100)
        self.minimum.setPrefix("Min relevance: ")
        self.minimum.setAccessibleName("Minimum relevance")
        self.minimum.valueChanged.connect(self.filter_changed)
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
        self.empty = label("Waiting for sources…", "muted", True)
        self.more_button = QPushButton("Show more")
        self.more_button.clicked.connect(self.show_more)
        self.card_layout.addWidget(self.empty)
        self.card_layout.addWidget(self.more_button)
        self.card_layout.addStretch()
        self.more_button.hide()
        self.scroll.setWidget(self.cards)
        layout.addWidget(self.scroll, 1)
        self.reset()

    def reset(self) -> None:
        self.inv = None
        self.visible_limit = 60
        for card in self.card_widgets.values():
            self.card_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.card_widgets.clear()
        self.empty.setText("Waiting for sources…")
        self.empty.show()
        self.more_button.hide()
        self.summary.setText("Collecting records. Results will appear as sources respond.")
        for button in (self.coverage_button, self.export_button, self.refresh_button):
            button.setEnabled(False)
        self.continue_button.hide()
        self.clear_filters()
        self.scroll.verticalScrollBar().setValue(0)

    def clear_filters(self) -> None:
        for edit in (self.text, self.domain, self.after, self.before):
            edit.clear()
        for box in (
            self.types,
            self.languages,
            self.providers,
            self.regions,
            self.entities,
            self.sort,
        ):
            box.setCurrentIndex(0)
        self.minimum.setValue(0)

    def filter_changed(self, *_: object) -> None:
        self.visible_limit = 60
        self.render(preserve_position=False)

    @staticmethod
    def populate(box: QComboBox, values: set[str], display=None) -> None:
        selected = box.currentData()
        caption = box.itemText(0)
        box.blockSignals(True)
        box.clear()
        box.addItem(caption, "")
        for value in sorted(values):
            box.addItem(display(value) if display else value, value)
        box.setCurrentIndex(max(0, box.findData(selected)))
        box.blockSignals(False)

    def update_investigation(self, inv: Investigation) -> None:
        if self.inv and self.inv.id != inv.id:
            self.reset()
        self.inv = inv
        tor_attempts = [a for a in inv.attempts if a.network == "tor"]
        if inv.status != "running":
            self.tor_status.setVisible(bool(tor_attempts))
            successful = sum(a.status == "success" for a in tor_attempts)
            latest = {a.provider: a for a in tor_attempts}
            failed = [a for a in latest.values() if a.status == "error"]
            self.tor_status.setText(
                f"Tor · {inv.coverage['onion_results']} unique onion results · "
                f"{successful} successful searches" + (f" · {failed[-1].error}" if failed else "")
            )
        self.populate(self.types, {r.source_type for r in inv.results})
        self.populate(self.languages, {r.original_language for r in inv.results}, language_name)
        self.populate(
            self.providers, {r.source_provider for r in inv.results}, lambda p: PROVIDERS.get(p, p)
        )
        self.populate(
            self.regions,
            {str(r.metadata["region"]) for r in inv.results if r.metadata.get("region")},
        )
        self.populate(self.entities, {e.kind for e in inv.entities})
        running = inv.status == "running"
        self.progress.setVisible(running)
        self.cancel_button.setVisible(running)
        self.continue_button.setVisible(bool(inv.pending_tasks) and not running)
        self.continue_button.setEnabled(len(inv.results) < inv.budget.get("max_results", 3000))
        self.refresh_button.setEnabled(not running)
        self.coverage_button.setEnabled(True)
        self.export_button.setEnabled(True)
        if running:
            self.status.setText(
                f"Investigating · Run {inv.runs} · {len(inv.attempts)} page attempts · "
                f"{len(inv.pending_tasks)} queued searches"
            )
        else:
            self.status.setText(f"{inv.status.title()} · {inv.stop_reason}")
        self.render()

    def render(self, *_: object, preserve_position: bool = True) -> None:
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
        error = ""
        try:
            filtered = filters.apply(inv)
        except ValueError as exc:
            filtered, error = [], str(exc)
        order = self.sort.currentData()
        if order in {"newest", "oldest"}:

            def key(result):
                bounds = date_bounds(result.published_at)
                ordinal = (bounds[0] if bounds else date.min).toordinal()
                return (
                    bounds is None,
                    -ordinal if order == "newest" else ordinal,
                    -result.relevance_score,
                )

            filtered.sort(key=key)
        c = inv.coverage
        self.summary.setText(
            error
            or f"{len(filtered)} results · {c['sources_successful']} sources · "
            f"{c['duplicates_removed']} duplicates grouped"
        )
        scroll = self.scroll.verticalScrollBar()
        position = scroll.value()
        anchors = [
            (rid, card.y() - position)
            for rid, card in self.card_widgets.items()
            if card.y() + card.height() > position
        ]
        anchor = min(anchors, key=lambda item: item[1]) if anchors else None
        visible = filtered[: self.visible_limit]
        wanted = {r.id for r in visible}
        for rid in list(self.card_widgets):
            if rid not in wanted:
                card = self.card_widgets.pop(rid)
                self.card_layout.removeWidget(card)
                card.hide()
                card.deleteLater()
        duplicates = Counter(r.duplicate_of for r in inv.results if r.duplicate_of)
        for index, result in enumerate(visible):
            card = self.card_widgets.get(result.id)
            if card is None:
                card = ResultCard(result)
                card.evidence_requested.connect(self.evidence_requested)
                card.related_requested.connect(self.related_requested)
                self.card_widgets[result.id] = card
            card.update_result(result, duplicates[result.id])
            if self.card_layout.indexOf(card) != index:
                self.card_layout.removeWidget(card)
                self.card_layout.insertWidget(index, card)
            card.show()
        self.empty.setVisible(not visible)
        self.empty.setText(
            error
            or (
                "Waiting for sources…"
                if inv.status == "running" and not inv.results
                else "No matching records. Clear your filters or review Coverage "
                "for source errors and limits."
            )
        )
        self.more_button.setVisible(len(filtered) > self.visible_limit)
        self.more_button.setText(
            f"Show more · {max(0, len(filtered) - self.visible_limit)} remaining"
        )
        self.card_layout.activate()
        if preserve_position and anchor and anchor[0] in self.card_widgets:
            scroll.setValue(self.card_widgets[anchor[0]].y() - anchor[1])
        else:
            scroll.setValue(position if preserve_position else 0)

    def show_more(self) -> None:
        self.visible_limit += 60
        self.render()
