"""Verify the wheel's essential packaged resources without network requests."""

import tomllib
import zipfile
from pathlib import Path

version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
wheels = list(Path("dist").glob(f"tractor_search-{version}-*.whl"))
if len(wheels) != 1:
    raise SystemExit("Expected exactly one wheel for the current version")
with zipfile.ZipFile(wheels[0]) as wheel:
    names = set(wheel.namelist())
    for required in (
        "tractor/assets/icon.svg",
        "tractor/benchmark/fixtures-v1.json",
        "tractor/sources/search/brave.py",
        "tractor/sources/common_crawl.py",
    ):
        if required not in names:
            raise SystemExit("Missing wheel resource: " + required)
print("Wheel includes provider modules, icon and versioned benchmark data.")
