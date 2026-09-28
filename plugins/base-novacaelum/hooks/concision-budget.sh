#!/bin/sh
# concision-budget.sh — UserPromptSubmit hook. The logic is concision_budget.py; lib/python.sh
# finds a Python to run it. Source: Nova Caelum (Apache-2.0).
HOOKS_DIR="$(dirname "$0")"
# shellcheck source=lib/python.sh disable=SC1091
. "$HOOKS_DIR/lib/python.sh"
run_hook concision_budget
