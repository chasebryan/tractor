import itertools
import json
import math
import statistics
import time
from pathlib import Path

from tractor.core.deduplication import DuplicateIndex, normalize_result
from tractor.core.models import Investigation, QueryVariant, SourceResult
from tractor.core.query import build_plan
from tractor.core.scoring import rank_results


def ranking_metrics(ranked_ids, judgments):
    relevant = {key for key, grade in judgments.items() if grade > 0}
    metrics = {}
    for k in (10, 50):
        metrics[f"recall_at_{k}"] = len(set(ranked_ids[:k]) & relevant) / max(1, len(relevant))
    metrics["mrr"] = next((1 / i for i, key in enumerate(ranked_ids, 1) if key in relevant), 0)
    dcg = sum(
        (2 ** judgments.get(key, 0) - 1) / math.log2(i + 2) for i, key in enumerate(ranked_ids[:10])
    )
    ideal = sum(
        (2**grade - 1) / math.log2(i + 2)
        for i, grade in enumerate(sorted(judgments.values(), reverse=True)[:10])
    )
    metrics["ndcg_at_10"] = dcg / ideal if ideal else 0.0
    return metrics


def pair_metrics(predicted, expected):
    true_positive = len(predicted & expected)
    return {
        "precision": true_positive / len(predicted) if predicted else 1.0,
        "recall": true_positive / len(expected) if expected else 1.0,
    }


def run_benchmark(path: Path | None = None) -> dict:
    fixture = json.loads(
        (path or Path(__file__).with_name("fixtures-v1.json")).read_text(encoding="utf-8")
    )
    if fixture["schema_version"] != 1:
        raise ValueError("Unsupported benchmark schema")
    cases = []
    for case in fixture["cases"]:
        started = time.perf_counter()
        plan = build_plan(case["query"])
        for alias in case.get("source_aliases", []):
            plan.variants.append(
                QueryVariant(
                    alias,
                    source="fixture_source",
                    kind="discovered_alias",
                    state="discovered",
                    reason=(
                        "Source-backed candidate in the synthetic fixture; no identity assertion."
                    ),
                )
            )
        inv = Investigation(case["query"], plan)
        index = DuplicateIndex()
        expected_groups = {}
        actual_groups = {}
        for raw in case["records"]:
            values = {
                key: value for key, value in raw.items() if key not in {"duplicate_group", "grade"}
            }
            result = SourceResult(**values)
            normalize_result(result)
            result.discovery_path = [inv.id, plan.variants[0].id, result.id]
            duplicate = index.find(result)
            if duplicate:
                result.duplicate_of = duplicate[0]
            index.add(result)
            inv.results.append(result)
            expected_groups.setdefault(raw.get("duplicate_group", result.id), []).append(result.id)
            actual_groups.setdefault(result.duplicate_of or result.id, []).append(result.id)
        rank_results(inv)
        judgments = case["judgments"]
        ids = {r.id for r in inv.results}
        if not set(judgments) <= ids or len(ids) != len(inv.results):
            raise ValueError("Invalid benchmark record IDs or judgments")
        expected_pairs = {
            tuple(sorted(pair))
            for group in expected_groups.values()
            for pair in itertools.combinations(group, 2)
        }
        actual_pairs = {
            tuple(sorted(pair))
            for group in actual_groups.values()
            for pair in itertools.combinations(group, 2)
        }
        metrics = ranking_metrics([r.id for r in inv.unique_results], judgments)
        metrics.update(
            {
                "dedup_" + key: value
                for key, value in pair_metrics(actual_pairs, expected_pairs).items()
            }
        )
        candidates = {v.value for v in plan.variants if v.source != "seed"}
        allowed = set(case.get("acceptable_candidates", [])) | set(case.get("source_aliases", []))
        metrics["candidate_precision"] = (
            len(candidates & allowed) / len(candidates) if candidates else None
        )
        top = inv.unique_results[:10]
        metrics.update(
            domain_diversity_at_10=len({r.canonical_url.split("/")[2] for r in top}),
            provider_diversity_at_10=len({r.source_provider for r in top}),
            source_types=len({r.source_type for r in top}),
            languages=len({r.original_language for r in top} - {"und"}),
            duplicate_ratio=sum(bool(r.duplicate_of) for r in inv.results)
            / max(1, len(inv.results)),
            runtime_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        cases.append(
            {
                "id": case["id"],
                "tags": case["tags"],
                "metrics": metrics,
                "ranking": [r.id for r in top],
            }
        )
    metrics = {
        key: round(
            statistics.mean(c["metrics"][key] for c in cases if c["metrics"][key] is not None), 4
        )
        for key in cases[0]["metrics"]
        if any(c["metrics"][key] is not None for c in cases)
    }
    minimums = fixture.get("minimum_metrics", {})
    failed = [key for key, minimum in minimums.items() if metrics.get(key, 0) < minimum]
    return {
        "fixture_version": fixture["fixture_version"],
        "ranking_version": 2,
        "scope": "Synthetic engineering fixtures; measured recall is within "
        "labeled fixture records, not the web.",
        "network_requests": 0,
        "network_latency_ms": None,
        "requests_per_useful_result": None,
        "case_count": len(cases),
        "metrics": metrics,
        "failed_thresholds": failed,
        "passed": not failed,
        "cases": cases,
    }
