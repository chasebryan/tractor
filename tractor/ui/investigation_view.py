from PySide6.QtWidgets import QDialog, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from tractor.core.models import Investigation
from tractor.ui.source_view import text_panel
from tractor.ui.theme import label


class InvestigationView(QDialog):
    def __init__(self, inv: Investigation, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TRACTOR · Investigation coverage")
        self.resize(960, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label("Investigation coverage", "heading"))
        layout.addWidget(
            label(
                "Actual attempts and evidence trails. Coverage is bounded by enabled "
                "sources, provider limits, and the investigation budget.",
                "muted",
                True,
            )
        )
        tabs = QTabWidget()

        def display_value(value: object) -> str:
            if isinstance(value, list):
                return ", ".join(map(str, value)) if value else "Not identified"
            return str(value)

        coverage = "\n".join(
            f"{key.replace('_', ' ').title()}: {display_value(value)}"
            for key, value in inv.coverage.items()
        )
        coverage += f"\n\nStatus: {inv.status}\n{inv.stop_reason}\n"
        coverage += f"\nNew unique records per completed pass: {inv.pass_yields}\n"
        coverage += "\nInvestigation limits\n" + "\n".join(
            f"{key.replace('_', ' ').replace('max ', 'Maximum ').capitalize()}: {value}"
            for key, value in inv.budget.items()
        )
        tabs.addTab(text_panel(coverage), "Coverage")
        attempts = QTreeWidget()
        attempts.setHeaderLabels(["Source / query", "Pass", "Status", "Records", "Details"])
        for a in inv.attempts:
            item = QTreeWidgetItem(
                [
                    f"{a.provider} · {a.query}",
                    str(a.pass_number),
                    a.status,
                    str(a.result_count),
                    a.error or ("Provider response limited" if a.truncated else ""),
                ]
            )
            attempts.addTopLevelItem(item)
        attempts.setColumnWidth(0, 360)
        tabs.addTab(attempts, "Source attempts")
        variants = QTreeWidget()
        variants.setHeaderLabels(["Query variant", "Language", "State", "Why it exists"])
        for v in inv.plan.variants:
            variants.addTopLevelItem(QTreeWidgetItem([v.value, v.language, v.state, v.reason]))
        variants.setColumnWidth(0, 250)
        variants.setColumnWidth(3, 600)
        tabs.addTab(variants, "Query plan")
        graph = QTreeWidget()
        graph.setHeaderLabels(["Evidence relationship", "State", "Confidence"])
        names = {
            inv.id: inv.query,
            **{v.id: v.value for v in inv.plan.variants},
            **{r.id: r.title for r in inv.results},
            **{e.id: e.value for e in inv.entities},
        }
        for edge in inv.edges:
            node = QTreeWidgetItem(
                [
                    f"{names.get(edge.source, edge.source)} → {edge.kind} → "
                    f"{names.get(edge.target, edge.target)}",
                    edge.state,
                    f"{edge.confidence:.2f}",
                ]
            )
            node.addChild(QTreeWidgetItem([edge.explanation]))
            graph.addTopLevelItem(node)
        graph.setColumnWidth(0, 700)
        tabs.addTab(graph, "Evidence graph")
        layout.addWidget(tabs)
