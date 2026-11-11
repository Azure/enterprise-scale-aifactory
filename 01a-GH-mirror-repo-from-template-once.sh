#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_bin=python3
elif command -v python >/dev/null 2>&1 && python -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_bin=python
else
    printf '%s\n' 'Python 3.9 or newer is required (Windows Store aliases are not interpreters).' >&2
    exit 1
fi
exec "$python_bin" "$script_dir/bootstrap/github_bootstrap.py" mirror "$@"
