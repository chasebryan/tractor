import csv
from pathlib import Path

from tractor.core.models import Investigation


def safe_cell(value: object) -> str:
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def export_csv(inv: Investigation, path: Path) -> None:
    fields = [
        "id",
        "title",
        "url",
        "source_type",
        "source_provider",
        "published_at",
        "original_language",
        "excerpt",
        "relevance_score",
        "duplicate_of",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        for result in inv.results:
            writer.writerow(safe_cell(getattr(result, name)) for name in fields)
