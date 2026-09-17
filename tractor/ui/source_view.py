import json

from PySide6.QtWidgets import QDialog, QTabWidget, QTextEdit, QVBoxLayout

from tractor.core.models import Investigation, SourceResult
from tractor.ui.theme import label


def text_panel(text: str) -> QTextEdit:
    panel = QTextEdit()
    panel.setReadOnly(True)
    panel.setPlainText(text)
    return panel


class SourceView(QDialog):
    def __init__(
        self, inv: Investigation, result: SourceResult, parent=None, related: bool = False
    ):
        super().__init__(parent)
        self.setWindowTitle("TRACTOR · Source evidence")
        self.resize(850, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.addWidget(label(result.title, "heading", True))
        layout.addWidget(label(result.url, "muted", True))
        tabs = QTabWidget()
        tabs.addTab(
            text_panel(result.original_text or "No source text supplied by this provider."),
            "Original text",
        )
        variants = {v.id: v for v in inv.plan.variants}
        records = {r.id: r for r in inv.results}
        path = []
        for node in result.discovery_path:
            if node == inv.id:
                path.append("SEARCH: " + inv.query)
            elif node in variants:
                v = variants[node]
                path.append(f"QUERY: {v.value}\n  {v.state} · {v.source}\n  {v.reason}")
            elif node in records:
                r = records[node]
                path.append(f"SOURCE: {r.title}\n  {r.url}")
        evidence = "\n\n↓\n\n".join(path)
        evidence += "\n\nRANKING (relevance, not a probability)\n"
        evidence += "\n".join(
            f"{key.replace('_', ' ')}: {value:g}" for key, value in result.score_breakdown.items()
        )
        evidence += (
            f"\n\nEvidence completeness: {result.evidence_score:.0f}/100\n"
            "Measures available provenance and metadata, not truth.\n"
            f"SHA-256 of supplied text: {result.content_hash}\n"
            f"First observed: {result.discovered_at}"
        )
        tabs.addTab(text_panel(evidence), "Evidence and ranking")
        related_lines = ["Shared identifiers are observations, not proof of shared identity.", ""]
        for entity in inv.entities:
            if entity.id in result.entities:
                related_lines.append(f"{entity.kind.upper()}: {entity.value}")
                related_lines += [
                    "  " + records[e].title
                    for e in entity.evidence_results
                    if e in records and e != result.id
                ]
                related_lines.append("")
        copies = [r for r in inv.results if r.duplicate_of == result.id]
        if copies:
            related_lines += ["DUPLICATE RECORDS RETAINED"]
            related_lines += [f"{r.source_provider}: {r.url}" for r in copies]
        tabs.addTab(text_panel("\n".join(related_lines)), "Related records")
        tabs.addTab(
            text_panel(json.dumps(result.metadata, ensure_ascii=False, indent=2)),
            "Provider metadata",
        )
        if result.translated_text:
            tabs.addTab(
                text_panel(
                    "MACHINE TRANSLATION\nOriginal content is preserved.\n\n"
                    + result.translated_text
                ),
                "English translation",
            )
        tabs.setCurrentIndex(2 if related else 1)
        layout.addWidget(tabs)
