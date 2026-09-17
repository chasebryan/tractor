import html
import re
from pathlib import Path
from urllib.parse import quote

from tractor.core.models import Investigation
from tractor.storage.atomic import atomic_text


def escaped(value: object) -> str:
    text = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#!|>])", r"\\\1", text).replace("\n", " ")


def export_markdown(inv: Investigation, path: Path) -> None:
    lines = [
        f"# TRACTOR investigation: {escaped(inv.query)}",
        "",
        f"Created: {inv.created_at}  ",
        f"Status: {inv.status}  ",
        f"Stop reason: {escaped(inv.stop_reason)}",
        "",
        "## Summary",
        "",
        f"{len(inv.unique_results)} unique records collected over {inv.passes} passes. "
        "Results are observations and search candidates, not verified conclusions. "
        "Coverage is limited to the adapters and budgets recorded below.",
        "",
        "## Source coverage",
        "",
    ]
    lines += [f"- {key.replace('_', ' ')}: {escaped(value)}" for key, value in inv.coverage.items()]
    lines += ["", "## Sources and evidence trails", ""]
    for result in inv.unique_results:
        url = quote(result.url, safe=":/?=&%+#@~;,")
        lines += [
            f"### {escaped(result.title)}",
            "",
            f"[{escaped(result.source_provider)}]({url}) · {result.source_type} · "
            f"{escaped(result.original_language)} · {escaped(result.published_at or 'Undated')}",
            "",
            escaped(result.excerpt),
            "",
            f"Relevance: {result.relevance_score:.0f}/100. "
            f"Evidence completeness: {result.evidence_score:.0f}/100 (not a truth probability).",
            "",
            "Discovery trail: " + " → ".join(result.discovery_path),
            "",
            "Matched queries: " + escaped("; ".join(result.matched_queries)),
            "",
        ]
    lines += ["## Query variants", ""]
    lines += [
        f"- {escaped(v.value)} [{v.state}; {v.language}] — {escaped(v.reason)}"
        for v in inv.plan.variants
    ]
    lines += ["", "## Observed identifiers", ""]
    lines += [
        f"- {e.kind}: {escaped(e.value)}. Evidence: {', '.join(e.evidence_results)}"
        for e in inv.entities
    ]
    lines += [
        "",
        "## Relationships",
        "",
        "Shared names or domains do not establish shared identity or ownership.",
        "",
    ]
    lines += [
        f"- {e.source} → {e.kind} → {e.target} [{e.state}, {e.confidence:.2f}]. "
        f"{escaped(e.explanation)} Evidence: {', '.join(e.evidence)}"
        for e in inv.edges
    ]
    lines += ["", "## Source attempts", ""]
    lines += [
        f"- Run {a.run_number} · Pass {a.pass_number} · Page {a.page} · "
        f"{a.provider} · {escaped(a.query)}: {a.status}; "
        f"{a.result_count} records"
        + (f"; {escaped(a.error)}" if a.error else "")
        + ("; provider response limited" if a.truncated else "")
        for a in inv.attempts
    ]
    lines += ["", "## Limits and remaining work", ""]
    lines += [f"- {escaped(note)}" for note in inv.limits]
    variants = {v.id: v.value for v in inv.plan.variants}
    lines += [
        f"- Pending: {task.provider} · {escaped(variants.get(task.query_id, task.query_id))} "
        f"· page {task.page}"
        for task in inv.pending_tasks
    ]
    with atomic_text(path) as file:
        file.write("\n".join(lines) + "\n")
