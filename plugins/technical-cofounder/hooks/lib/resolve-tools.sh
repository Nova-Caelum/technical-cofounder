#!/bin/bash
# lib/resolve-tools.sh — find Python and jq without trusting PATH alone.
#
# Source: Nova Caelum (2026). License: Apache-2.0.
#
# Sourced by every hook in this plugin. Sets and exports two variables:
#
#   NC_PYTHON  the first of these that exists and runs:
#                ${CLAUDE_PROJECT_DIR}/.hyperspace/env/bin/python
#                ${CLAUDE_PROJECT_DIR}/.hyperspace/env/Scripts/python.exe
#                python3, python, then `py -3` on PATH
#              `py -3` is stored as the interpreter it starts, so the value
#              is always one word a hook can run as "$NC_PYTHON".
#   NC_JQ      the first of these that runs:
#                jq on PATH
#                ${NC_TOOLS_DIR:-$HOME/.local/bin}/jq, then the same with .exe
#
# Either is empty when nothing runs. A hook uses "$NC_PYTHON" and "$NC_JQ"
# where it would have written python3 and jq, and tests [ -n "$NC_JQ" ] where
# it would have written `command -v jq`.
#
# Why "runs" and not just "exists": a file can be there and still not start
# (the Windows Store alias named python3, a binary the system refuses to
# launch). So every candidate is started once, with its input closed, before
# it is chosen.
# Python is started with -S (no site import): the probe runs on every hook
# event, and -S is the cheapest start that still proves the interpreter runs.
#
# Prints nothing and never exits: sourcing this cannot break a hook.

nc_resolve_python() {
    local project="${CLAUDE_PROJECT_DIR:-}" candidate found
    if [ -n "$project" ]; then
        for candidate in "$project/.hyperspace/env/bin/python" "$project/.hyperspace/env/Scripts/python.exe"; do
            if [ -f "$candidate" ] && "$candidate" -S -c '' </dev/null >/dev/null 2>&1; then
                printf '%s' "$candidate"
                return 0
            fi
        done
    fi
    for candidate in python3 python; do
        if "$candidate" -S -c '' </dev/null >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    found="$(py -3 -c 'import sys; print(sys.executable)' </dev/null 2>/dev/null)" || found=""
    printf '%s' "${found%$'\r'}"
    return 0
}

nc_resolve_jq() {
    local tools="${NC_TOOLS_DIR:-${HOME:-}/.local/bin}" candidate
    for candidate in jq "$tools/jq" "$tools/jq.exe"; do
        if "$candidate" --version </dev/null >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 0
}

NC_PYTHON="$(nc_resolve_python)"
NC_JQ="$(nc_resolve_jq)"
export NC_PYTHON NC_JQ
