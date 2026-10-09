#!/usr/bin/env python3
"""cli_freshness.py -- a fortnightly check that the tools Technical Cofounder
relies on are not out of date. hooks/cli-freshness.sh runs it at SessionStart.

Source: Nova Caelum (2026). License: Apache-2.0.

When something is out of date it prints ONE line, which lands in the session's
context. The line carries its own instructions: the agent tells the user in
plain words what is out of date and the one command that updates it, and runs
that command only after the user says yes. Nothing is ever updated here.

When it runs, and what it costs
  - At most once every 14 days. The stamp is ${CLAUDE_PLUGIN_DATA}/cli-freshness.json
    (the plugin's per-user data folder; ~/.claude/technical-cofounder/ when
    Claude Code does not set it). It holds two epoch-second times: "checked"
    (the last time version lookups got an answer) and "attempted" (the last time
    this ran at all). A check is due when "checked" is 14 days old and
    "attempted" is a day old. Offline therefore costs nothing: the lookups fail,
    only "attempted" moves, and the next try is a day later, not a fortnight.
  - "attempted" is written BEFORE the lookups, so a second window opening at the
    same moment does not repeat them, and a run that is killed is not retried
    at every session. If the stamp cannot be written, nothing is checked.
  - Every program started here has 2 seconds and the whole check has 3.5, all
    tools in parallel. A tool that has not answered by then is simply not
    reported. Typical cost is a few hundred milliseconds.
  - Version lookups use the system `curl`, so they trust the same certificates
    the rest of the computer does. They never follow a download; they read a
    redirect header (GitHub) or a 6-byte text file (Claude Code).

What is reported
  A tool is out of date when a newer minor or major version exists: patch-only
  gaps are not worth interrupting anyone for. Claude Code ships only patch
  numbers, so it is out of date when it is 7 or more builds behind the stable
  channel. Each tool is reported only when
  there is one safe command to update it:
    - Claude Code, only when it will NOT update itself: DISABLE_AUTOUPDATER is
      set, or it came from Homebrew/WinGet without
      CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE. DISABLE_UPDATES means silence.
    - uv, jq, GitHub's command line (gh), and Git for Windows.
  Never reported: a tool the operating system owns (Apple's Git, /usr/bin/jq;
  they update with the OS, and starting Apple's Git shim without the Command
  Line Tools opens an installer window), Homebrew (it updates itself on every
  brew command), and Python (uv fetched it; keeping uv current is the lever).
  jq that setup downloaded into the per-user tools folder has no one-line update
  command, so it is not reported.

Everything printed is built from integers and fixed text: a version read from
the network or from a program is parsed to numbers and printed back as numbers,
never echoed.

Written for Python 3.8 and newer, standard library only. Fails open: any error
becomes one line on stderr and exit 0.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

CHECK_EVERY = 14 * 24 * 3600   # seconds between checks that got an answer
RETRY_AFTER = 24 * 3600        # seconds between tries when nothing answered
STATE_FILE = "cli-freshness.json"
PROGRAM_SECONDS = 2            # for each program started here
DEADLINE_SECONDS = 3.5         # for the whole check
GITHUB_LATEST = "https://github.com/{repo}/releases/latest"
CLAUDE_STABLE = "https://downloads.claude.ai/claude-code-releases/stable"
OS_OWNED = ("/usr/bin/", "/bin/", "/usr/sbin/", "/sbin/", "/System/", "/Library/Developer/CommandLineTools/")


@dataclass(frozen=True)
class Tool:
    key: str                # the program's name
    label: str              # what the agent calls it to the user
    repo: str = None        # GitHub repo whose latest release is the current version; None: Claude Code
    brew: str = None        # Homebrew formula
    winget: str = None      # WinGet package id
    own: str = None         # the tool's own update command
    patch_gap: int = None   # builds behind that count as out of date within one minor version
    applies: object = None  # test of `--version` output: is this the flavour we compare?
    note: str = None        # one clause the agent must pass on with the command


TOOLS = (
    Tool("claude", "Claude Code", brew="claude-code", winget="Anthropic.ClaudeCode", own="claude update",
         patch_gap=7, note="restart Claude Code afterwards"),
    Tool("uv", "uv", "astral-sh/uv", brew="uv", winget="astral-sh.uv", own="uv self update"),
    Tool("jq", "jq", "jqlang/jq", brew="jq", winget="jqlang.jq"),
    Tool("gh", "GitHub's command line (gh)", "cli/cli", brew="gh", winget="GitHub.cli"),
    Tool("git", "Git for Windows", "git-for-windows/git", winget="Git.Git", applies=lambda out: ".windows." in out,
         note="the user runs this one themselves, in PowerShell with Claude Code closed"),
)

# kind: "skip" (nothing to say), "noanswer" (a lookup was needed and failed), "current", "outdated"
Result = namedtuple("Result", "kind tool installed latest command", defaults=(None, None, None, None, None))
SKIP = Result("skip")
NOANSWER = Result("noanswer")


# -- versions -------------------------------------------------------------------

def triple(found):
    """(major, minor, patch) from a match of three groups, the last optional; None for no match."""
    return (int(found.group(1)), int(found.group(2)), int(found.group(3) or 0)) if found else None


def installed_version(text):
    """The first number like 1.7.1 in a program's first line of output, or None."""
    first = (text or "").strip().splitlines()[:1]
    return triple(re.search(r"(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?", first[0]) if first else None)


def tag_version(location):
    """The version in a GitHub redirect `.../releases/tag/<tag>`: the tag is
    v1.2.3, jq-1.8.2 or v2.56.0.windows.2, and anything else is None."""
    found = re.search(r"/releases/tag/([^/\s?#]+)\s*$", location or "")
    return triple(re.fullmatch(r"(?:jq-|v)?(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?(?:\.windows\.\d{1,3})?", found.group(1)) if found else None)


def behind(have, latest, patch_gap=None):
    """True when `latest` has a newer minor or major, or (Claude Code) is
    `patch_gap` builds ahead inside the same minor version."""
    if latest[:2] > have[:2]:
        return True
    return bool(patch_gap) and latest[:2] == have[:2] and latest[2] - have[2] >= patch_gap


def dotted(version):
    return ".".join(str(part) for part in version)


# -- the outside world -------------------------------------------------------------

class Host:
    """Everything the check touches outside this process. Tests pass a stand-in."""

    def __init__(self, github=GITHUB_LATEST, claude=CLAUDE_STABLE):
        self.environ = os.environ
        self.home = Path.home()
        self.system = {"darwin": "macos", "win32": "windows", "cygwin": "windows"}.get(sys.platform, "linux")
        self.github = github
        self.claude = claude
        self.now = time.time

    @property
    def tools_dir(self):
        """Where setup puts what it downloads: the folder lib/resolve-tools.sh looks in."""
        return Path(self.environ.get("NC_TOOLS_DIR") or self.home / ".local" / "bin")

    def find(self, name):
        """Path of the program: the one on PATH (for jq, the one the hooks'
        resolver chose), then the per-user folders installers write to, because
        a session that started before an install does not have them on PATH."""
        on_path = shutil.which((self.environ.get("NC_JQ") if name == "jq" else "") or name)
        suffix = ".exe" if self.system == "windows" else ""
        for candidate in (on_path, self.tools_dir / (name + suffix), self.home / ".local" / "bin" / (name + suffix)):
            if candidate and os.path.isfile(str(candidate)):
                return str(candidate)
        return None

    def realpath(self, path):
        """The real location, with forward slashes: Homebrew and WinGet link their
        programs from a folder of their own, and the real path says which."""
        return os.path.realpath(path).replace("\\", "/")

    def run(self, argv):
        """Standard output of the program, or None when it will not start,
        fails or takes more than PROGRAM_SECONDS."""
        try:
            done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=PROGRAM_SECONDS + 1)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None

    def curl(self, *args):
        return self.run(["curl", "-sS", "--connect-timeout", "1", "-m", str(PROGRAM_SECONDS), *args])

    def latest(self, tool):
        """The current version as a tuple, or None when nothing sensible came back."""
        if tool.repo:
            headers = self.curl("-I", self.github.format(repo=tool.repo)) or ""
            location = next((line.split(":", 1)[1].strip() for line in headers.splitlines() if line.lower().startswith("location:")), "")
            return tag_version(location)
        return triple(re.fullmatch(r"(\d{1,4})\.(\d{1,4})\.(\d{1,4})", (self.curl("-f", self.claude) or "").strip()))


# -- where a tool came from, and how to update it ------------------------------------

def truthy(environ, key):
    return environ.get(key, "").strip().lower() not in ("", "0", "false", "no", "off")


def folder_key(folder):
    return os.path.normcase(os.path.abspath(str(folder)))


def classify(path, host):
    """How the program got here: "os", "brew", "home" (the per-user tools
    folder), "winget" or "other"."""
    real = host.realpath(path)
    lower = real.lower()
    if host.system != "windows" and real.startswith(OS_OWNED):
        return "os"
    if "/cellar/" in lower or "/caskroom/" in lower:
        return "brew"
    if folder_key(os.path.dirname(path)) in {folder_key(host.tools_dir), folder_key(host.home / ".local" / "bin")}:
        return "home"
    return "winget" if "/winget/" in lower else "other"


def update_command(tool, kind, path, host):
    """The one command that updates this copy, or None when there is no safe one."""
    if kind == "brew" and tool.brew:
        cask = "claude-code@latest" if tool.key == "claude" and "claude-code@latest" in path.lower() else tool.brew
        return "brew upgrade " + cask
    if kind == "winget" and tool.winget:
        return "winget upgrade --id " + tool.winget
    if tool.own and kind in ("home", "other"):
        return tool.own
    if kind == "other" and host.system == "windows" and tool.winget:
        return "winget upgrade --id " + tool.winget
    return None


def updates_itself(kind, environ):
    """Claude Code: False when it will not keep itself current, so it is worth reporting."""
    if truthy(environ, "DISABLE_UPDATES"):
        return True    # nothing can update it; there is nothing to offer
    if truthy(environ, "DISABLE_AUTOUPDATER"):
        return False
    if kind in ("brew", "winget"):
        return truthy(environ, "CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE")
    return True


# -- one tool -----------------------------------------------------------------------------

def check_tool(tool, host):
    path = host.find(tool.key)
    if path is None:
        return SKIP
    kind = classify(path, host)
    if kind == "os" or (tool.key == "claude" and updates_itself(kind, host.environ)):
        return SKIP
    command = update_command(tool, kind, host.realpath(path), host)
    if command is None:
        return SKIP
    output = host.run([path, "--version"])
    have = installed_version(output)
    if have is None or (tool.applies and not tool.applies(output)):
        return SKIP
    latest = host.latest(tool)
    if latest is None:
        return NOANSWER
    kind = "outdated" if behind(have, latest, tool.patch_gap) else "current"
    return Result(kind, tool, have, latest, command)


def check_all(host):
    """Every tool, in parallel, within DEADLINE_SECONDS; a slow tool is NOANSWER."""
    pool = ThreadPoolExecutor(max_workers=len(TOOLS))
    futures = [(tool, pool.submit(check_tool, tool, host)) for tool in TOOLS]
    done, _ = wait([future for _, future in futures], timeout=DEADLINE_SECONDS)
    pool.shutdown(wait=False)
    results = []
    for tool, future in futures:
        if future not in done:
            results.append(NOANSWER)
            continue
        try:
            results.append(future.result())
        except Exception as exc:   # one tool's bug must not hide the others
            print("cli-freshness: %s check failed (%s)" % (tool.key, type(exc).__name__), file=sys.stderr)
            results.append(SKIP)
    return results


def render(outdated):
    parts = []
    for r in outdated:
        extra = ", " + r.tool.note if r.tool.note else ""
        parts.append("%s %s (current %s; update with `%s`%s)" % (r.tool.label, dotted(r.installed), dotted(r.latest), r.command, extra))
    return ("technical-cofounder two-week tool check: some tools on this computer are out of date: " + "; ".join(parts)
            + ". In your first reply, tell the user in plain words which tools are out of date and the one command that updates each,"
            " and ask whether they want you to run it. Run an update only after they say yes. Do not bring this up again unless they ask.")


# -- the stamp --------------------------------------------------------------------------------

def state_folder(host):
    data = host.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    return Path(data) if data else host.home / ".claude" / "technical-cofounder"


def read_stamp(folder):
    try:
        data = json.loads((folder / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_stamp(folder, checked, attempted):
    folder.mkdir(parents=True, exist_ok=True)
    scratch = folder / ("%s.%d.tmp" % (STATE_FILE, os.getpid()))
    scratch.write_text(json.dumps({"checked": checked, "attempted": attempted}), encoding="utf-8")
    os.replace(str(scratch), str(folder / STATE_FILE))


def stamp_time(value, now):
    """A stamp time as an int, or None when it is not one or lies in the future
    (a clock that was once wrong must not silence the check for years)."""
    ok = isinstance(value, int) and not isinstance(value, bool) and 0 < value <= now + 86400
    return value if ok else None


def due(stamp, now):
    checked, attempted = stamp_time(stamp.get("checked"), now), stamp_time(stamp.get("attempted"), now)
    return not ((checked is not None and now - checked < CHECK_EVERY) or (attempted is not None and now - attempted < RETRY_AFTER))


# -- entry point ------------------------------------------------------------------------------------

def main(host=None, out=None):
    host, out = host or Host(), out or sys.stdout
    now = int(host.now())
    folder = state_folder(host)
    stamp = read_stamp(folder)
    if not due(stamp, now):
        return 0
    try:
        write_stamp(folder, stamp_time(stamp.get("checked"), now), now)
    except OSError as exc:
        print("cli-freshness: no place to keep its stamp (%s), so it is not checking" % type(exc).__name__, file=sys.stderr)
        return 0
    results = check_all(host)
    answered = any(r.kind in ("current", "outdated") for r in results)
    if answered or not any(r.kind == "noanswer" for r in results):
        try:
            write_stamp(folder, now, now)
        except OSError:
            pass
    outdated = [r for r in results if r.kind == "outdated"]
    if outdated:
        print(render(outdated), file=out)
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("cli-freshness: skipped (%s)" % type(exc).__name__, file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)   # a lookup thread may still be waiting on a slow network
