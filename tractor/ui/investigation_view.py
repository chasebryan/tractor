from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

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
        metrics = QHBoxLayout()
        for count, title in (
            (len(inv.unique_results), "UNIQUE RECORDS"),
            (len(inv.coverage["known_independent_search_indexes"]), "KNOWN INDEPENDENT INDEXES"),
            (len(inv.coverage["domains_represented"]), "HOST DOMAINS"),
            (len(inv.pending_tasks), "SEARCHES PENDING"),
        ):
            metrics.addWidget(label(f"{count:,}\n{title}", "muted", True))
        layout.addLayout(metrics)
        layout.addWidget(
            label(
                "Multiple indexes are discovery paths, not independent factual confirmation.",
                "muted",
                True,
            )
        )

        def display_value(value: object) -> str:
            if isinstance(value, list):
                return ", ".join(map(str, value)) if value else "Not identified"
            return str(value)

        coverage = "\n".join(
            f"{key.replace('_', ' ').title()}: {display_value(value)}"
            for key, value in inv.coverage.items()
        )
        coverage += f"\n\nStatus: {inv.status}\n{inv.stop_reason}\n"
        coverage += f"\nNew unique records by discovery pass: {inv.pass_yields}\n"
        coverage += f"\nProfile: {inv.profile}\n"
        coverage += "\n".join(
            f"{key.replace('_', ' ')}: {value}" for key, value in inv.search_options.items()
        )
        if inv.previous_investigation:
            coverage += f"\nRefreshed from investigation: {inv.previous_investigation}\n"
        coverage += "\nCoverage notes\n" + (
            "\n".join(inv.limits) or "No additional limits reported."
        )
        coverage += "\nInvestigation limits\n" + "\n".join(
            f"{key.replace('_', ' ').replace('max ', 'Maximum ').capitalize()}: {value}"
            for key, value in inv.budget.items()
        )
        tabs.addTab(text_panel(coverage), "Coverage")
        providers = QTreeWidget()
        providers.setHeaderLabels(
            ["Provider", "Configuration", "Attempts", "Unique / duplicate", "Recent health"]
        )
        for key in dict.fromkeys([*inv.provider_configuration, *inv.source_ids]):
            state = inv.provider_configuration.get(key, {})
            rows = [a for a in inv.attempts if a.provider == key]
            health = inv.provider_health.get(key, {})
            item = QTreeWidgetItem(
                [
                    state.get("name", key),
                    ("Enabled · " if state.get("enabled", True) else "Disabled · ")
                    + state.get("configuration", "Not recorded"),
                    str(len(rows)),
                    f"{sum(a.unique_yield for a in rows)} / {sum(a.duplicate_yield for a in rows)}",
                    (
                        f"{health['success_rate']:.0%} success · "
                        f"{health['median_latency_ms'] / 1000:.1f}s median"
                        if health
                        else "No completed requests"
                    ),
                ]
            )
            for note in sorted({note for a in rows for note in a.warnings}):
                item.addChild(QTreeWidgetItem([note]))
            if health.get("last_error_class"):
                item.addChild(
                    QTreeWidgetItem(["Latest error class: " + health["last_error_class"]])
                )
            if state.get("capabilities"):
                item.addChild(
                    QTreeWidgetItem(
                        [
                            "Supports: "
                            + ", ".join(
                                k.replace("_", " ")
                                for k, supported in state["capabilities"].items()
                                if supported
                            )
                        ]
                    )
                )
            providers.addTopLevelItem(item)
        providers.setColumnWidth(0, 230)
        providers.setColumnWidth(1, 240)
        tabs.addTab(providers, "Providers and health")
        attempts = QTreeWidget()
        attempts.setHeaderLabels(
            ["Source / query", "Network", "Run / pass / page", "Status", "Records", "Details"]
        )
        for a in inv.attempts:
            item = QTreeWidgetItem(
                [
                    f"{a.provider} · {a.query}",
                    a.network.title(),
                    f"{a.run_number} / {a.pass_number} / {a.page}",
                    a.status,
                    str(a.result_count),
                    (a.error or "; ".join(a.warnings))
                    or (
                        f"{a.duration_ms / 1000:.1f}s · {a.cached_requests} cached · "
                        f"{a.network_requests} requests"
                        + (" · more matches available" if a.truncated else "")
                    ),
                ]
            )
            attempts.addTopLevelItem(item)
        attempts.setColumnWidth(0, 360)
        tabs.addTab(attempts, "Source attempts")
        pending = QTreeWidget()
        pending.setHeaderLabels(["Provider", "Query", "Pass", "Next page"])
        names = {v.id: v.value for v in inv.plan.variants}
        for task in inv.pending_tasks:
            pending.addTopLevelItem(
                QTreeWidgetItem(
                    [
                        task.provider,
                        names.get(task.query_id, task.query_id),
                        str(task.pass_number),
                        str(task.page),
                    ]
                )
            )
        pending.setColumnWidth(1, 380)
        tabs.addTab(pending, f"Remaining work ({len(inv.pending_tasks)})")
        variants = QTreeWidget()
        variants.setHeaderLabels(
            ["Query variant", "Language / script", "State / kind", "Why it exists"]
        )
        for v in inv.plan.variants:
            variants.addTopLevelItem(
                QTreeWidgetItem(
                    [v.value, f"{v.language} / {v.script}", f"{v.state} / {v.kind}", v.reason]
                )
            )
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
