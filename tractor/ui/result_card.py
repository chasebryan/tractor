from urllib.parse import urlsplit

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from tractor.core.deduplication import normalize_url
from tractor.core.models import SourceResult
from tractor.ui.theme import label


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
        top.addWidget(label(result.source_type, "badge"))
        top.addStretch()
        top.addWidget(label(f"RELEVANCE  {result.relevance_score:.0f}", "muted"))
        layout.addLayout(top)
        layout.addWidget(label(result.title, "resultTitle", True))
        language = (
            result.original_language if result.original_language != "und" else "Language unknown"
        )
        layout.addWidget(
            label(
                f"{result.source_provider.replace('_', ' ').title()}   ·   "
                f"{(result.published_at or 'Undated')[:10]}   ·   {language}",
                "muted",
            )
        )
        layout.addWidget(
            label(result.excerpt[:380] or "Metadata record. Open evidence for details.", wrap=True)
        )
        bottom = QHBoxLayout()
        bottom.addWidget(label(urlsplit(result.url).hostname or "", "muted"))
        bottom.addStretch()
        for text, action in (
            ("Open source ↗", self.open_source),
            ("Evidence", lambda: self.evidence_requested.emit(result.id)),
            ("Related", lambda: self.related_requested.emit(result.id)),
        ):
            button = QPushButton(text)
            button.setObjectName("quiet")
            button.clicked.connect(action)
            bottom.addWidget(button)
        layout.addLayout(bottom)

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
        QDesktopServices.openUrl(QUrl(url))
