#!/bin/sh
# circuit-breaker.sh — PreToolUse, PostToolUse and PostToolUseFailure hook.
# The logic is circuit_breaker.py; lib/python.sh finds a Python to run it. Source: Nova Caelum (Apache-2.0).
HOOKS_DIR="$(dirname "$0")"
# shellcheck source=lib/python.sh disable=SC1091
. "$HOOKS_DIR/lib/python.sh"
run_hook circuit_breaker
