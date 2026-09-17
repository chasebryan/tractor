import json
from pathlib import Path

from tractor.core.models import Investigation
from tractor.storage.atomic import atomic_text


def export_json(inv: Investigation, path: Path) -> None:
    with atomic_text(path) as file:
        json.dump(inv.to_dict(), file, ensure_ascii=False, indent=2)
