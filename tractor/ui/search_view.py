from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from tractor.ui.theme import label


class SearchBox(QWidget):
    submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.input = QLineEdit()
        self.input.setObjectName("searchInput")
        self.input.setPlaceholderText("A name, an organization, a subject…")
        self.input.setAccessibleName("Investigation query")
        self.input.setMaxLength(240)
        self.button = QPushButton("Search  →")
        self.button.setObjectName("primary")
        self.button.setMinimumHeight(62)
        self.input.returnPressed.connect(self.submit)
        self.button.clicked.connect(self.submit)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.button)

    def submit(self) -> None:
        if self.isEnabled():
            self.submitted.emit(self.input.text())


class SearchView(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(45, 20, 45, 55)
        outer.addStretch(3)
        content = QWidget()
        content.setMinimumWidth(720)
        content.setMaximumWidth(780)
        layout = QVBoxLayout(content)
        layout.setSpacing(18)
        eyebrow = label("GLOBAL INTELLIGENCE SEARCH", "eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wordmark = label("TRACTOR", "hero")
        wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = label("One subject. A deeper investigation.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(eyebrow)
        layout.addWidget(wordmark)
        layout.addWidget(subtitle)
        layout.addSpacing(22)
        self.search = SearchBox()
        layout.addWidget(self.search)
        self.error = label("", "muted", True)
        layout.addWidget(self.error)
        note = label("PUBLIC SOURCES   /   TRACEABLE EVIDENCE   /   LOCAL HISTORY", "eyebrow")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)
        outer.addWidget(content, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(4)
        privacy = label(
            "Search queries are sent to enabled public data providers.\n"
            "Your investigation stays on this device. No telemetry.",
            "muted",
            True,
        )
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(privacy)
