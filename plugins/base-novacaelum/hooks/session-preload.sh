#!/bin/sh
# session-preload.sh — SessionStart hook. The logic is session_preload.py; lib/python.sh
# finds a Python to run it. Source: Nova Caelum (Apache-2.0).
HOOKS_DIR="$(dirname "$0")"
# shellcheck source=lib/python.sh disable=SC1091
. "$HOOKS_DIR/lib/python.sh"
run_hook session_preload notice
