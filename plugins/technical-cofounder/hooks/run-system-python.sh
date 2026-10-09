#!/bin/bash
# run-system-python.sh — run one of this plugin's standard-library-only Python
# hooks with this computer's own Python, never the project's.
#
# Source: Nova Caelum (2026). License: Apache-2.0.
#
# Usage (hooks.json):  run-system-python.sh <script.py> [args...]
#
# The event's JSON on standard input and the script's standard output go
# through untouched. Python is found by lib/resolve-tools.sh, the resolver every
# hook here shares, but only its system half (python3, python, `py -3`): the
# project's `.hyperspace/env` is not tried even as a last resort. A downloaded
# folder can ship a file at that path, a hook like this one runs in every
# folder Claude Code opens, and a script that imports only the standard library
# has no use for the project's environment.
#
# Fails open: no Python, or a script that errors, prints nothing and exits 0. A
# guardrail that can break a tool call is worse than none. Standard error is
# discarded, as the command this replaced did.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || exit 0

# shellcheck source=lib/resolve-tools.sh disable=SC1091
source "$HERE/lib/resolve-tools.sh" 2>/dev/null || exit 0
NC_PYTHON="$(nc_resolve_system_python)" || NC_PYTHON=""

if [ -z "$NC_PYTHON" ] || [ "$#" -eq 0 ]; then
    cat >/dev/null 2>&1 || true
    exit 0
fi

"$NC_PYTHON" "$@" 2>/dev/null || true
exit 0
