#!/bin/sh
set -eu
app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for interpreter in python3.12 python3.13 python3.11 python3; do
    if command -v "$interpreter" >/dev/null 2>&1 && "$interpreter" -c 'import sys; sys.exit(not (3,11) <= sys.version_info[:2] <= (3,13))' 2>/dev/null; then
        exec "$interpreter" "$app_dir/scripts/launch.py" "$@"
    fi
done
printf '%s\n' 'Python 3.11–3.13 is required. Install Python 3.12, then run this launcher again.' >&2
exit 1
