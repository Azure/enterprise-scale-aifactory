#!/usr/bin/env bash
# BLUE v1.26 entry point: one script for the GitHub mirror, GitHub settings and the registered consumer.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'USAGE'
usage: bash aifactory.sh <command> [options]

commands:
  mirror    Mirror this template into your GitHub repository (once).
  init      Install the pinned registered helpers and an empty azurefactory/register.json (once).
  sync      Create or update the GitHub environments, variables and secrets from .env.
  refresh   Refresh the registered helpers and the scoped GitHub workflow from the pinned PURPLE.
  deploy    Retired: prints the registered azurefactory.sh guidance and fails closed.

Run "bash aifactory.sh <command> --help" for the options of a command.
Set AIFACTORY_PYTHON to choose the Python 3.9+ interpreter.
USAGE
}

if [[ $# -eq 0 ]]; then
    usage >&2
    exit 2
fi
command_name="$1"
shift
case "$command_name" in
    -h|--help) usage; exit 0 ;;
    mirror|sync) target=(bootstrap/github_bootstrap.py "$command_name") ;;
    init|refresh|deploy) target=(bootstrap/consumer.py "$command_name") ;;
    *) printf 'ERROR: unknown command: %s\n\n' "$command_name" >&2; usage >&2; exit 2 ;;
esac

if [[ -n "${AIFACTORY_PYTHON:-}" ]]; then
    python_command=("$AIFACTORY_PYTHON")
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_command=(python3)
elif command -v python >/dev/null 2>&1 && python -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    python_command=(python)
else
    printf 'ERROR: Python 3.9 or newer is required (Windows Store aliases are not interpreters).\n' >&2
    exit 2
fi
exec "${python_command[@]}" -B "$SCRIPT_DIR/${target[0]}" "${target[@]:1}" "$@"
