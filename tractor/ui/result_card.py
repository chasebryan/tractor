from urllib.parse import urlsplit

from PySide6.QtCore import QLocale, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from tractor.core.deduplication import normalize_url
from tractor.core.models import SourceResult
from tractor.ui.theme import label

PROVIDERS = {
    "europe_pmc": "Europe PMC",
    "gdelt": "GDELT News",
    "github": "GitHub",
    "crossref": "Crossref",
    "wikidata": "Wikidata",
    "internet_archive": "Internet Archive",
    "searxng": "Web search",
    "torch": "Torch · via Tor",
    "onion_searxng": "Onion metasearch · via Tor",
}


def language_name(code: str) -> str:
    if code == "und":
        return "Language unknown"
    if code == "mul":
        return "Multiple languages"
    locale = QLocale(code)
    return (
        code
        if locale.language() == QLocale.Language.C
        else QLocale.languageToString(locale.language())
    )


class ResultCard(QFrame):
    evidence_requested = Signal(str)
    related_requested = Signal(str)

    def __init__(self, result: SourceResult):
        super().__init__()
        self.result = result
        self.setObjectName("resultCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(23, 18, 23, 17)
        layout.setSpacing(9)
        top = QHBoxLayout()
        self.badge = label("", "badge")
        self.score = label("", "muted")
        self.score.setToolTip(
            "Query relevance, not a probability. See Evidence for the calculation."
        )
        top.addWidget(self.badge)
        top.addStretch()
        top.addWidget(self.score)
        layout.addLayout(top)
        self.title = label("", "resultTitle", True)
        self.metadata = label("", "muted", True)
        self.excerpt = label("", wrap=True)
        for widget in (self.title, self.metadata, self.excerpt):
            layout.addWidget(widget)
        bottom = QHBoxLayout()
        self.domain = label("", "muted")
        bottom.addWidget(self.domain)
        bottom.addStretch()
        for text, action in (
            ("Open source ↗", self.open_source),
            ("Copy link", self.copy_link),
            ("Evidence", lambda: self.evidence_requested.emit(self.result.id)),
            ("Related", lambda: self.related_requested.emit(self.result.id)),
        ):
            button = QPushButton(text)
            button.setObjectName("quiet")
            button.clicked.connect(action)
            bottom.addWidget(button)
            if text == "Copy link":
                self.copy_button = button
        layout.addLayout(bottom)
        self.update_result(result)

    def update_result(self, result: SourceResult, duplicates: int = 0) -> None:
        self.result = result
        self.badge.setText(
            result.source_type + (f"  ·  {duplicates + 1} RECORDS" if duplicates else "")
        )
        self.score.setText(f"RELEVANCE  {result.relevance_score:.0f}")
        self.title.setText(result.title)
        provider = PROVIDERS.get(
            result.source_provider, result.source_provider.replace("_", " ").title()
        )
        self.metadata.setText(
            f"{provider}   ·   {(result.published_at or 'Undated')[:10]}   ·   "
            f"{language_name(result.original_language)}"
        )
        self.excerpt.setText(result.excerpt[:380] or "Metadata record. Open evidence for details.")
        domain = urlsplit(result.url).hostname or ""
        self.domain.setText(
            self.domain.fontMetrics().elidedText(domain, Qt.TextElideMode.ElideMiddle, 220)
        )
        self.domain.setToolTip(result.url)

    def copy_link(self) -> None:
        QApplication.clipboard().setText(self.result.url)
        self.copy_button.setText("Copied")
        QTimer.singleShot(1500, self, lambda: self.copy_button.setText("Copy link"))

    def open_source(self) -> None:
        try:
            url = normalize_url(self.result.url)
        except ValueError:
            QMessageBox.warning(self, "Source unavailable", "This source has an invalid URL.")
            return
        if (urlsplit(url).hostname or "").endswith(".onion"):
            QMessageBox.information(
                self, "Onion source", "Open this address in your Tor browser:\n" + url
            )
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.information(
                self, "Could not open browser", "Use Copy link to open this source manually."
            )
