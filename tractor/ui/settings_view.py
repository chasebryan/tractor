"""Provider configuration, bounded search controls, and a local privacy inventory."""

from dataclasses import asdict, replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tractor.core.convergence import BUDGET_LIMITS, Budget
from tractor.settings import Settings
from tractor.sources.base import SearchOptions
from tractor.sources.catalog import PROFILES, catalog, configuration, select_profile
from tractor.storage.health import provider_health
from tractor.ui.theme import label


class SettingsView(QDialog):
    def __init__(self, settings, data_dir, connection, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.data_dir = data_dir
        self.setWindowTitle("Search settings")
        self.resize(790, 720)
        outer = QVBoxLayout(self)
        outer.addWidget(label("Search configuration", "heading"))
        outer.addWidget(
            label("Choose where queries go and how far an investigation runs.", "muted")
        )
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        providers = self.page("Providers")
        self.profile = QComboBox()
        self.profile.addItems(["Custom", *PROFILES])
        self.profile.setCurrentText(settings.profile)
        providers.addWidget(label("Search profile", "section"))
        providers.addWidget(self.profile)
        providers.addWidget(
            label(
                "Profiles select available providers. Maximum coverage increases search budgets; "
                "it can cost more API credits and take longer. No search is exhaustive.",
                "muted",
                True,
            )
        )
        adapters = {a.id: a for a in catalog(settings)}
        states = configuration(settings)
        health = provider_health(connection)
        self.checks = {}
        for group, keys in (
            ("Web search", ["brave", "mojeek", "kagi", "marginalia", "searxng"]),
            (
                "Specialized sources",
                [
                    "wikidata",
                    "crossref",
                    "europe_pmc",
                    "internet_archive",
                    "github",
                    "gdelt",
                    "common_crawl",
                ],
            ),
            ("Tor", ["torch", "onion_searxng"]),
        ):
            providers.addSpacing(16)
            providers.addWidget(label(group.upper(), "section"))
            for key in keys:
                state = states[key]
                check = QCheckBox(state["name"])
                check.setChecked(key in settings.sources)
                check.setAccessibleName("Enable " + key)
                providers.addWidget(check)
                status = label("", "muted", True)

                def status_text(checked, *, status=status, state=state, key=key):
                    text = (
                        state["configuration"]
                        if checked
                        else "Disabled · " + state["configuration"]
                    )
                    recent = health.get(key)
                    if recent:
                        text += (
                            f" · Last run: {recent['last_status']} · "
                            f"{recent['success_rate']:.0%} recent success · "
                            f"{recent['median_latency_ms'] / 1000:.1f}s median"
                        )
                    status.setText(text)

                check.toggled.connect(status_text)
                status_text(check.isChecked())
                providers.addWidget(status)
                if key in adapters:
                    providers.addWidget(label(adapters[key].description, "muted", True))
                if state["environment_variable"]:
                    providers.addWidget(
                        label("Credential: " + state["environment_variable"], "muted")
                    )
                self.checks[key] = check
        providers.addWidget(
            label(
                "Set API keys in your environment before launching. Keys are "
                "never written to settings "
                "or SQLite. Optional operating-system keychain entry is deferred. "
                "Test a provider with: tractor --test-provider PROVIDER_ID",
                "muted",
                True,
            )
        )
        providers.addWidget(
            label(
                "Marginalia's public key is for development and shares rate limits. Its returned "
                "license is retained with each record. Use an appropriate key for commercial use.",
                "muted",
                True,
            )
        )
        self.mojeek_storage = QCheckBox("My Mojeek plan permits persistent result storage")
        self.mojeek_storage.setChecked(settings.search.mojeek_storage_allowed)
        providers.addWidget(self.mojeek_storage)
        providers.addWidget(
            label("Required for Mojeek: check your plan's storage rights.", "muted")
        )

        connection_layout = self.page("Connections")
        form = QFormLayout()
        self.web = QLineEdit(settings.web_endpoint)
        self.onion = QLineEdit(settings.onion_endpoint)
        self.proxy = QLineEdit(settings.tor_proxy)
        self.web.setPlaceholderText("https://your-search-server.example")
        self.onion.setPlaceholderText("http://your-v3-server.onion")
        self.proxy.setPlaceholderText("Automatic: local port 9050 or 9150")
        form.addRow("SearxNG server", self.web)
        form.addRow("Onion SearxNG server", self.onion)
        form.addRow("Local Tor proxy", self.proxy)
        connection_layout.addLayout(form)
        self.autostart = QCheckBox("Start an installed Tor client when needed")
        self.autostart.setChecked(settings.tor_autostart)
        connection_layout.addWidget(self.autostart)
        connection_layout.addWidget(
            label(
                "Use servers you operate or trust, with JSON search enabled. The "
                "onion server needs "
                "the onions category. Tor uses socks5h and never falls back to a "
                "direct connection. "
                "Automatic startup requires tor on PATH. Existing Tor clients stay running.",
                "muted",
                True,
            )
        )

        search = self.page("Search controls")
        form = QFormLayout()
        self.language = QLineEdit(settings.search.language)
        self.region = QLineEdit(settings.search.region)
        self.category = QComboBox()
        self.category.addItems(["general", "news"])
        self.category.setCurrentText(settings.search.category)
        self.freshness = QComboBox()
        self.freshness.addItems(["any", "day", "week", "month", "year", "custom"])
        self.freshness.setCurrentText(settings.search.freshness)
        self.after = QLineEdit(settings.search.after)
        self.before = QLineEdit(settings.search.before)
        self.after.setPlaceholderText("YYYY-MM-DD")
        self.before.setPlaceholderText("YYYY-MM-DD")
        self.collection = QLineEdit(settings.search.common_crawl_collection)
        self.collection.setPlaceholderText("Latest collection at first request")
        self.per_domain = QSpinBox()
        self.per_domain.setRange(1, 100)
        self.per_domain.setValue(settings.search.results_per_domain)
        for title, widget in (
            ("Language (auto / all / code)", self.language),
            ("Region (two-letter code)", self.region),
            ("Category", self.category),
            ("Freshness", self.freshness),
            ("After", self.after),
            ("Before", self.before),
            ("Common Crawl collection", self.collection),
            ("Marginalia results per domain", self.per_domain),
        ):
            form.addRow(title, widget)
        search.addLayout(form)
        search.addWidget(
            label(
                "Controls apply where an API supports them. Coverage lists unsupported requests. "
                "A region is a search hint, not evidence of a publisher's location. Common Crawl "
                "accepts known URLs or domains and returns capture metadata only.",
                "muted",
                True,
            )
        )
        self.budgets = {}
        budget_form = QFormLayout()
        for key, (_, maximum) in BUDGET_LIMITS.items():
            field = QSpinBox()
            field.setRange(1, int(maximum))
            field.setValue(int(getattr(settings.budget, key)))
            budget_form.addRow(
                key.replace("max_", "Maximum ").replace("_", " ").capitalize(), field
            )
            self.budgets[key] = field
        search.addSpacing(15)
        search.addWidget(label("Investigation budgets", "section"))
        search.addLayout(budget_form)
        search.addWidget(
            label(
                "Limits bound each run. Continue retains queued pages. Network "
                "response-size and routing limits remain fixed.",
                "muted",
                True,
            )
        )
        self.profile.currentTextChanged.connect(self.apply_profile)
        privacy = self.page("Privacy")
        privacy.addWidget(label("Your search footprint", "heading"))
        privacy.addWidget(
            label(
                "Enabled clearnet providers receive queries, generated spelling "
                "candidates, and source-backed aliases directly. "
                "API providers also receive their own authentication token. "
                "Mojeek's documented API puts its key in the "
                "HTTPS query string; the application keeps authenticated request "
                "URLs out of logs and persistent caches. "
                "Providers may retain requests under their policies. Kagi results "
                "can reflect account settings.\n\n"
                "SearxNG and its upstream engines receive queries. Onion indexes "
                "use a separate Tor connection. "
                "Other providers still connect directly: this is not an "
                "application-wide anonymity mode. "
                "Onion destinations are never fetched automatically.\n\n"
                "Investigations, public-response caches and bounded provider "
                "health stay on this device. "
                "Authenticated responses are cached only in memory during a run. "
                "No application telemetry is sent. "
                "Exports contain your queries and evidence; choose recipients accordingly.\n\n"
                "Saved records contain original provider text. Translation and AI "
                "answers are not required by the engine.\n\n"
                "Local storage: " + str(data_dir),
                "muted",
                True,
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def page(self, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, title)
        return layout

    def apply_profile(self, profile):
        if profile == "Custom":
            return
        draft = replace(
            self.settings,
            web_endpoint=self.web.text().strip(),
            onion_endpoint=self.onion.text().strip(),
            search=replace(
                self.settings.search, mojeek_storage_allowed=self.mojeek_storage.isChecked()
            ),
        )
        try:
            selected = select_profile(draft, profile)
        except ValueError:
            return
        for key, check in self.checks.items():
            check.setChecked(key in selected)
        defaults = asdict(Budget())
        if profile == "Maximum coverage":
            defaults.update(
                max_jobs=240,
                max_variants=24,
                max_pages_per_query=6,
                max_seconds=900,
                max_results=6000,
            )
        for key, value in defaults.items():
            self.budgets[key].setValue(int(value))
        self.category.setCurrentText("news" if profile == "News" else "general")

    def save(self):
        try:
            selected = [key for key, field in self.checks.items() if field.isChecked()]
            if not selected:
                raise ValueError("Select at least one provider.")
            if "searxng" in selected and not self.web.text().strip():
                raise ValueError("Enter a SearxNG server URL in Connections.")
            if "onion_searxng" in selected and not self.onion.text().strip():
                raise ValueError("Enter an onion SearxNG server URL in Connections.")
            options = SearchOptions(
                self.language.text().strip(),
                self.region.text().strip(),
                self.category.currentText(),
                self.freshness.currentText(),
                self.after.text().strip(),
                self.before.text().strip(),
                self.per_domain.value(),
                self.collection.text().strip(),
                self.mojeek_storage.isChecked(),
            )
            updated = Settings(
                selected,
                self.web.text(),
                self.proxy.text(),
                self.autostart.isChecked(),
                self.onion.text(),
                search=options,
                budget=Budget(**{key: field.value() for key, field in self.budgets.items()}),
                profile=self.profile.currentText(),
            )
            updated.save(self.data_dir)
        except (ValueError, OSError) as exc:
            QMessageBox.information(self, "Check settings", str(exc))
            return
        self.settings = updated
        self.accept()
