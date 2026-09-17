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


def test_launch_screen_contains_brand_only_once(qtbot, tmp_path):
    from PySide6.QtWidgets import QPushButton

    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.show()
    visible = [
        widget.text()
        for cls in (QLabel, QPushButton)
        for widget in window.findChildren(cls)
        if widget.isVisible()
    ]
    assert sum(text.lower().count("tractor") for text in visible) == 1
    assert "tractor" not in window.windowTitle().lower()
    assert not window.home_button.isVisible()


def test_streaming_retains_card_identity_and_reading_position(qtbot, investigation):
    from tractor.ui.results_view import ResultsView

    view = ResultsView()
    qtbot.addWidget(view)
    view.resize(1050, 780)
    for i in range(20):
        investigation.results.append(
            SourceResult(
                f"Record {i}",
                f"https://example.org/{i}",
                "DOCUMENT",
                "test",
                relevance_score=20 - i,
            )
        )
    view.update_investigation(investigation)
    view.show()
    qtbot.waitUntil(lambda: view.scroll.verticalScrollBar().maximum() > 1000)
    position = list(view.card_widgets.values())[3].y() + 20
    view.scroll.verticalScrollBar().setValue(position)
    original = dict(view.card_widgets)
    investigation.results.append(
        SourceResult(
            "New highest result", "https://example.org/new", "DOCUMENT", "test", relevance_score=100
        )
    )
    anchor = next(
        card for card in original.values() if card.y() <= position < card.y() + card.height()
    )
    offset = anchor.y() - position
    view.update_investigation(investigation)
    assert all(view.card_widgets[key] is card for key, card in original.items())
    assert abs(anchor.y() - view.scroll.verticalScrollBar().value() - offset) <= 2
    view.after.setText("not a date")
    assert not view.card_widgets
    assert "YYYY-MM-DD" in view.summary.text()


def test_new_search_clears_old_results_and_export_target(
    qtbot, tmp_path, investigation, monkeypatch
):
    import tractor.ui.worker as module
    from tests.test_engine import FixtureAdapter

    monkeypatch.setattr(module, "default_adapters", lambda: [FixtureAdapter()])
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.enabled_sources = ["fixture"]
    window.inv = investigation
    window.results.update_investigation(investigation)
    window.search("New query")
    assert window.inv is None
    assert not window.results.card_widgets
    assert not window.results.export_button.isEnabled()
    qtbot.waitUntil(lambda: window.worker is None, timeout=5000)


def test_gui_continue_reuses_history_and_investigation_id(qtbot, tmp_path, monkeypatch):
    import tractor.ui.worker as module
    from tests.test_continuation import Pages

    source = Pages(5)
    monkeypatch.setattr(module, "default_adapters", lambda: [source])
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.enabled_sources = [source.id]
    window.show()
    window.search("Acme")
    qtbot.waitUntil(lambda: window.worker is None, timeout=5000)
    original = window.inv.id
    assert window.inv.status == "partial"
    assert window.results.continue_button.isVisible()
    window.continue_search()
    qtbot.waitUntil(lambda: window.worker is None, timeout=5000)
    assert window.inv.id == original and window.inv.runs == 2
    assert len(window.inv.unique_results) == 5
    assert not window.results.continue_button.isVisible()
    assert len(window.database.history()) == 1


def test_copy_link_and_date_sorting(qtbot, investigation, result):
    from PySide6.QtWidgets import QApplication

    from tractor.ui.results_view import ResultsView

    view = ResultsView()
    qtbot.addWidget(view)
    recent = SourceResult(
        "Recent", "https://example.org/recent", "WEB", "test", published_at="2026-09-17"
    )
    unknown = SourceResult("Unknown", "https://example.org/unknown", "WEB", "test")
    investigation.results += [recent, unknown]
    view.update_investigation(investigation)
    view.sort.setCurrentIndex(view.sort.findData("newest"))
    assert view.card_layout.itemAt(0).widget().result.id == recent.id
    view.sort.setCurrentIndex(view.sort.findData("oldest"))
    assert view.card_layout.itemAt(0).widget().result.id == result.id
    assert view.card_layout.itemAt(2).widget().result.id == unknown.id
    card = view.card_widgets[recent.id]
    card.copy_link()
    assert QApplication.clipboard().text() == recent.url
