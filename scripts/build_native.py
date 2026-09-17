"""Build one native portable bundle on the target OS; never cross-compile."""

import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "Tractor",
        "--onedir",
        "--collect-data",
        "tractor",
        "--collect-data",
        "langdetect",
        "--hidden-import",
        "tractor.packaging_smoke",
        "--distpath",
        str(root / "dist" / "native"),
        "--workpath",
        str(root / "build" / "native"),
        "--specpath",
        str(root / "build"),
        *(["--windowed"] if sys.platform == "darwin" else []),
        *(["--hide-console", "hide-early"] if sys.platform == "win32" else []),
        str(root / "scripts" / "native_entry.py"),
    ],
    cwd=root,
    check=True,
)
name = f"Tractor-{version}-{platform.system().lower()}-{platform.machine().lower()}"
folder = root / "dist" / "native"
bundle = "Tractor.app" if sys.platform == "darwin" else "Tractor"
executable = (
    folder
    / bundle
    / (
        "Contents/MacOS/Tractor"
        if sys.platform == "darwin"
        else "Tractor.exe"
        if sys.platform == "win32"
        else "Tractor"
    )
)
subprocess.run([str(executable), "--smoke-test"], check=True, timeout=90)
releases = root / "dist" / "release"
releases.mkdir(exist_ok=True)
if sys.platform == "win32":
    shutil.make_archive(str(releases / name), "zip", root_dir=folder, base_dir=bundle)
else:
    shutil.make_archive(str(releases / name), "gztar", root_dir=folder, base_dir=bundle)
print(name)
