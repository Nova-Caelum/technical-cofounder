#!/usr/bin/env bash
# First step of Technical Cofounder setup on macOS and Linux.
#
# It does only what cannot wait for Python:
#   1. checks Git
#   2. installs uv if it is missing
#   3. has uv fetch Python 3.12
#   4. proves that Python by running it
# then hands over to nc_setup.py, passing along the arguments it was given.
#
#   bash bootstrap.sh [--dry-run] [nc_setup.py arguments...]
#
# Progress lines start with "bootstrap:" and go to standard error. Standard
# output gets exactly one status line from this script, always its last:
#   BOOTSTRAP=OK python=<absolute path>
#   BOOTSTRAP=NEEDS_YOU reason=<text>          (exit 3)
#   BOOTSTRAP=NEEDS_RESTART reason=<text>      (exit 4; only the Windows script needs it)
# After OK, whatever nc_setup.py prints follows.
#
# --dry-run prints each decision it would take and changes nothing.
#
# Written for the bash 3.2 a Mac ships with. It never runs the `python3` on
# PATH: that one may be years old.
set -u

DRY_RUN=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then DRY_RUN=1; else ARGS+=("$arg"); fi
done

HERE="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s)"
UV_INSTALL='curl -LsSf https://astral.sh/uv/install.sh | sh'
AGAIN='then paste the same message again'

say() { printf 'bootstrap: %s\n' "$*" >&2; }
needs_you() { printf 'BOOTSTRAP=NEEDS_YOU reason=%s\n' "$*"; exit 3; }

# -- 1. Git -------------------------------------------------------------------
# On a Mac without Apple's command line tools, /usr/bin/git is a stand-in that
# opens a window when run. Ask whether the tools exist before touching it.
git_path="$(command -v git 2>/dev/null || true)"
if [ "$OS" = "Darwin" ] && { [ -z "$git_path" ] || [ "$git_path" = "/usr/bin/git" ]; } \
    && ! xcode-select -p >/dev/null 2>&1; then
  needs_you "Apple's command line tools, which include Git, are missing. Run this one command, accept the window that opens, $AGAIN: xcode-select --install"
fi
if git --version >/dev/null 2>&1; then
  say "Git is already here: $(git --version 2>/dev/null)"
elif [ "$OS" = "Darwin" ]; then
  needs_you "Git did not run. Run this one command, accept the window that opens, $AGAIN: xcode-select --install"
else
  needs_you "Git is missing. Install it with your system's package manager (for example: sudo apt install git), $AGAIN."
fi

# -- 2. uv --------------------------------------------------------------------
find_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi
  for dir in "${XDG_BIN_HOME:-}" "$HOME/.local/bin"; do
    if [ -n "$dir" ] && [ -x "$dir/uv" ]; then
      printf '%s\n' "$dir/uv"
      return 0
    fi
  done
  return 1
}

UV="$(find_uv || true)"
if [ -n "$UV" ]; then
  say "uv is already here: $UV"
elif [ "$DRY_RUN" = 1 ]; then
  say "would run: $UV_INSTALL"
  UV="$HOME/.local/bin/uv"
else
  say "Installing uv, a small tool that fetches the right Python for your team without touching the one your computer came with."
  command -v curl >/dev/null 2>&1 \
    || needs_you "curl is missing, so uv cannot be downloaded. Install curl, $AGAIN."
  say "running: $UV_INSTALL"
  curl -LsSf https://astral.sh/uv/install.sh | sh >&2
  # The installer's own word is not proof. Look for uv again, by full path:
  # this shell's PATH has not caught up with what was just installed.
  UV="$(find_uv || true)"
  [ -n "$UV" ] \
    || needs_you "uv could not be installed from https://astral.sh/uv/install.sh. Check the internet connection, $AGAIN."
fi

# -- 3. Python ----------------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  say "would run: $UV python install 3.12"
  say "would run: $UV python find 3.12"
  say "would prove that Python by running it"
  if [ "${#ARGS[@]}" -gt 0 ]; then
    say "would run: nc_setup.py ${ARGS[*]}"
  fi
  printf 'BOOTSTRAP=OK python=dry-run\n'
  exit 0
fi

say "Installing Python so your team's memory and safety checks can run."
say "running: $UV python install 3.12"
"$UV" python install 3.12 >&2 \
  || needs_you "uv could not install Python 3.12. Check the internet connection, $AGAIN."
PY="$(UV_PYTHON_PREFERENCE=only-managed "$UV" python find 3.12 2>/dev/null || true)"
{ [ -n "$PY" ] && [ -x "$PY" ]; } \
  || needs_you "Python 3.12 was installed, but uv could not say where it is. Paste the same message again."

# -- 4. Prove it ----------------------------------------------------------------
prove() { "$PY" -c 'import sys, tomllib, sqlite3, venv; print(sys.version)' </dev/null 2>&1; }

version="$(prove)"
status=$?
if [ "$status" -gt 128 ] && [ "$OS" = "Darwin" ]; then
  # macOS can kill a freshly downloaded interpreter on launch until it carries
  # a signature made on this Mac.
  say "macOS stopped the new Python from starting; signing it on this Mac and trying once more"
  codesign --force -s - "$PY" >&2 2>&1 || true
  version="$(prove)"
  status=$?
fi
[ "$status" -eq 0 ] \
  || needs_you "The new Python at $PY did not run (exit $status). Paste the same message again; if it fails the same way, this computer is blocking it."
say "Python is ready: $(printf '%s\n' "$version" | head -n 1)"

printf 'BOOTSTRAP=OK python=%s\n' "$PY"
if [ "${#ARGS[@]}" -gt 0 ]; then
  exec "$PY" "$HERE/nc_setup.py" "${ARGS[@]}"
fi
