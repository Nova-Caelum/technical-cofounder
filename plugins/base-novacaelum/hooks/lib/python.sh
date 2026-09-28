# shellcheck shell=sh
# lib/python.sh — the plugin's one interpreter rule, sourced by every hook shim.
#
# Source: Nova Caelum (Apache-2.0).
#
# POSIX sh: runs under `sh` on macOS and Linux and under Git Bash on Windows.
# Candidates, in order: the project's own environment (.cofounder/env, in the
# POSIX `bin/python` layout or the Windows `Scripts/python.exe` one), python3,
# python, then the Windows launcher `py -3`. Each candidate is EXECUTED before
# it is trusted: on Windows `python3` can be the Microsoft Store placeholder,
# which prints an install prompt and exits non-zero instead of running.
# Probes read /dev/null, so the hook's JSON on stdin reaches the hook intact.

python_ok() {
    "$@" -c "import sys" </dev/null >/dev/null 2>&1
}

# Sets PY (and PY_ARG, "-3" for the py launcher) to the first candidate
# python_ok accepts; returns 1 when none runs.
find_python() {
    PY=""
    PY_ARG=""
    env_dir="${CLAUDE_PROJECT_DIR:-$PWD}/.cofounder/env"
    for candidate in "$env_dir/bin/python" "$env_dir/Scripts/python.exe"; do
        if { [ -f "$candidate" ] || [ -f "$candidate.exe" ]; } && python_ok "$candidate"; then
            PY="$candidate"
            return 0
        fi
    done
    for name in python3 python; do
        candidate="$(command -v "$name" 2>/dev/null)" || candidate=""
        if [ -n "$candidate" ] && python_ok "$candidate"; then
            PY="$candidate"
            return 0
        fi
    done
    candidate="$(command -v py 2>/dev/null)" || candidate=""
    if [ -n "$candidate" ] && python_ok "$candidate" -3; then
        PY="$candidate"
        PY_ARG="-3"
        return 0
    fi
    return 1
}

# run_hook <module> [notice]: exec "$HOOKS_DIR/<module>.py" with the resolved
# Python, stdin untouched. Fails open: with no Python it says so on stderr (and
# on stdout too with `notice`, where a SessionStart hook's output reaches the
# session) and exits 0, so a missing interpreter never breaks the session.
run_hook() {
    if find_python; then
        exec "$PY" ${PY_ARG:+"$PY_ARG"} "$HOOKS_DIR/$1.py"
    fi
    msg="⚠️ base-novacaelum: no working Python found (tried .cofounder/env, python3, python, py -3), so the $1 hook was skipped. Install Python 3 (on Windows, from python.org, not the Store), then run /base-novacaelum:setup."
    printf '%s\n' "$msg" >&2
    if [ "${2:-}" = notice ]; then
        printf '%s\n' "$msg"
    fi
    exit 0
}
