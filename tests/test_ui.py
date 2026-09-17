from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTabWidget, QTextEdit

from tractor.core.models import SourceResult
from tractor.sources.base import SearchBatch
from tractor.ui.main_window import MainWindow
from tractor.ui.result_card import ResultCard
from tractor.ui.source_view import SourceView


def test_minimal_home_and_empty_query(qtbot, tmp_path):
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.show()
    assert window.pages.currentWidget() is window.home
    window.search(" ")
    assert "Enter a subject" in window.home.error.text()
    assert window.worker is None


def test_result_content_is_never_rendered_as_html(qtbot, result, investigation):
    result.title = "<script>untrusted</script>"
    result.original_text = "<img src='https://tracker.test/pixel'>"
    card = ResultCard(result)
    qtbot.addWidget(card)
    assert all(
        widget.textFormat() == Qt.TextFormat.PlainText for widget in card.findChildren(QLabel)
    )
    view = SourceView(investigation, result)
    qtbot.addWidget(view)
    assert view.findChild(QTabWidget).widget(0).toPlainText() == result.original_text
    assert all(widget.isReadOnly() for widget in view.findChildren(QTextEdit))


def test_background_search_streams_and_reopens(qtbot, tmp_path, monkeypatch):
    import asyncio

    import tractor.ui.worker as module

    class Source:
        id = "offline"

        async def search(self, query, context):
            await asyncio.sleep(0.05)
            return SearchBatch(
                [
                    SourceResult(
                        "Offline Acme record", "https://example.org/acme", "DOCUMENT", self.id
                    )
                ]
            )

    monkeypatch.setattr(module, "default_adapters", lambda: [Source()])
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.enabled_sources = ["offline"]
    window.show()
    window.search("Acme")
    assert not window.results.search.isEnabled()
    qtbot.waitUntil(lambda: window.worker is None, timeout=5000)
    assert window.inv.status == "complete"
    assert window.results.search.isEnabled()
    assert "1 results" in window.results.summary.text()
    saved = window.database.load(window.inv.id)
    assert saved.results[0].title == "Offline Acme record"
    window.results.update_investigation(saved)
    window.results.text.setText("unmatched")
    assert "0 results" in window.results.summary.text()


def test_closing_cancels_worker_without_destroying_running_thread(qtbot, tmp_path, monkeypatch):
    import asyncio

    import tractor.ui.worker as module

    class Slow:
        id = "slow"

        async def search(self, query, context):
            await asyncio.sleep(60)

    monkeypatch.setattr(module, "default_adapters", lambda: [Slow()])
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.enabled_sources = ["slow"]
    window.show()
    window.search("Acme")
    qtbot.waitUntil(lambda: window.inv is not None)
    window.close()
    qtbot.waitUntil(lambda: window.worker is None and not window.isVisible(), timeout=3000)
    assert window.inv.status == "cancelled"
