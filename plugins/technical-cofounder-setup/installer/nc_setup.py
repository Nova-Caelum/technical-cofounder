#!/usr/bin/env python3
"""Technical Cofounder setup: look at this computer, say what is missing,
install only that, and look again.

    nc_setup.py scan  --project <absolute path> [--record]
    nc_setup.py plan  --project <absolute path>
    nc_setup.py apply --project <absolute path> --item <id>
    nc_setup.py apply --project <absolute path> --all
    nc_setup.py ack   --project <absolute path> --item <id>
    nc_setup.py judge --project <absolute path> --set claude-code|none

Every verb prints one JSON document on stdout and nothing else there;
progress lines go to stderr. Exit 0: the command did what it was asked.
Exit 1: an item failed. Exit 2: bad usage.

scan   looks and changes nothing. With --record it also writes
       <project>/core_text/setup-scan.json (only when the folder exists).
plan   is the scan plus, for every item, one verdict out of six, a one-line
       detail, and the "why" and "how long" from setup/steps.json.
apply  acts on an item only when its verdict is install, upgrade or repair,
       then checks the item again. The second check decides the result; a
       command that exits 0 is never taken as proof.
ack    records a yes to a question that only needed one.
judge  sets the judge Hyperspace Engine's verifier uses in this project:
       claude-code only when Claude Code's command line is signed in and
       answers, none always. It changes .hyperspace/config.toml and nothing
       else, and works before the engine's workspace is built or after.

Standard library only. Python 3.11 or newer.
"""
import argparse
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

READY, INSTALL, UPGRADE, REPAIR = "ready", "install", "upgrade", "repair"
NEEDS_YOU, NEEDS_RESTART = "needs-you", "needs-restart"
VERDICTS = (READY, INSTALL, UPGRADE, REPAIR, NEEDS_YOU, NEEDS_RESTART)
ACTIONABLE = (INSTALL, UPGRADE, REPAIR)

# Installing or repairing one of these means Claude Code has to be closed and
# opened again before the change is visible to it.
RESTART_ITEMS = frozenset({"claude-cli", "git", "team-plugin", "engine-env"})
# Questions a plain yes can clear.
ACKABLE = frozenset({"existing-config"})

MIN_PYTHON = (3, 11)
NEEDED_MODULES = ("tomllib", "sqlite3", "venv")
NETWORK_URL = "https://github.com"
NETWORK_SECONDS = 5
EXISTING_CONFIG_QUESTION = (
    "This folder already has instructions for Claude. Setup will keep them "
    "and add nothing over them. OK to continue?"
)

# Two ways a Git for Windows can be installed and still not be on this
# session's PATH; unseen_git() tells them apart.
DIRECT, STALE = "direct", "stale"
GIT_RESTART = (
    "Git is installed, but this session started before it was; close Claude Code "
    "completely, open it again, and paste the same message; if you started Claude "
    "Code from a terminal window, close that window too"
)
REGISTRY_MACHINE_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
REGISTRY_USER_ENV = "Environment"

MARKETPLACE = "nova-caelum"
# The full address, so no machine decides for itself between HTTPS and SSH.
MARKETPLACE_SOURCE = "https://github.com/Nova-Caelum/plugins.git"   # NC_MARKETPLACE_SOURCE overrides it
TEAM_PLUGIN = "technical-cofounder@nova-caelum"
ENGINE_PLUGIN = "hyperspace-engine@nova-caelum"

CLAUDE_INSTALL = {
    "posix": ["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"],
    "windows": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "irm https://claude.ai/install.ps1 | iex"],
}
UV_INSTALL = {
    "posix": ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
    "windows": ["powershell", "-ExecutionPolicy", "ByPass", "-c",
                "irm https://astral.sh/uv/install.ps1 | iex"],
}
JQ_DOWNLOADS = "https://github.com/jqlang/jq/releases/latest/download/"
JQ_BUILDS = {
    ("macos", "arm64"): "jq-macos-arm64",
    ("macos", "amd64"): "jq-macos-amd64",
    ("linux", "amd64"): "jq-linux-amd64",
    ("linux", "arm64"): "jq-linux-arm64",
    ("windows", "amd64"): "jq-windows-amd64.exe",
    ("windows", "arm64"): "jq-windows-amd64.exe",   # Windows on Arm runs the 64-bit Intel build
}

# The verifier's judge. On Claude Code the default is Claude Code's own command
# line, on the user's plan, with a modest model so a plan that runs Opus by
# default does not spend Opus on every closure. `none` is always available.
JUDGE_MODEL = "sonnet"
JUDGE_CHOICES = ("claude-code", "none")
JUDGE_SECONDS = 30
JUDGE_REASONS = {
    "answered": "The judge is on: Claude Code's command line will check each finished task, using your Claude plan.",
    "kept": "This project already chose its judge, and setup keeps it.",
    "chosen": 'The judge is off, as you chose. Say "turn on the judge" any time to switch it on.',
    "not-signed-in": (
        "Claude Code's command line is not signed in, so the judge cannot use it: run `claude auth login` "
        'in your own terminal window, then say "turn on the judge".'
    ),
    "no-answer": (
        "Claude Code's command line did not answer a test question within %d seconds, so the judge cannot "
        'use it yet: if it is not signed in, run `claude auth login` in your own terminal window; then say '
        '"turn on the judge" to try again.' % JUDGE_SECONDS
    ),
    "no-cli": "Claude Code's command line is not installed yet, so the judge cannot use it.",
}

STEPS_FILE = Path(__file__).resolve().parent.parent / "setup" / "steps.json"
RECORD_PARTS = ("core_text", "setup-scan.json")

POSIX_SYSTEM_DIRS = (
    "/System", "/Library", "/Applications", "/usr", "/etc", "/bin", "/sbin",
    "/dev", "/proc", "/sys", "/boot",
)
WINDOWS_SYSTEM_DIRS = (
    r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)", r"C:\ProgramData",
)
WINDOWS_SYSTEM_VARS = ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")


class UsageError(Exception):
    """The command line asked for something this script does not do."""


# ---------------------------------------------------------------------------
# The outside world: one command runner, one network probe, one downloader.
# ---------------------------------------------------------------------------

class Result:
    """What a child process left behind. A negative code means a signal
    killed it; 124 a timeout; 126 and 127 that it could not be started."""

    def __init__(self, code, out="", err=""):
        self.code, self.out, self.err = code, out, err

    def __repr__(self):
        return "Result(%r, %r, %r)" % (self.code, self.out, self.err)


def run_command(argv, cwd=None, env=None, timeout=60):
    """The one place this script starts another program.

    CLAUDECODE is removed from the child's environment: a `claude` started
    from inside a Claude Code session can hang when it inherits it. Standard
    input is closed, so nothing a child runs can wait for a keypress.
    """
    child_env = dict(os.environ if env is None else env)
    child_env.pop("CLAUDECODE", None)
    try:
        done = subprocess.run(
            [str(a) for a in argv], cwd=None if cwd is None else str(cwd), env=child_env,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError:
        return Result(127, "", "%s: not found" % argv[0])
    except subprocess.TimeoutExpired:
        return Result(124, "", "no answer within %d seconds" % timeout)
    except OSError as exc:
        return Result(126, "", str(exc))
    return Result(done.returncode, done.stdout, done.stderr)


def http_reach(url, timeout):
    """(True, note) when `url` answers a HEAD request within `timeout` seconds,
    else (False, reason). The request runs on a helper thread so a slow name
    lookup cannot stretch the wait."""
    box = {}

    def ask():
        try:
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "nc-setup"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                box["answer"] = (True, "HTTP %s" % response.status)
        except urllib.error.HTTPError as exc:
            box["answer"] = (False, "it answered HTTP %s" % exc.code)
        except Exception as exc:  # any failure to connect is the same answer: not reachable
            box["answer"] = (False, str(getattr(exc, "reason", exc)) or type(exc).__name__)

    worker = threading.Thread(target=ask, daemon=True)
    worker.start()
    worker.join(timeout + 0.5)
    return box.get("answer", (False, "no answer within %d seconds" % timeout))


def download_file(url, dest):
    """Fetch `url` to `dest`, landing it whole or not at all."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "nc-setup"})
    with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out)
    os.replace(partial, dest)


def detect_system():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in ("win32", "cygwin", "msys"):
        return "windows"
    return "linux"


def detect_machine():
    machine = platform.machine().lower()
    return {"aarch64": "arm64", "x86_64": "amd64"}.get(machine, machine)


class Ctx:
    """Everything a check or a fix may touch. Tests replace the runner, the
    network probe, the downloader and the folders; real runs take the
    defaults."""

    def __init__(self, project, runner=run_command, which=None, reach=http_reach,
                 download=download_file, home=None, system=None, machine=None,
                 env=None, python=None, python_version=None,
                 importer=importlib.import_module, applications=None,
                 tools_dir=None, log=None):
        self.project = str(project)
        self.runner = runner
        self.reach = reach
        self.download = download
        self.env = dict(os.environ) if env is None else env
        self.home = Path(home) if home is not None else Path.home()
        self.system = system or detect_system()
        self.machine = machine or detect_machine()
        self.python = python or sys.executable
        self.python_version = tuple(python_version or sys.version_info[:3])
        self.importer = importer
        self.applications = Path(applications) if applications is not None else Path("/Applications")
        self.tools_dir = Path(tools_dir or self.env.get("NC_TOOLS_DIR") or self.home / ".local" / "bin")
        self.which = which or (lambda name: shutil.which(name, path=self.env.get("PATH")))
        self.log = log or (lambda line: print("nc-setup: " + line, file=sys.stderr, flush=True))
        self.probes = {}       # tool name -> (path, result), kept until something is installed
        self.unseen_git = None # (git.exe, DIRECT or STALE) on Windows, once it has been worked out
        self.changed = set()   # items installed or repaired by this run
        self.acks = set()      # questions answered yes by this run
        self.judge = None      # the judge the engine build chose, and why

    def run(self, argv, cwd=None, env=None, timeout=60):
        return self.runner(argv, cwd=cwd, env=self.env if env is None else env, timeout=timeout)

    @property
    def project_dir(self):
        return Path(self.project)

    @property
    def record_path(self):
        return self.project_dir.joinpath(*RECORD_PARTS)


# ---------------------------------------------------------------------------
# The record: <project>/core_text/setup-scan.json
# ---------------------------------------------------------------------------

def read_record(ctx):
    try:
        record = json.loads(ctx.record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def acknowledged(ctx):
    record = read_record(ctx) or {}
    known = record.get("acknowledged")
    return set(known if isinstance(known, list) else ()) | ctx.acks


def build_record(ctx, rows):
    verdicts = {row["id"]: row["verdict"] for row in rows}
    # A question stays answered once it was answered, or once a record saw
    # there was nothing to ask about: files setup lays down later are not the
    # user's earlier work.
    answered = acknowledged(ctx) | {i for i in ACKABLE if verdicts.get(i) == READY}
    return {
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": ctx.system,
        "restart_required": NEEDS_RESTART in verdicts.values() or bool(ctx.changed & RESTART_ITEMS),
        "tools": tool_paths(ctx),
        "items": [{"id": r["id"], "verdict": r["verdict"], "detail": r["detail"]} for r in rows],
        "acknowledged": sorted(answered),
    }


def save_record(ctx, record):
    """Write the record into the project, or return None when there is no
    usable project folder. A record that says what the file already says is
    not rewritten, so a run that changed nothing leaves every file alone.

    That makes `scanned_at` the time of the last change, and
    `restart_required` a statement about that moment: a restart was needed
    as of `scanned_at`. A later run that finds nothing new cannot know
    whether Claude Code was restarted since, so it leaves both as they are.
    A reader decides by comparing `scanned_at` with when its session began."""
    verdicts = {item["id"]: item["verdict"] for item in record["items"]}
    if verdicts.get("project-folder") != READY:
        return None
    path = ctx.record_path
    previous = read_record(ctx)
    if previous is not None:
        same = all(previous.get(key) == record[key] for key in ("platform", "tools", "items", "acknowledged"))
        if same and (previous.get("restart_required") or not record["restart_required"]):
            return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(partial, path)
    return str(path)


def tool_paths(ctx):
    """Where each tool really is, so later sessions need not trust PATH."""
    paths = {"python": ctx.python}
    for name in ("uv", "jq", "git", "claude"):
        paths[name] = working(ctx, name)
    return paths


# ---------------------------------------------------------------------------
# Checks. Each returns (verdict, one-line detail) and changes nothing.
# ---------------------------------------------------------------------------

def _flavour(ctx):
    return PureWindowsPath if ctx.system == "windows" else PurePosixPath


def _parts(ctx, path):
    parts = _flavour(ctx)(str(path)).parts
    if ctx.system in ("windows", "macos"):   # their disks ignore letter case
        return tuple(part.casefold() for part in parts)
    return parts


def _forms(ctx, path):
    """The path as given and, when this computer can follow it, with its
    links resolved (/etc is /private/etc on a Mac)."""
    forms = [_parts(ctx, path)]
    if Path(str(path)).is_absolute():
        forms.append(_parts(ctx, os.path.realpath(str(path))))
    return forms


def _within(inner, outer):
    return inner[:len(outer)] == outer


def _named(ctx, name):
    """What the environment holds under a Windows name. Windows ignores the
    letter case of a name, and Python hands a real Windows environment over
    with every name in capitals: PROGRAMFILES, never ProgramFiles."""
    return ctx.env.get(name) or ctx.env.get(name.upper())


def _system_dirs(ctx):
    if ctx.system == "windows":
        named = [_named(ctx, var) for var in WINDOWS_SYSTEM_VARS]
        return [d for d in list(WINDOWS_SYSTEM_DIRS) + named if d]
    return list(POSIX_SYSTEM_DIRS)


def refusal(ctx):
    """One plain sentence saying why this path cannot be a project folder,
    or None when it can."""
    given = ctx.project
    pure = _flavour(ctx)(given)
    hint = "pick a new folder inside your home folder instead"
    if not (pure.is_absolute() or Path(given).is_absolute()):
        return "Setup needs the full path to the project folder, starting from the top of the disk."
    if pure.parent == pure:
        return "The top of the disk is not a place for a project; %s." % hint
    project_forms = _forms(ctx, given)
    home_forms = _forms(ctx, ctx.home)
    if any(p == h for p in project_forms for h in home_forms):
        return "Setup will not turn your home folder into a project; pick a new folder inside it."
    if any(_within(h, p) for p in project_forms for h in home_forms):
        return "That folder contains your home folder; %s." % hint
    system_forms = [form for d in _system_dirs(ctx) for form in _forms(ctx, d)]
    if any(_within(p, s) for p in project_forms for s in system_forms):
        return "%s is a system folder; %s." % (given, hint)
    if ctx.system != "windows" and len(pure.parts) == 2:
        return "%s is a system folder at the top of the disk; %s." % (given, hint)
    return None


def check_project_folder(ctx):
    reason = refusal(ctx)
    if reason:
        return NEEDS_YOU, reason
    project = ctx.project_dir
    if project.is_dir():
        return READY, "the folder exists"
    if project.exists():
        return NEEDS_YOU, "%s is a file, not a folder; pick a folder for the project." % ctx.project
    return INSTALL, "the folder does not exist yet"


def check_existing_config(ctx):
    project = ctx.project_dir
    if not ((project / "CLAUDE.md").exists() or (project / ".claude" / "rules").is_dir()):
        return READY, "no earlier instructions for Claude here"
    if "existing-config" in acknowledged(ctx):
        return READY, "the instructions already here stay as they are"
    return NEEDS_YOU, EXISTING_CONFIG_QUESTION


def check_python(ctx):
    version = ".".join(str(part) for part in ctx.python_version[:3])
    if tuple(ctx.python_version[:2]) < MIN_PYTHON:
        return NEEDS_YOU, "this is Python %s and setup needs 3.11 or newer; run the first-step script again" % version
    for module in NEEDED_MODULES:
        try:
            ctx.importer(module)
        except Exception:
            return NEEDS_YOU, "this Python %s cannot load %s; run the first-step script again" % (version, module)
    return READY, "Python %s at %s" % (version, ctx.python)


def check_network(ctx):
    ok, note = ctx.reach(NETWORK_URL, NETWORK_SECONDS)
    if ok:
        return READY, "%s answered" % NETWORK_URL
    return NEEDS_YOU, (
        "could not reach %s within %d seconds (%s); check the connection or ask "
        "whoever runs this network, then run setup again" % (NETWORK_URL, NETWORK_SECONDS, note)
    )


def check_obsidian(ctx):
    if (ctx.project_dir / ".obsidian").is_dir():
        return READY, "this folder is already a vault"
    if ctx.system == "macos":
        places = [ctx.applications / "Obsidian.app", ctx.home / "Applications" / "Obsidian.app"]
    elif ctx.system == "windows":
        local = ctx.env.get("LOCALAPPDATA")
        places = [Path(local) / "Programs" / "Obsidian", Path(local) / "Obsidian"] if local else []
    else:
        places = [Path(found)] if (found := ctx.which("obsidian")) else []
    return READY, "installed" if any(place.exists() for place in places) else "not installed"


# -- tools ------------------------------------------------------------------

def exe(ctx, name):
    return name + ".exe" if ctx.system == "windows" else name


def copies(ctx, name):
    """Every copy of a tool worth trying: the one on PATH, then the per-user
    folders the installers write to. A fresh install is found there even
    though this session's PATH has not caught up."""
    if name == "git":
        git, how = unseen_git(ctx)
        if how == DIRECT:
            return [git]   # its folder is first on this run's PATH: it is the Git every child gets
    found = ctx.which(name)
    places = [str(found)] if found else []
    for folder in (ctx.tools_dir, ctx.home / ".local" / "bin"):
        candidate = folder / exe(ctx, name)
        if candidate.is_file() and str(candidate) not in places:
            places.append(str(candidate))
    return places


def probe(ctx, name):
    """(path, result) for the first copy of `name` that answers --version;
    when none does, the last copy tried; (None, None) when there is none."""
    if name not in ctx.probes:
        answer = (None, None)
        for path in copies(ctx, name):
            answer = (path, ctx.run([path, "--version"], timeout=30))
            if answer[1].code == 0:
                break
        ctx.probes[name] = answer
    return ctx.probes[name]


def working(ctx, name):
    path, result = probe(ctx, name)
    return path if result is not None and result.code == 0 else None


def first_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[0] if lines else ""


def last_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def killed_on_launch(ctx, result):
    """macOS kills a program it will not trust before it prints a thing."""
    return ctx.system == "macos" and result is not None and result.code < 0


def tool_verdict(ctx, name, label):
    path, result = probe(ctx, name)
    if path is None:
        return INSTALL, "%s is not installed" % label
    if result.code == 0:
        return READY, "%s at %s" % (first_line(result.out) or label, path)
    if result.code == 124:
        return NEEDS_YOU, "%s at %s did not answer within 30 seconds; run setup again" % (label, path)
    if killed_on_launch(ctx, result):
        return REPAIR, "macOS stopped %s at %s from starting; it has to be signed again" % (label, path)
    return REPAIR, "%s at %s does not run (exit %s)" % (label, path, result.code)


def check_claude(ctx):
    return tool_verdict(ctx, "claude", "Claude Code's command line")


def check_uv(ctx):
    return tool_verdict(ctx, "uv", "uv")


def check_jq(ctx):
    verdict, detail = tool_verdict(ctx, "jq", "jq")
    if verdict in (INSTALL, REPAIR) and (ctx.system, ctx.machine) not in JQ_BUILDS:
        return NEEDS_YOU, "there is no official jq download for %s %s; install jq yourself, then run setup again" % (
            ctx.system, ctx.machine)
    return verdict, detail


def _windows_stand_in(path):
    """Windows ships its own bash.exe that is not Git Bash."""
    folded = str(path).replace("/", "\\").casefold()
    return "\\windows\\system32\\" in folded or "\\windowsapps\\" in folded


def git_bash(ctx, git):
    """Git's own bash.exe: beside git.exe the way Git for Windows lays itself
    out (which is how Claude Code finds it), or on PATH and not Windows'
    stand-in. By default Git for Windows puts only Git\\cmd on PATH, so a
    `bash` that resolves to the stand-in says nothing about Git."""
    for folder in list(Path(git).parents)[:3]:
        if (folder / "bin" / "bash.exe").is_file():
            return str(folder / "bin" / "bash.exe")
    bash = ctx.which("bash")
    return str(bash) if bash and not _windows_stand_in(bash) else None


def _git_installs(ctx):
    roots = [_named(ctx, var) for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")]
    local = ctx.env.get("LOCALAPPDATA")
    roots.append(str(Path(local) / "Programs") if local else None)
    return [Path(root) / "Git" / "cmd" / "git.exe" for root in roots if root]


def registry_path():
    """The machine's saved PATH and then the user's, as Windows keeps them in
    the registry, joined into one. Empty where there is no registry."""
    try:
        import winreg
    except ImportError:
        return ""
    found = []
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, REGISTRY_MACHINE_ENV), (winreg.HKEY_CURRENT_USER, REGISTRY_USER_ENV)):
        try:
            with winreg.OpenKey(hive, key) as handle:
                text, kind = winreg.QueryValueEx(handle, "Path")
            if kind == winreg.REG_EXPAND_SZ:   # %SystemRoot% and the like, which PowerShell fills in too
                text = winreg.ExpandEnvironmentStrings(text)
        except OSError:
            continue
        found.append(str(text))
    return ";".join(found)


def saved_path(ctx):
    """The PATH a newly started program gets, which a session that is already
    running does not see. NC_PERSISTED_PATH stands in for it, as it does in
    bootstrap.ps1, so the rule below can be tested on any system."""
    stand_in = ctx.env.get("NC_PERSISTED_PATH")
    if stand_in is not None:
        return stand_in
    return registry_path() if ctx.system == "windows" else ""


def _on_saved_path(ctx, folder):
    def plain(entry):   # Windows ignores letter case and a trailing backslash
        return str(entry).strip().replace("/", "\\").rstrip("\\").casefold()
    return plain(folder) in {plain(entry) for entry in saved_path(ctx).split(";")}


def _find_unseen_git(ctx):
    if ctx.system != "windows":
        return None, None
    on_path = ctx.which("git")
    if on_path and git_bash(ctx, on_path):
        return None, None
    installed = next((copy for copy in _git_installs(ctx) if copy.is_file()), None)
    if installed is None or not git_bash(ctx, installed):
        return None, None
    return str(installed), (STALE if _on_saved_path(ctx, installed.parent) else DIRECT)


def unseen_git(ctx):
    """A full Git for Windows (its own Git Bash beside it) that this session's
    PATH does not lead to, ruled the way bootstrap.ps1 rules it. Returns
    (its git.exe, which of the two it is):

    DIRECT  its folder is not on the saved PATH either. It was installed to
            stay off PATH, so no restart would ever show it: it is used where
            it is, and its folder goes first on the PATH this run hands to
            every program it starts, so a `claude plugin` command can clone.
    STALE   its folder is on the saved PATH. This session started before Git
            was installed, and only a restart shows it.

    (None, None) when PATH already leads to a Git with its Git Bash, or no
    such install exists. Worked out once per run."""
    if ctx.unseen_git is None:
        ctx.unseen_git = _find_unseen_git(ctx)
        git, how = ctx.unseen_git
        if how == DIRECT:
            folder = os.path.dirname(git)
            rest = [entry for entry in ctx.env.get("PATH", "").split(os.pathsep) if entry and entry != folder]
            ctx.env["PATH"] = os.pathsep.join([folder] + rest)
    return ctx.unseen_git


def check_git_windows(ctx):
    git, how = unseen_git(ctx)
    if how == STALE:
        return NEEDS_RESTART, GIT_RESTART
    path, result = probe(ctx, "git")
    if result is not None and result.code == 0:
        if how == DIRECT:
            return READY, "%s at %s (not on PATH; used directly)" % (first_line(result.out) or "Git", path)
        if git_bash(ctx, path):
            return READY, "%s at %s" % (first_line(result.out) or "Git", path)
        return NEEDS_YOU, (
            "the Git at %s has no Git Bash with it; run the first-step script, bootstrap.ps1, "
            "which installs Git for Windows" % path
        )
    if result is not None and result.code == 124:
        return NEEDS_YOU, "Git at %s did not answer within 30 seconds; run setup again" % path
    if how == DIRECT:
        return NEEDS_YOU, (
            "the Git at %s does not run (exit %s); install Git for Windows again from "
            "https://git-scm.com/downloads/win, then run setup again" % (path, result.code)
        )
    if any(copy.is_file() for copy in _git_installs(ctx)):
        return NEEDS_RESTART, GIT_RESTART
    return NEEDS_YOU, "Git for Windows is missing; run the first-step script, bootstrap.ps1, which installs it"


def check_git(ctx):
    if ctx.system == "windows":
        return check_git_windows(ctx)
    if ctx.system == "macos" and ctx.which("git") in (None, "/usr/bin/git"):
        # /usr/bin/git is Apple's stand-in: without the command line tools,
        # running it opens a window. Ask whether the tools exist instead.
        if ctx.run(["xcode-select", "-p"], timeout=30).code != 0:
            return NEEDS_YOU, (
                "Apple's command line tools, which include Git, are missing; run this one command, "
                "accept the window that opens, then run setup again: xcode-select --install"
            )
    path, result = probe(ctx, "git")
    if result is not None and result.code == 0:
        return READY, "%s at %s" % (first_line(result.out) or "Git", path)
    if result is not None and result.code == 124:
        return NEEDS_YOU, "Git at %s did not answer within 30 seconds; run setup again" % path
    if ctx.system == "macos":
        return NEEDS_YOU, "Git did not run; run this one command, then run setup again: xcode-select --install"
    return NEEDS_YOU, (
        "Git is missing; install it with your system's package manager "
        "(for example: sudo apt install git), then run setup again"
    )


# -- the catalog, the team, the engine's workspace ---------------------------

def claude_json(ctx, args, cwd=None):
    """(list, None) from a `claude ... --json` call, or (None, the reason it
    could not be read)."""
    shown = "claude " + " ".join(args)
    result = ctx.run([working(ctx, "claude")] + args, cwd=cwd, timeout=120)
    if result.code != 0:
        return None, "`%s` exited %s: %s" % (shown, result.code, last_line(result.err or result.out))
    try:
        data = json.loads(result.out)
    except ValueError:
        data = None
    if not isinstance(data, list):
        return None, "`%s` gave an answer setup could not read; update Claude Code and run setup again" % shown
    return [entry for entry in data if isinstance(entry, dict)], None


def check_marketplace(ctx):
    if not working(ctx, "claude"):
        return INSTALL, "waits for Claude Code's command line"
    listed, problem = claude_json(ctx, ["plugin", "marketplace", "list", "--json"])
    if problem:
        return NEEDS_YOU, problem
    if any(entry.get("name") == MARKETPLACE for entry in listed):
        return READY, "the %s catalog is added" % MARKETPLACE
    return INSTALL, "the %s catalog is not added yet" % MARKETPLACE


def _same_folder(a, b):
    def norm(path):
        return os.path.normcase(os.path.realpath(str(path)))
    return bool(a) and norm(a) == norm(b)


def plugin_state(ctx, entries, plugin_id):
    """"ok", "broken" or "absent", as seen from the project folder. The list
    also shows installs that belong to other projects; those are not ours."""
    mine = [entry for entry in entries if entry.get("id") == plugin_id]
    if any(entry.get("enabled") and not entry.get("errors") for entry in mine):
        return "ok"
    here = [
        entry for entry in mine
        if entry.get("enabled") or entry.get("scope") != "project"
        or _same_folder(entry.get("projectPath"), ctx.project)
    ]
    return "broken" if here else "absent"


def plugin_entries(ctx):
    return claude_json(ctx, ["plugin", "list", "--json"], cwd=ctx.project)


def check_team_plugin(ctx):
    if not working(ctx, "claude"):
        return INSTALL, "waits for Claude Code's command line"
    if not ctx.project_dir.is_dir():
        return INSTALL, "waits for the project folder"
    entries, problem = plugin_entries(ctx)
    if problem:
        return NEEDS_YOU, problem
    team = plugin_state(ctx, entries, TEAM_PLUGIN)
    engine = plugin_state(ctx, entries, ENGINE_PLUGIN)
    if team == engine == "ok":
        return READY, "your team and Hyperspace Engine are installed and switched on here"
    if team == engine == "absent":
        return INSTALL, "your team is not installed in this project yet"
    faulty = " and ".join(
        label for label, state in (("your team", team), ("Hyperspace Engine", engine)) if state != "ok"
    )
    return REPAIR, "%s is missing, switched off or did not load" % faulty


def engine_env(ctx):
    """(the folder, the interpreter inside it, the path the engine's server
    starts). The last two differ only on Windows, where the engine links
    env\\bin to env\\Scripts."""
    env = ctx.project_dir / ".hyperspace" / "env"
    if ctx.system == "windows":
        return env, env / "Scripts" / "python.exe", env / "bin" / "python.exe"
    return env, env / "bin" / "python", env / "bin" / "python"


def engine_loads(ctx, python):
    return ctx.run([str(python), "-c", "import hyperspace"], timeout=60)


def check_engine_env(ctx):
    env, python, served = engine_env(ctx)
    if not env.exists():
        return INSTALL, ("the workspace is not built yet" if ctx.project_dir.is_dir() else "waits for the project folder")
    if not python.is_file():
        return REPAIR, "the workspace folder is there but has no Python in it"
    result = engine_loads(ctx, python)
    if result.code == 124:
        return NEEDS_YOU, "the workspace's Python did not answer within 60 seconds; run setup again"
    if killed_on_launch(ctx, result):
        return REPAIR, "macOS stopped the workspace's Python from starting; it has to be signed again"
    if result.code != 0:
        return REPAIR, "the workspace is there but Hyperspace Engine does not load in it"
    if not served.is_file():
        return REPAIR, "the workspace works but %s is missing, so the engine's server cannot start" % served
    return READY, "Hyperspace Engine loads in %s" % env


# ---------------------------------------------------------------------------
# Fixes. Each acts once and returns None, or a note about what went wrong.
# The note is only ever extra detail: the check that runs afterwards, not the
# fix and not a command's exit code, decides whether the item is ready.
# ---------------------------------------------------------------------------

def run_install(ctx, argv, **options):
    options.setdefault("timeout", 900)
    result = ctx.run(argv, **options)
    if result.code == 0:
        return None
    shown = " ".join(str(part) for part in argv)
    return "`%s` exited %s: %s" % (shown, result.code, last_line(result.err or result.out) or "no message")


def sign_again(ctx, path):
    """macOS can kill a freshly downloaded program on launch until it carries
    a signature made on this Mac."""
    return run_install(ctx, ["codesign", "--force", "-s", "-", os.path.realpath(str(path))], timeout=60)


def _family(ctx):
    return "windows" if ctx.system == "windows" else "posix"


def fix_claude(ctx, verdict):
    return run_install(ctx, CLAUDE_INSTALL[_family(ctx)])


def fix_uv(ctx, verdict):
    return run_install(ctx, UV_INSTALL[_family(ctx)])


def fix_jq(ctx, verdict):
    path, result = probe(ctx, "jq")
    if verdict == REPAIR and killed_on_launch(ctx, result):
        return sign_again(ctx, path)
    url = JQ_DOWNLOADS + JQ_BUILDS[(ctx.system, ctx.machine)]
    target = ctx.tools_dir / exe(ctx, "jq")
    try:
        ctx.download(url, target)
        if ctx.system != "windows":
            os.chmod(target, 0o755)
    except Exception as exc:   # a failed download is a failed item, never a crash
        return "could not download %s: %s" % (url, exc)
    if killed_on_launch(ctx, ctx.run([str(target), "--version"], timeout=30)):
        return sign_again(ctx, target)
    return None


def fix_project_folder(ctx, verdict):
    try:
        ctx.project_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return "could not create the folder: %s" % exc
    return None


def fix_marketplace(ctx, verdict):
    claude = working(ctx, "claude")
    if not claude:
        return "Claude Code's command line is not installed yet; install it first"
    source = ctx.env.get("NC_MARKETPLACE_SOURCE") or MARKETPLACE_SOURCE
    return run_install(ctx, [claude, "plugin", "marketplace", "add", source])


def fix_team_plugin(ctx, verdict):
    """One install, run from the project folder. Hyperspace Engine is the
    team's dependency and arrives with it; the same command brings back an
    engine that went missing."""
    claude = working(ctx, "claude")
    if not claude:
        return "Claude Code's command line is not installed yet; install it first"
    return run_install(ctx, [claude, "plugin", "install", TEAM_PLUGIN, "--scope", "project"], cwd=ctx.project)


def engine_config(ctx):
    return ctx.project_dir / ".hyperspace" / "config.toml"


def chosen_judge(ctx):
    """The judge this project's engine config already names, or None."""
    try:
        import tomllib
        with open(engine_config(ctx), "rb") as handle:
            judge = tomllib.load(handle).get("judge")
    except Exception:   # no file yet, or one that cannot be read
        judge = None
    return judge if isinstance(judge, str) and judge else None


def signed_in(ctx, claude):
    """False only when `claude auth status` says plainly that the command line
    is signed out. True, or None when it cannot tell (an older CLI): the
    ping decides then. The desktop app's sign-in does not reach the command
    line, so a desktop-only user's command line is often signed out."""
    result = ctx.run([claude, "auth", "status"], timeout=JUDGE_SECONDS)
    try:
        state = json.loads(result.out)
    except ValueError:
        return None
    logged_in = state.get("loggedIn") if isinstance(state, dict) else None
    return logged_in if isinstance(logged_in, bool) else None


def host_judge(ctx):
    """(judge, why) for this harness: Claude Code's own command line when it
    is signed in and answers a one-word question on the judge's model, the
    same probe the engine uses; otherwise none and why."""
    claude = working(ctx, "claude")
    if not claude:
        return "none", "no-cli"
    if signed_in(ctx, claude) is False:
        return "none", "not-signed-in"
    ping = ctx.run([claude, "-p", "ping", "--output-format", "json", "--model", JUDGE_MODEL], timeout=JUDGE_SECONDS)
    return ("claude-code", "answered") if ping.code == 0 else ("none", "no-answer")


def engine_judge(ctx):
    """(judge, why): the judge this project already chose, so a rebuild does
    not reset it; otherwise this harness's default."""
    judge = chosen_judge(ctx)
    return (judge, "kept") if judge else host_judge(ctx)


def write_judge(ctx, judge):
    """Name the judge in the engine's config and keep every other line. The
    engine keeps a model it finds there, so claude-code gets the judge's
    model when no model is named yet."""
    path = engine_config(ctx)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    def key(line):
        return line.split("=", 1)[0].strip() if "=" in line else None

    entry = 'judge = "%s"' % judge
    lines = [entry if key(line) == "judge" else line for line in lines]
    if entry not in lines:
        lines.insert(0, entry)
    if judge == "claude-code" and not any(key(line) == "model" for line in lines):
        lines.insert(lines.index(entry) + 1, 'model = "%s"' % JUDGE_MODEL)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(partial, path)


def judge_report(judge, why):
    return {"judge": judge, "why": why, "detail": JUDGE_REASONS[why]}


def fix_engine_env(ctx, verdict):
    """Hand the build to the engine's own setup script, with this Python and
    with uv's folder first on the child's PATH."""
    env, python, _ = engine_env(ctx)
    if python.is_file() and killed_on_launch(ctx, engine_loads(ctx, python)):
        sign_again(ctx, python)
        if engine_loads(ctx, python).code == 0:
            return None
    if not working(ctx, "claude"):
        return "Claude Code's command line is not installed yet; install it first"
    entries, problem = plugin_entries(ctx)
    if problem:
        return problem
    engines = [e for e in entries if e.get("id") == ENGINE_PLUGIN and e.get("installPath")]
    engines.sort(key=lambda entry: not entry.get("enabled"))
    if not engines:
        return "Hyperspace Engine is not installed yet; install your team first"
    child_env = dict(ctx.env)
    uv = working(ctx, "uv")
    if uv:
        child_env["PATH"] = os.pathsep.join(filter(None, [os.path.dirname(uv), child_env.get("PATH")]))
    if env.exists():
        child_env["UV_VENV_CLEAR"] = "1"   # uv will not build over an existing environment unless told to replace it
    judge, why = engine_judge(ctx)
    if why != "kept":
        write_judge(ctx, judge)   # decided once: a build that fails is not asked again
    ctx.judge = judge_report(judge, why)
    setup = Path(engines[0]["installPath"]) / "bin" / "hyperspace_setup.py"
    return run_install(
        ctx,
        [ctx.python, str(setup), "--dir", ctx.project, "--provision", "--judge", judge],
        cwd=ctx.project, env=child_env, timeout=1800,
    )


# ---------------------------------------------------------------------------
# The items, in the order setup walks them. An item with no fix can only be
# ready or wait for the user.
# ---------------------------------------------------------------------------

class Item:
    def __init__(self, item_id, check, fix=None):
        self.id, self.check, self.fix = item_id, check, fix


ITEMS = [
    Item("claude-cli", check_claude, fix_claude),
    Item("git", check_git),
    Item("uv", check_uv, fix_uv),
    Item("python", check_python),
    Item("jq", check_jq, fix_jq),
    Item("network", check_network),
    Item("project-folder", check_project_folder, fix_project_folder),
    Item("existing-config", check_existing_config),
    Item("marketplace", check_marketplace, fix_marketplace),
    Item("team-plugin", check_team_plugin, fix_team_plugin),
    Item("engine-env", check_engine_env, fix_engine_env),
    Item("obsidian", check_obsidian),
]
ITEM_BY_ID = {item.id: item for item in ITEMS}


def load_reasons():
    """setup/steps.json: the one source of 'why' and 'how long'."""
    entries = json.loads(STEPS_FILE.read_text(encoding="utf-8"))["install"]
    return {entry["id"]: entry for entry in entries}


def check_item(ctx, item):
    """One row of the scan. A check that cannot tell is never `ready`: it
    waits for the user, with the reason."""
    try:
        verdict, detail = item.check(ctx)
    except Exception as exc:
        verdict, detail = NEEDS_YOU, "setup could not check this (%s: %s); run setup again" % (type(exc).__name__, exc)
    return {"id": item.id, "verdict": verdict, "detail": " ".join(str(detail).split())}


def scan_rows(ctx):
    return [check_item(ctx, item) for item in ITEMS]


# ---------------------------------------------------------------------------
# The verbs.
# ---------------------------------------------------------------------------

def do_scan(ctx, record):
    document = build_record(ctx, scan_rows(ctx))
    recorded = save_record(ctx, document) if record else None
    return 0, dict(document, command="scan", project=ctx.project, recorded=recorded)


def why(ctx, entry):
    return (entry.get("why_windows") if ctx.system == "windows" else None) or entry["why"]


def do_plan(ctx):
    reasons = load_reasons()
    rows = scan_rows(ctx)
    for row in rows:
        entry = reasons[row["id"]]
        row.update(title=entry["title"], why=why(ctx, entry), minutes=entry["minutes"])
    waiting = [row["id"] for row in rows if row["verdict"] != READY]
    return 0, {
        "command": "plan", "project": ctx.project, "platform": ctx.system,
        "items": rows, "next": waiting[0] if waiting else None,
    }


def apply_item(ctx, item, reasons):
    """Act on one item if its verdict asks for it, then check it again."""
    before = check_item(ctx, item)
    result = {"id": item.id, "before": before["verdict"], "after": before["verdict"],
              "detail": before["detail"], "acted": False}
    if before["verdict"] not in ACTIONABLE or item.fix is None:
        return result
    ctx.log(why(ctx, reasons[item.id]))
    try:
        note = item.fix(ctx, before["verdict"])
    except Exception as exc:
        note = "%s: %s" % (type(exc).__name__, exc)
    ctx.probes.clear()
    after = check_item(ctx, item)
    result.update(after=after["verdict"], detail=after["detail"], acted=True)
    if after["verdict"] == READY:
        ctx.changed.add(item.id)
    elif note:
        result["detail"] = "%s (%s)" % (after["detail"], " ".join(note.split()))
    ctx.log("%s: %s" % (item.id, result["after"] if result["after"] == READY else result["detail"]))
    return result


def do_apply(ctx, item_id):
    """`item_id` None walks every item in order and stops at the first one
    that is not ready afterwards: a failure, or something only the user or a
    restart can settle."""
    reasons = load_reasons()
    everything = item_id is None
    results, stopped_at = [], None
    for item in (ITEMS if everything else [ITEM_BY_ID[item_id]]):
        result = apply_item(ctx, item, reasons)
        results.append(result)
        if result["after"] != READY:
            stopped_at = item.id
            break
    acted = any(result["acted"] for result in results)
    restart = any(r["after"] == NEEDS_RESTART for r in results) or bool(ctx.changed & RESTART_ITEMS)
    recorded = None
    if everything or acted:
        if everything and stopped_at is None and not acted:
            rows = [{"id": r["id"], "verdict": r["after"], "detail": r["detail"]} for r in results]
        else:
            ctx.probes.clear()
            rows = scan_rows(ctx)   # the re-scan is the only source of "done"
        recorded = save_record(ctx, build_record(ctx, rows))
    failed = any(result["acted"] and result["after"] != READY for result in results)
    document = {
        "command": "apply", "project": ctx.project, "results": results,
        "stopped_at": stopped_at, "failed": failed,
        "restart_required": restart, "recorded": recorded,
    }
    if ctx.judge:
        document["judge"] = ctx.judge
    return (1 if failed else 0), document


def do_ack(ctx, item_id):
    if item_id not in ACKABLE:
        raise UsageError("%s is not a question setup can take a yes for" % item_id)
    ctx.acks.add(item_id)
    rows = scan_rows(ctx)
    recorded = save_record(ctx, build_record(ctx, rows))
    row = next(row for row in rows if row["id"] == item_id)
    return 0, {"command": "ack", "project": ctx.project, "item": row, "recorded": recorded}


def do_judge(ctx, choice):
    """Set the judge, or say why it cannot be set: claude-code only after the
    same checks a new project gets; nothing changes when they fail."""
    if not ctx.project_dir.is_dir():
        return 1, {"command": "judge", "project": ctx.project, "judge": None, "why": None,
                   "detail": "The project folder does not exist yet; set the project up first."}
    judge, why = ("none", "chosen") if choice == "none" else host_judge(ctx)
    if judge == choice:
        write_judge(ctx, judge)
        return 0, dict(judge_report(judge, why), command="judge", project=ctx.project)
    return 1, dict(judge_report(chosen_judge(ctx) or "none", why), command="judge", project=ctx.project)


def parse(argv):
    parser = argparse.ArgumentParser(prog="nc_setup.py", description=__doc__.split("\n\n")[0])
    verbs = parser.add_subparsers(dest="verb", required=True)
    scan = verbs.add_parser("scan", help="look at this computer; change nothing")
    scan.add_argument("--record", action="store_true", help="also write the scan record into the project")
    verbs.add_parser("plan", help="scan, plus one verdict, a why and a time for every item")
    apply_ = verbs.add_parser("apply", help="install or repair what the plan says is missing")
    which = apply_.add_mutually_exclusive_group(required=True)
    which.add_argument("--item", choices=[item.id for item in ITEMS])
    which.add_argument("--all", action="store_true")
    ack = verbs.add_parser("ack", help="record a yes to a question setup asked")
    ack.add_argument("--item", required=True)
    judge = verbs.add_parser("judge", help="set the judge Hyperspace Engine's verifier uses here")
    judge.add_argument("--set", required=True, choices=JUDGE_CHOICES, dest="choice")
    for verb in (scan, verbs.choices["plan"], apply_, ack, judge):
        verb.add_argument("--project", required=True, help="absolute path of the project folder")
    return parser.parse_args(argv)


def main(argv=None, **overrides):
    for stream in (sys.stdout, sys.stderr):   # Windows consoles default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = parse(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    ctx = Ctx(args.project, **overrides)
    try:
        unseen_git(ctx)   # before any verb: every program this run starts gets the same PATH
        if args.verb == "scan":
            code, document = do_scan(ctx, args.record)
        elif args.verb == "plan":
            code, document = do_plan(ctx)
        elif args.verb == "ack":
            code, document = do_ack(ctx, args.item)
        elif args.verb == "judge":
            code, document = do_judge(ctx, args.choice)
        else:
            code, document = do_apply(ctx, None if args.all else args.item)
    except UsageError as exc:
        print("nc_setup.py: %s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:   # still one JSON document, and never a zero exit
        traceback.print_exc(file=sys.stderr)
        code = 1
        document = {"command": args.verb, "project": ctx.project, "error": "%s: %s" % (type(exc).__name__, exc)}
    print(json.dumps(document, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
