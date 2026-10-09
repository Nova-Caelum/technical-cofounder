#!/bin/bash
# lib/resolve-tools.sh — find Python and jq without trusting PATH alone.
#
# Source: Nova Caelum (2026). License: Apache-2.0.
#
# Sourced by every hook in this plugin. Sourcing it does two things:
#
#   NC_JQ      is set and exported: the first of these that runs,
#                jq on PATH
#                ${NC_TOOLS_DIR:-$HOME/.local/bin}/jq, then the same with .exe
#              It is empty when none runs. A hook uses "$NC_JQ" where it would
#              have written jq, and tests [ -n "$NC_JQ" ] where it would have
#              written `command -v jq`.
#   nc_resolve_system_python
#              is defined, and not called. It prints the first of these that
#              runs, or nothing:
#                python3, python, then `py -3` on PATH
#              `py -3` is printed as the interpreter it starts, so the result
#              is always one word a hook can run. A hook whose script needs
#              only the standard library uses this one: it can never start a
#              file the project folder ships.
#   nc_resolve_python
#              is defined, and not called. It prints what
#              nc_resolve_system_python finds and, when that is nothing, the
#              first of these that runs, or nothing:
#                ${CLAUDE_PROJECT_DIR}/.hyperspace/env/bin/python
#                ${CLAUDE_PROJECT_DIR}/.hyperspace/env/Scripts/python.exe
#              The project's own interpreter is the last resort, never the
#              first choice: a downloaded repository can ship a file at that
#              path, and a hook must not start it while this machine has a
#              Python of its own. Use it only where the script needs the
#              project's environment.
#
# Python is looked for only by the hook that uses it (session-preload.sh):
# finding it means starting it, and the guardrail hooks run on every prompt
# and every tool call without needing it.
#
# Why "runs" and not just "exists": a file can be there and still not start
# (the Windows Store alias named python3, a binary the system refuses to
# launch). So every candidate is started once, with its input closed, before
# it is chosen. Python is started with -S (no site import), the cheapest start
# that still proves the interpreter runs.
#
# Prints nothing and never exits: sourcing this cannot break a hook.

nc_resolve_system_python() {
    local candidate found
    for candidate in python3 python; do
        if "$candidate" -S -c '' </dev/null >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    # The launcher reports a Windows path ending in a carriage return. Kept
    # with forward slashes, bash runs it as a path, not as a command name.
    found="$(py -3 -c 'import sys; print(sys.executable)' </dev/null 2>/dev/null)" || found=""
    found="${found%$'\r'}"
    if [ -n "$found" ]; then
        printf '%s' "${found//\\//}"
    fi
    return 0
}

nc_resolve_python() {
    local project="${CLAUDE_PROJECT_DIR:-}" candidate found
    found="$(nc_resolve_system_python)"
    if [ -n "$found" ]; then
        printf '%s' "$found"
        return 0
    fi
    [ -n "$project" ] || return 0
    for candidate in "$project/.hyperspace/env/bin/python" "$project/.hyperspace/env/Scripts/python.exe"; do
        if [ -f "$candidate" ] && "$candidate" -S -c '' </dev/null >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
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

NC_JQ="$(nc_resolve_jq)"
export NC_JQ
