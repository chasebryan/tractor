from dataclasses import asdict

import pytest
from PySide6.QtWidgets import QTabWidget

from tractor.benchmark.runner import pair_metrics, ranking_metrics, run_benchmark
from tractor.core.convergence import Budget
from tractor.core.diversity import index_families
from tractor.core.models import Attempt, SourceResult
from tractor.core.query import build_plan
from tractor.language.script import detect_script
from tractor.settings import Settings
from tractor.sources.base import SearchOptions
from tractor.storage.health import provider_health, record_health, scheduling_score
from tractor.ui.investigation_view import InvestigationView
from tractor.ui.settings_view import SettingsView


def test_metrics_penalize_bad_rank_missing_evidence_and_duplicate_errors():
    metrics = ranking_metrics(["wrong", "relevant"], {"relevant": 3, "missing": 2})
    assert metrics["mrr"] == 0.5 and metrics["recall_at_10"] == 0.5
    assert metrics["ndcg_at_10"] < 0.6
    assert pair_metrics({("a", "b"), ("b", "c")}, {("a", "b"), ("a", "c")}) == {
        "precision": 0.5,
        "recall": 0.5,
    }


def test_versioned_benchmark_detects_ranking_and_dedup_regressions():
    report = run_benchmark()
    assert report["fixture_version"] == "1.0.0" and report["case_count"] == 16
    assert report["passed"], report["failed_thresholds"]
    assert report["network_requests"] == 0 and report["network_latency_ms"] is None
    assert (
        0 < report["metrics"]["mrr"] < 1
    )  # Name collisions remain challenging; no inflated score.


def test_health_is_bounded_persistent_and_not_a_permanent_provider_ban(database):
    for i in range(205):
        attempt = Attempt(
            "brave",
            "query",
            "subject",
            "und",
            1,
            task_id=str(i),
            status="success" if i % 2 else "error",
            duration_ms=100 + i,
            error_category=None if i % 2 else "rate_limited",
            rate_limit_events=0 if i % 2 else 1,
            unique_yield=1 if i % 2 else 0,
            duplicate_yield=2 if i % 2 else 0,
            finished_at=f"2026-09-17T12:{i // 60:02d}:{i % 60:02d}+00:00",
        )
        record_health(database.connection, "fixture-investigation", attempt)
    health = provider_health(database.connection)["brave"]
    assert health["attempts"] == 200 and health["success_rate"] == 0.5
    assert health["median_latency_ms"] == 204.5
    assert health["last_error_class"] == "rate_limited" and health["rate_limit_events"] == 100
    assert health["duplicate_yield"] == 200 and health["last_success_at"]
    assert -0.5 <= scheduling_score(health) <= 2
    assert scheduling_score({"success_rate": 0}) == 0


def test_script_and_language_are_independent_and_candidates_are_hypotheses():
    assert detect_script("Владимир") == "Cyrl"
    assert detect_script("東京かな") == "Jpan"
    assert detect_script("محمد") == "Arab"
    plan = build_plan("Mara Chen")
    assert plan.variants[0].language == "und" and plan.variants[0].script == "Latn"
    assert all(v.state == "discovered" for v in plan.variants[1:])
    assert {v.kind for v in plan.variants[1:]} == {"mechanical_variant", "provider_hint"}
    assert "Nordlicht Gesellschaft mit beschränkter Haftung" in {
        v.value for v in build_plan("Nordlicht GmbH").variants
    }
    assert all(
        len(build_plan(value, 4).variants) <= 2 for value in ["Acme Ltd", "Михаил Ходорковский"]
    )


def test_search_index_diversity_never_invents_unknown_independence():
    result = SourceResult(
        "Title",
        "https://example.org/",
        "WEB",
        "searxng",
        metadata={"upstream_engines": ["brave", "mojeek", "unknown-engine", "brave"]},
    )
    assert index_families(result) == {"brave", "mojeek"}
    result.metadata = {"index_family": "kagi-aggregate"}
    assert not index_families(result)


@pytest.mark.parametrize(
    "value",
    [
        {"max_jobs": 0},
        {"max_seconds": float("inf")},
        {"max_results": 10001},
        {"concurrency": True},
        {"max_pages_per_query": 1.5},
    ],
)
def test_unbounded_or_invalid_settings_are_rejected(value):
    with pytest.raises(ValueError):
        Budget(**value)


@pytest.mark.parametrize(
    "value",
    [
        {"results_per_domain": 0},
        {"region": "earth"},
        {"category": "arbitrary"},
        {"freshness": "custom", "after": "2025-02-01", "before": "2025-01-01"},
        {"common_crawl_collection": "../../evil"},
    ],
)
def test_invalid_provider_options_rejected(value):
    with pytest.raises(ValueError):
        SearchOptions(**value)


def test_settings_controls_reach_runtime_configuration_and_persist(qtbot, tmp_path, database):
    dialog = SettingsView(Settings(), tmp_path, database.connection)
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(dialog.checks) == 14
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == [
        "Providers",
        "Connections",
        "Search controls",
        "Privacy",
    ]
    dialog.profile.setCurrentText("Historical")
    dialog.language.setText("fr")
    dialog.budgets["max_jobs"].setValue(123)
    dialog.save()
    loaded = Settings.load(tmp_path)
    assert "common_crawl" in loaded.sources and loaded.search.language == "fr"
    assert loaded.budget.max_jobs == 123 and loaded.profile == "Historical"


def test_coverage_dashboard_reads_persisted_configuration(qtbot, investigation):
    investigation.source_ids = ["brave"]
    investigation.provider_configuration = {
        "brave": {"name": "Brave Search", "enabled": True, "configuration": "Credential missing"}
    }
    investigation.search_options = asdict(SearchOptions(language="fr"))
    dialog = InvestigationView(investigation)
    qtbot.addWidget(dialog)
    tabs = dialog.findChild(QTabWidget)
    assert "Providers and health" in [tabs.tabText(i) for i in range(tabs.count())]
