import json
from pathlib import Path

from tractor.core.models import Investigation


def export_json(inv: Investigation, path: Path) -> None:
    path.write_text(json.dumps(inv.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
