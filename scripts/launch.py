"""Create a private environment on first launch, then start the desktop application."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def main():
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        print("Install Python 3.12, then run this launcher with Python 3.12.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    environment = root / ".venv"
    interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    fingerprint = hashlib.sha256((root / "pyproject.toml").read_bytes()).hexdigest()
    marker = environment / ".tractor-installed"
    try:
        if not interpreter.exists():
            print("Preparing the application environment…", flush=True)
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        installed = marker.read_text() if marker.exists() else ""
        if installed != fingerprint:
            print(
                "Installing application dependencies. The first launch needs internet access…",
                flush=True,
            )
            subprocess.run(
                [
                    str(interpreter),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-e",
                    str(root),
                ],
                check=True,
            )
            marker.write_text(fingerprint)
        os.execv(str(interpreter), [str(interpreter), "-m", "tractor", *sys.argv[1:]])
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Setup could not finish: {exc}\nSee the Run section in README.md.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
