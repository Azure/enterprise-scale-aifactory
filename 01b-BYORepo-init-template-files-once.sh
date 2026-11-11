#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${AIFACTORY_PYTHON:-}" ]]; then
    python_command=("$AIFACTORY_PYTHON")
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_command=(python3)
elif command -v python >/dev/null 2>&1 && python -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_command=(python)
else
    printf 'ERROR: Python 3.9 or newer is required.\n' >&2
    exit 2
fi
exec "${python_command[@]}" -B "$SCRIPT_DIR/bootstrap/consumer.py" init "$@"
