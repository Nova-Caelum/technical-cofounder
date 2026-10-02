#!/usr/bin/env python3
"""Walk Technical Cofounder's real install on this computer, end to end.

    python scripts/ci_install_walk.py [--repo <checkout>] [--fresh-pc]

It does what a person's agent does after the install message is pasted, with
the real `claude` command line, the real first-step script and the real
install script, and checks each result:

  1. builds a stand-in catalog named nova-caelum in a temp folder: this
     checkout's two plugins as copies, Hyperspace Engine pinned to a release;
  2. the message's own two commands, `claude plugin marketplace add` and
     `claude plugin install technical-cofounder-setup@nova-caelum`, then
     reads where the setup plugin landed from `claude plugin list --json`;
  3. from that installed copy: the first-step script (bootstrap.sh under
     bash; bootstrap.ps1 under Windows PowerShell), which must end
     `BOOTSTRAP=OK python=<path>`;
  4. with that Python: plan, apply --all into a project folder that does not
     exist yet, scan --record, and a second apply --all that changes nothing;
  5. the team plugin as installed: its server started with the project's
     workspace Python, one worklog entry written and read back, and its
     session briefing run under bash.

jq is hidden from PATH for all of it, so the install script has to fetch it.

On Windows the walk hides Git as well: Git's folders are taken off PATH (and
off the saved PATH the scripts read), which is the case of a Git for Windows
installed to stay off PATH. Before that it runs the first step as a dry run
and for real with Git hidden from PATH only, and prints which branch it took.

--fresh-pc (Windows, continuous integration only) is for a runner whose Git
was really uninstalled: the first step installs Git and asks for a restart,
then a new session, with the PATH Windows saved, carries on with the walk.

Everything lives in one new temp folder (the Claude config, the catalog, the
tools folder, the project), which is left in place. Outside continuous
integration uv's downloads go there too. In continuous integration uv and
its Python are installed where a person's would be.

Every command and its output is printed. The last line is INSTALL_WALK=PASS
or INSTALL_WALK=FAIL, and the exit code matches.

Standard library only. Python 3.11 or newer.
"""
import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

MARKETPLACE = "nova-caelum"
TEAM = "technical-cofounder@nova-caelum"
ENGINE = "hyperspace-engine@nova-caelum"
SETUP = "technical-cofounder-setup@nova-caelum"
ENGINE_URL = "https://github.com/Nova-Caelum/hyperspace-engine.git"
ENGINE_SHA = "ba35bfd90fd31ab99fcf767b20a57db3d4721c11"   # tag hyperspace-engine--v0.1.4
ENGINE_VERSION = "0.1.4"
# A real catalog reached by a Git address, for the one check that needs a clone.
GIT_CATALOG = "https://github.com/Nova-Caelum/technical-cofounder.git"

VERDICTS = ("ready", "install", "upgrade", "repair", "needs-you", "needs-restart")
ITEMS = (
    "claude-cli", "git", "uv", "python", "jq", "network", "project-folder",
    "existing-config", "marketplace", "team-plugin", "engine-env", "obsidian",
)
MIN_PYTHON = (3, 11)
LAST_LINE = re.compile(r"^BOOTSTRAP=(?:(OK) python=(.+)|(NEEDS_RESTART|NEEDS_YOU) reason=(.+))$")
INSTALLED_GIT = ("package-manager", "direct-download", "package-manager-failed-then-direct-download")


# ---------------------------------------------------------------------------
# The pure parts: what the walk builds, and what it concludes from output.
# ---------------------------------------------------------------------------

def build_marketplace(repo, folder):
    """A stand-in for the public catalog: this checkout's team and setup
    plugins as copies, and Hyperspace Engine by HTTPS, pinned to a release."""
    repo, folder = Path(repo), Path(folder)
    for name in ("technical-cofounder", "technical-cofounder-setup"):
        shutil.copytree(repo / "plugins" / name, folder / "plugins" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    catalog = {
        "name": MARKETPLACE,
        "owner": {"name": "Nova Caelum"},
        "description": "Stand-in catalog built by the install walk.",
        "plugins": [
            {"name": "technical-cofounder", "source": "./plugins/technical-cofounder",
             "description": "The team plugin, as it is in this checkout."},
            {"name": "technical-cofounder-setup", "source": "./plugins/technical-cofounder-setup",
             "description": "The setup plugin, as it is in this checkout."},
            {"name": "hyperspace-engine", "source": {"source": "url", "url": ENGINE_URL, "sha": ENGINE_SHA},
             "description": "Hyperspace Engine, from its public repository."},
        ],
    }
    (folder / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (folder / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return catalog


def parse_bootstrap(out):
    """(status, value) from the last line the first-step script printed:
    ("OK", the Python's path), ("NEEDS_RESTART" or "NEEDS_YOU", the reason),
    or (None, that last line) when it is none of the three forms."""
    lines = [line.strip() for line in (out or "").splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    match = LAST_LINE.match(last)
    if not match:
        return None, last
    if match.group(1):
        return "OK", match.group(2)
    return match.group(3), match.group(4)


def git_branch(out):
    """Which way the Windows first step went about Git, from what it printed."""
    status, value = parse_bootstrap(out)
    if "(not on PATH; using it directly)" in out:
        return "used-directly"
    if "bootstrap: Git is already here" in out:
        return "present"
    if "bootstrap: would run: winget install" in out or "bootstrap: would download" in out:
        return "would-install"
    package_manager = "bootstrap: running: winget install" in out
    download = "trying the installer from GitHub" in out or "winget is missing; downloading" in out
    if package_manager or download:
        if status != "NEEDS_RESTART":
            return "install-failed"
        if package_manager and download:
            return "package-manager-failed-then-direct-download"
        return "direct-download" if download else "package-manager"
    if status == "NEEDS_RESTART" and "this session started before it was" in value:
        return "stale-session"
    return "unknown"


def _holds(folder, name):
    return os.path.isfile(os.path.join(folder, name))


def windows_own(path):
    """Windows ships its own bash.exe that is not Git Bash."""
    folded = str(path).replace("/", "\\").rstrip("\\").casefold() + "\\"
    return "\\windows\\system32\\" in folded or "\\windowsapps\\" in folded


def path_without_git(path, sep=os.pathsep, holds=_holds):
    """(PATH, the folders taken off it): every folder that holds git.exe, or
    a bash.exe that is not Windows' own, is taken off."""
    kept, removed = [], []
    for folder in path.split(sep):
        if not folder:
            continue
        if holds(folder, "git.exe") or (holds(folder, "bash.exe") and not windows_own(folder)):
            removed.append(folder)
        else:
            kept.append(folder)
    return sep.join(kept), removed


def path_without_jq(path, mirror_root, system, sep=os.pathsep):
    """(PATH, the folders that held jq). On Windows such a folder is left
    out. On macOS and Linux jq sits in /usr/bin beside everything else, so
    the folder is replaced by a new one that links to all of it but jq."""
    name = "jq.exe" if system == "windows" else "jq"
    kept, changed = [], []
    for folder in path.split(sep):
        if not folder:
            continue
        if not os.path.isfile(os.path.join(folder, name)):
            kept.append(folder)
            continue
        changed.append(folder)
        if system == "windows":
            continue
        mirror = Path(mirror_root) / str(len(changed))
        mirror.mkdir(parents=True)
        for entry in os.scandir(folder):
            if entry.name != name:
                os.symlink(entry.path, mirror / entry.name)
        kept.append(str(mirror))
    return sep.join(kept), changed


def _plain(entry):
    """A Windows PATH entry as Windows compares it: no letter case, no
    trailing backslash."""
    return str(entry).strip().replace("/", "\\").rstrip("\\").casefold()


def path_entries(text, sep=";"):
    return [_plain(entry) for entry in (text or "").split(sep) if entry.strip()]


def on_path(folder, text, sep=";"):
    return _plain(folder) in path_entries(text, sep)


def restarted_path(saved, current, is_git, sep=";"):
    """The PATH a program started after a restart gets: what Windows saved,
    then whatever this session added that is not a Git folder, so Git is
    seen only if the saved PATH leads to it."""
    kept, seen = [], set()
    for folder in [f for f in saved.split(sep)] + [f for f in current.split(sep) if not is_git(f)]:
        if folder.strip() and _plain(folder) not in seen:
            seen.add(_plain(folder))
            kept.append(folder.strip())
    return sep.join(kept)


def plan_problems(doc):
    """Why this is not a plan of the twelve items with one of the six
    verdicts each; empty when it is."""
    rows = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return ["the plan is not a document with a list of items: %r" % (doc,)]
    ids = [row.get("id") for row in rows]
    problems = []
    missing = [item for item in ITEMS if item not in ids]
    if missing:
        problems.append("the plan has no row for: %s" % ", ".join(missing))
    extra = sorted({str(i) for i in ids if i not in ITEMS} | {str(i) for i in ids if ids.count(i) > 1})
    if extra:
        problems.append("the plan has rows it should not have, or has them twice: %s" % ", ".join(extra))
    for row in rows:
        if row.get("verdict") not in VERDICTS:
            problems.append("%s has the verdict %r, which is not one of the six" % (row.get("id"), row.get("verdict")))
    return problems


def verdicts(doc):
    rows = doc.get("items") if isinstance(doc, dict) else None
    return {row.get("id"): row.get("verdict") for row in rows or [] if isinstance(row, dict)}


def not_ready(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        return {"(no document)": "missing"}
    return {item: verdict for item, verdict in verdicts(doc).items() if verdict != "ready"}


def acted_on(doc):
    results = doc.get("results") if isinstance(doc, dict) else None
    return [r.get("id") for r in results or [] if isinstance(r, dict) and r.get("acted")]


def plugin_problems(entries, plugin_ids):
    """Why each of these plugins is not enabled and loaded; empty when all are."""
    if not isinstance(entries, list):
        return ["`claude plugin list --json` did not print a list"]
    problems = []
    for plugin_id in plugin_ids:
        mine = [e for e in entries if isinstance(e, dict) and e.get("id") == plugin_id]
        if any(e.get("enabled") and not e.get("errors") for e in mine):
            continue
        if not mine:
            problems.append("%s is not installed" % plugin_id)
        elif any(e.get("errors") for e in mine):
            problems.append("%s did not load: %s" % (plugin_id, "; ".join(
                str(error) for e in mine for error in (e.get("errors") or []))))
        else:
            problems.append("%s is switched off" % plugin_id)
    return problems


def plugin_entry(entries, plugin_id):
    mine = [e for e in entries or [] if isinstance(e, dict) and e.get("id") == plugin_id and e.get("installPath")]
    mine.sort(key=lambda e: not e.get("enabled"))
    return mine[0] if mine else None


def install_path(entries, plugin_id):
    entry = plugin_entry(entries, plugin_id)
    return entry["installPath"] if entry else None


def server_command(entry, server, project, plugin_root):
    """The command Claude Code starts for one of a plugin's servers, with the
    two names it fills in filled in."""
    spec = (entry.get("mcpServers") or {}).get(server) if isinstance(entry, dict) else None
    if not isinstance(spec, dict) or not spec.get("command"):
        return None

    def fill(text):
        return str(text).replace("${CLAUDE_PROJECT_DIR}", str(project)).replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))

    return [fill(spec["command"])] + [fill(arg) for arg in spec.get("args") or []]


def server_requests(summary, project):
    """What the walk says to the team's server: start, write one worklog
    entry, read the recent ones back."""
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "ci-install-walk", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "worklog_append",
            "arguments": {"summary": summary, "author": "ci-install-walk", "tags": ["install-walk"], "root": str(project)}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "worklog_recent", "arguments": {"n": 5, "root": str(project)}}},
    ]
    return "".join(json.dumps(message) + "\n" for message in messages)


def _tool_text(answer):
    result = answer.get("result") if isinstance(answer, dict) else None
    content = result.get("content") if isinstance(result, dict) else None
    text = " ".join(str(part.get("text", "")) for part in content or [] if isinstance(part, dict))
    return (isinstance(result, dict) and result.get("isError") is False), text


def server_problems(out, summary):
    """Why the server's answers are not a valid start, an entry written and
    the same entry read back; empty when they are."""
    answers = {}
    for line in (out or "").splitlines():
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict) and "id" in message:
            answers[message["id"]] = message
    problems = []
    result = (answers.get(1) or {}).get("result")
    valid = (
        isinstance(result, dict) and (answers[1].get("jsonrpc") == "2.0")
        and isinstance(result.get("serverInfo"), dict) and result["serverInfo"].get("name")
        and isinstance(result.get("capabilities"), dict) and "tools" in result["capabilities"]
    )
    if not valid:
        problems.append("initialize got no valid answer: %r" % (answers.get(1),))
    ok, text = _tool_text(answers.get(2))
    if not ok:
        problems.append("worklog_append failed: %s" % (text or answers.get(2)))
    ok, text = _tool_text(answers.get(3))
    if not ok:
        problems.append("worklog_recent failed: %s" % (text or answers.get(3)))
    elif summary not in text:
        problems.append("worklog_recent did not return the entry %r" % summary)
    return problems


def hook_commands(declared, event):
    """The commands a plugin's hooks.json has Claude Code run for one event."""
    groups = (declared.get("hooks") or {}).get(event) if isinstance(declared, dict) else None
    return [
        hook["command"] for group in groups or [] if isinstance(group, dict)
        for hook in group.get("hooks") or []
        if isinstance(hook, dict) and hook.get("type") == "command" and hook.get("command")
    ]


def health_lines(text):
    return [line.rstrip() for line in (text or "").splitlines() if line.startswith("## Health")]


def snapshot(root):
    """Every file and folder under root: kind, size, modification time."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        st = path.lstat()
        is_dir = path.is_dir() and not path.is_symlink()
        found[path.relative_to(root).as_posix()] = ("dir" if is_dir else "file", 0 if is_dir else st.st_size, st.st_mtime_ns)
    return found


def changes(before, after):
    found = []
    for key in sorted(set(before) | set(after)):
        if key not in before:
            found.append("added: " + key)
        elif key not in after:
            found.append("removed: " + key)
        elif before[key] != after[key]:
            found.append("changed: " + key)
    return found


def _same(path):
    return os.path.normcase(os.path.realpath(str(path)))


def python_problems(version, path, already_here):
    """Why the Python the first step handed over will not do; empty when it
    is new enough and is not one this machine already had."""
    problems = []
    if tuple(version[:2]) < MIN_PYTHON:
        problems.append("the first step's Python is %s; setup needs 3.11 or newer" % ".".join(str(v) for v in version))
    if _same(path) in {_same(other) for other in already_here if other}:
        problems.append("the first step handed over a Python this machine already had: %s" % path)
    return problems


# ---------------------------------------------------------------------------
# The walk.
# ---------------------------------------------------------------------------

def detect_system():
    if sys.platform == "darwin":
        return "macos"
    return "windows" if sys.platform == "win32" else "linux"


def json_document(out):
    try:
        return json.loads(out)
    except (TypeError, ValueError):
        return None


class Walk:
    """Runs commands with their input closed, prints each one with its
    output, and collects failures instead of stopping at the first."""

    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n" + "=" * 78 + "\n" + title + "\n" + "=" * 78, flush=True)

    def note(self, text):
        print(text, flush=True)

    def expect(self, condition, text):
        print(("ok: " if condition else "FAIL: ") + text, flush=True)
        if not condition:
            self.failures.append(text)
        return bool(condition)

    def none_of(self, problems, text):
        """One expectation for a list of problems: fine when it is empty."""
        return self.expect(not problems, text if not problems else "%s: %s" % (text, "; ".join(problems)))

    def run(self, argv, env, cwd=None, timeout=900, label=None, text_in=None, flags=0):
        argv = [str(part) for part in argv]
        print("\n$ %s%s" % (label or " ".join(argv), "   (in %s)" % cwd if cwd else ""), flush=True)
        options = dict(cwd=None if cwd is None else str(cwd), env=env, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
        if text_in is None:
            options["stdin"] = subprocess.DEVNULL
        else:
            options["input"] = text_in
        if flags:
            options["creationflags"] = flags
        started = time.time()
        try:
            done = subprocess.run(argv, **options)
            code, out, err = done.returncode, done.stdout, done.stderr
        except FileNotFoundError as exc:
            code, out, err = 127, "", str(exc)
        except subprocess.TimeoutExpired as exc:
            code, out, err = 124, _text(exc.stdout), _text(exc.stderr) + "[no answer within %s seconds]" % timeout
            self.failures.append("timed out: " + (label or " ".join(argv)))
        except OSError as exc:
            code, out, err = 126, "", str(exc)
        print("exit: %s  (%.1fs)\n--- stdout\n%s--- stderr\n%s--- end" % (
            code, time.time() - started, _block(out), _block(err)), flush=True)
        return code, out, err


def _text(data):
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data or ""


def _block(text):
    text = _text(text)
    return text if text.endswith("\n") or not text else text + "\n"


def which(name, env):
    return shutil.which(name, path=env.get("PATH", ""))


def git_root_of(git):
    """The Git for Windows folder this git.exe belongs to: the nearest one
    above it that has Git's own bin\\bash.exe."""
    for parent in list(Path(git).parents)[:3]:
        if (parent / "bin" / "bash.exe").is_file():
            return parent
    return None


def installed_gits(env):
    """Where the Git for Windows installer puts git.exe, as the first-step
    script looks for it."""
    roots = [env.get("PROGRAMFILES"), env.get("PROGRAMW6432"), env.get("PROGRAMFILES(X86)")]
    if env.get("LOCALAPPDATA"):
        roots.append(os.path.join(env["LOCALAPPDATA"], "Programs"))
    found = []
    for root in roots:
        candidate = Path(root) / "Git" / "cmd" / "git.exe" if root else None
        if candidate and candidate.is_file() and candidate not in found:
            found.append(candidate)
    return found


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Install:
    """One walk: the folders it uses, the environment it hands to every
    program, and the steps."""

    def __init__(self, walk, repo, fresh_pc):
        self.w = walk
        self.repo = Path(repo).resolve()
        self.fresh_pc = fresh_pc
        self.system = detect_system()
        self.windows = self.system == "windows"
        self.root = Path(tempfile.mkdtemp(prefix="nc-install-walk-")).resolve()
        for name in ("claude-config", "tools", "work", "empty"):
            (self.root / name).mkdir()
        self.catalog = self.root / "marketplace"
        self.tools = self.root / "tools"
        self.project = self.root / "work" / "my-project"
        self.flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.base = self.base_env()
        self.env = dict(self.base)     # the session: what the first step and the install script get
        self.setup_root = None         # where the setup plugin landed
        self.python = None             # the Python the first step proved
        self.git_root = None           # Windows: the Git for Windows folder
        self.powershell = None
        self.powershell_version = ""
        self.saved_path = ""

    # -- the environment ------------------------------------------------------
    def base_env(self):
        env = dict(os.environ)
        for name in ("CLAUDECODE", "NC_PERSISTED_PATH", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT"):
            env.pop(name, None)
        env.update({
            "CLAUDE_CONFIG_DIR": str(self.root / "claude-config"),
            "NC_TOOLS_DIR": str(self.root / "tools"),
            "NC_MARKETPLACE_SOURCE": str(self.root / "marketplace"),
        })
        if not os.environ.get("CI"):
            for name, folder in (("UV_PYTHON_INSTALL_DIR", "uv-python"), ("UV_PYTHON_BIN_DIR", "uv-bin"),
                                 ("UV_CACHE_DIR", "uv-cache")):
                env[name] = str(self.root / folder)
        return env

    def claude(self, env):
        return which("claude", env) or "claude"

    def first_step(self, script_root, env, *args, timeout=1800):
        """Run the first-step script of this system, from `script_root`."""
        installer = Path(script_root) / "installer"
        if self.windows:
            argv = [self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(installer / "bootstrap.ps1"), *args]
        else:
            argv = [which("bash", env) or "bash", str(installer / "bootstrap.sh"), *args]
        code, out, err = self.w.run(argv, env, timeout=timeout, flags=self.flags)
        return code, out, err, parse_bootstrap(out)

    def setup(self, *args, env=None, timeout=300, python=None):
        """One verb of the install script, run from the installed copy with
        the Python the first step proved."""
        script = Path(self.setup_root) / "installer" / "nc_setup.py"
        code, out, _ = self.w.run([python or self.python, script, *args], env or self.env, timeout=timeout)
        return code, json_document(out)

    # -- the steps --------------------------------------------------------------
    def facts(self):
        w = self.w
        w.section("This computer")
        w.note("system: %s %s (%s)" % (self.system, platform.machine(), platform.platform()))
        w.note("the Python running this walk: %s (%s)" % (sys.executable, sys.version.split()[0]))
        w.note("checkout: %s   commit: %s" % (self.repo, os.environ.get("GITHUB_SHA", "(not in continuous integration)")))
        w.note("temp folder for everything: %s" % self.root)
        w.note("uv's own files: %s" % ("where a person's would be (continuous integration)" if os.environ.get("CI")
                                         else "in the temp folder (not continuous integration)"))
        w.note("PATH: %s" % self.base.get("PATH", ""))
        w.expect(sys.version_info[:2] >= MIN_PYTHON, "this walk runs on Python 3.11 or newer")
        code, _, _ = w.run([self.claude(self.base), "--version"], self.base, timeout=120)
        w.expect(code == 0, "`claude --version` works")
        if not self.windows:
            return
        self.powershell = which("powershell", self.base)
        w.expect(bool(self.powershell), "powershell.exe, which is Windows PowerShell, is on PATH: %s" % self.powershell)
        _, out, _ = w.run([self.powershell or "powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                          self.base, timeout=120)
        self.powershell_version = out.strip()
        w.note("POWERSHELL_VERSION=%s" % self.powershell_version)
        w.expect(self.powershell_version.startswith("5.1."), "powershell.exe is Windows PowerShell 5.1")
        for name in ("git", "bash", "jq", "winget", "uv", "python", "py"):
            w.note("on PATH, %s: %s" % (name, which(name, self.base)))

    def build_catalog(self):
        w = self.w
        w.section("The stand-in catalog")
        catalog = build_marketplace(self.repo, self.catalog)
        w.note("%s\n%s" % (self.catalog / ".claude-plugin" / "marketplace.json", json.dumps(catalog, indent=2)))

    def hide_jq(self, env):
        w = self.w
        sep = ";" if self.windows else os.pathsep
        mirror = Path(tempfile.mkdtemp(prefix="path-", dir=self.root))
        env["PATH"], changed = path_without_jq(env.get("PATH", ""), mirror, self.system, sep=sep)
        w.note("JQ_HIDDEN folders=%s" % (changed or "none: this machine had no jq on PATH"))
        w.expect(which("jq", env) is None, "jq is hidden from PATH")
        for name in ("claude", "bash" if not self.windows else "powershell"):
            w.expect(which(name, env) is not None, "%s is still on PATH with jq hidden" % name)

    def hide_git(self):
        """Windows, in the three-system job: Git is on this machine, and the
        session is given a PATH that does not lead to it."""
        w = self.w
        w.section("Windows: Git hidden from PATH")
        git = which("git", self.base)
        self.git_root = git_root_of(git) if git else None
        w.expect(self.git_root is not None, "this machine has a Git for Windows to hide: %s" % self.git_root)
        self.hide_jq(self.env)
        self.env["PATH"], removed = path_without_git(self.env["PATH"], sep=";")
        w.note("GIT_HIDDEN=yes removed=%s" % removed)
        w.expect(bool(removed) and which("git", self.env) is None, "with those folders off PATH there is no `git`")
        bash = which("bash", self.env)
        w.expect(bool(bash) and windows_own(bash),
                 "with Git hidden, `bash` still resolves to Windows' own stand-in, which is not Git Bash: %s" % bash)

    def read_saved_path(self):
        """The PATH Windows saved, read the way bootstrap.ps1 reads it and the
        way nc_setup.py reads it."""
        w = self.w
        _, out, _ = w.run([self.powershell, "-NoProfile", "-Command",
                           "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
                           "[Environment]::GetEnvironmentVariable('Path','User')"], self.base, timeout=120)
        self.saved_path = out.strip()
        return self.saved_path

    def message_commands(self):
        """Step 3 and the start of step 4 of the pasted message. The message
        makes sure of Git first, so these run with Git where the message
        left it: on PATH."""
        w = self.w
        w.section("The pasted message's own commands")
        env = dict(self.env)
        if self.windows and not self.fresh_pc:
            env = dict(self.base)
            env["PATH"] = path_without_jq(env["PATH"], self.root / "unused", self.system, sep=";")[0]
        claude = self.claude(env)
        code, _, _ = w.run([claude, "plugin", "marketplace", "add", self.catalog], env, cwd=self.root, timeout=300)
        w.expect(code == 0, "`claude plugin marketplace add <stand-in>` exits 0")
        code, _, _ = w.run([claude, "plugin", "install", SETUP], env, cwd=self.root, timeout=300)
        w.expect(code == 0, "`claude plugin install %s` exits 0" % SETUP)
        code, out, _ = w.run([claude, "plugin", "list", "--json"], env, cwd=self.root, timeout=300)
        entries = json_document(out)
        w.none_of(plugin_problems(entries, [SETUP]), "the setup plugin is installed and enabled")
        self.setup_root = install_path(entries, SETUP)
        w.note("SETUP_INSTALL_PATH=%s" % self.setup_root)
        if not w.expect(bool(self.setup_root) and Path(self.setup_root).is_dir(),
                        "`claude plugin list --json` gives the setup plugin's installPath, and it is a folder"):
            return False
        source = self.repo / "plugins" / "technical-cofounder-setup"
        for part in ("skills/setup/SKILL.md", "installer/bootstrap.sh", "installer/bootstrap.ps1",
                     "installer/nc_setup.py", "setup/steps.json"):
            landed = Path(self.setup_root) / part
            w.expect(landed.is_file() and landed.read_bytes() == (source / part).read_bytes(),
                     "the installed copy has %s, byte for byte as in the checkout" % part)
        return True

    def git_hidden_first_step(self):
        """Windows, three-system job: what the first step decides with Git
        hidden from PATH, as a dry run and for real."""
        w = self.w
        w.section("Windows: the first step with Git hidden from PATH")
        saved = self.read_saved_path()
        nc = load_module(Path(self.setup_root) / "installer" / "nc_setup.py", "nc_setup_installed")
        registry = nc.registry_path()
        w.note("the saved PATH as nc_setup.py reads it from the registry:\n%s" % registry)
        w.expect(path_entries(registry) == path_entries(saved) and bool(path_entries(saved)),
                 "nc_setup.py's registry read gives the same saved PATH as PowerShell's (%d entries)" % len(path_entries(saved)))
        git_cmd = self.git_root / "cmd"
        stale = on_path(git_cmd, saved)
        w.note("GIT_ON_SAVED_PATH=%s (%s)" % ("yes" if stale else "no", git_cmd))
        expected = "stale-session" if stale else "used-directly"

        w.note("\n-- dry run on a computer with no Git anywhere: Git's folders off PATH, and the places its "
               "installer uses pointed at an empty folder")
        bare = dict(self.env)
        for name in ("PROGRAMFILES", "PROGRAMW6432", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            bare[name] = str(self.root / "empty")
        code, out, _, (status, value) = self.first_step(self.setup_root, bare, "-DryRun", timeout=300)
        w.expect(code == 4 and status == "NEEDS_RESTART" and git_branch(out) == "would-install",
                 "it decides to install Git and to ask for a restart (exit %s, %s)" % (code, git_branch(out)))
        w.expect("Git is already here" not in out, "a `bash` under System32 alone is not taken for Git")
        w.note("WOULD_INSTALL_GIT_WITH=%s" % ("the package manager (winget)" if "would run: winget" in out
                                               else "the direct download (winget is missing)"))

        w.note("\n-- dry run with Git's folders off PATH only; the saved PATH is the registry's")
        code, out, _, (status, value) = self.first_step(self.setup_root, self.env, "-DryRun", timeout=300)
        w.note("FIRST_STEP_DRY_RUN_DECISION=%s" % git_branch(out))
        w.expect(git_branch(out) == expected,
                 "the dry run rules %s, as the saved PATH says it should" % expected)

        w.note("\n-- the same for real")
        code, out, _, (status, value) = self.first_step(self.setup_root, self.env)
        branch = git_branch(out)
        w.note("FIRST_STEP_REAL_RUN_GIT_HIDDEN branch=%s last_line=BOOTSTRAP=%s" % (branch, status))
        w.expect(branch == expected and code == (4 if stale else 0),
                 "the real run takes the same branch (%s, exit %s)" % (branch, code))
        w.note("GIT_INSTALL_EXERCISED=neither (Git is on this runner's disk, so the first step never installs it here: "
               "not the package-manager install, not the direct-download fallback)")
        return stale

    def keep_git_off_path(self):
        """From here on the session is the case of a Git for Windows that was
        installed to stay off PATH: its folders are on neither PATH."""
        self.env["NC_PERSISTED_PATH"] = self.env["PATH"]
        self.w.note("NC_PERSISTED_PATH is now the same PATH without Git, so Git is on neither the session's PATH "
                    "nor the saved one")

    def fresh_pc_first_run(self):
        """Windows, the no-Git job: Git was really uninstalled. The first
        step, from the checkout, has to install it and ask for a restart."""
        w = self.w
        w.section("Windows with no Git at all: the first step installs it")
        self.hide_jq(self.env)
        bash = which("bash", self.env)
        gone = which("git", self.env) is None and not installed_gits(self.env) and (bash is None or windows_own(bash))
        w.note("on PATH, git: %s   bash: %s   Git installs on disk: %s" % (
            which("git", self.env), bash, installed_gits(self.env) or "none"))
        if not w.expect(gone, "Git and Git Bash are gone from this machine"):
            return False
        w.note("GIT_ABSENT=yes")
        source = self.repo / "plugins" / "technical-cofounder-setup"
        code, out, _, (status, value) = self.first_step(source, self.env, timeout=2400)
        branch = git_branch(out)
        w.note("GIT_INSTALL_EXERCISED=%s" % branch)
        ok = w.expect(code == 4 and status == "NEEDS_RESTART" and branch in INSTALLED_GIT,
                      "the first step installed Git and asked for a restart (exit %s, BOOTSTRAP=%s, %s)" % (code, status, branch))
        found = installed_gits(self.env)
        w.expect(bool(found), "a Git for Windows is on disk afterwards: %s" % (found or "none"))
        if not (ok and found):
            return False
        self.git_root = git_root_of(found[0])
        w.expect(self.git_root is not None, "it has its own Git Bash beside it: %s" % self.git_root)
        code, _, _ = w.run([found[0], "--version"], self.env, timeout=120)
        w.expect(code == 0, "the installed Git runs")

        w.section("Windows with no Git at all: a new session after the restart")
        saved = self.read_saved_path()
        w.note("GIT_ON_SAVED_PATH=%s" % ("yes" if on_path(found[0].parent, saved) else "no"))
        root = _plain(self.git_root) + "\\"
        self.env["PATH"] = restarted_path(saved, self.env["PATH"], is_git=lambda folder: (_plain(folder) + "\\").startswith(root))
        self.hide_jq(self.env)
        w.note("the new session's PATH (the saved PATH first; Git only if the saved PATH leads to it):\n%s" % self.env["PATH"])
        w.note("GIT_VISIBLE_AFTER_RESTART=%s (%s)" % ("yes" if which("git", self.env) else "no", which("git", self.env)))
        return self.git_root is not None

    def real_first_step(self):
        w = self.w
        w.section("The first step, for real, from the installed copy")
        code, out, _, (status, value) = self.first_step(self.setup_root, self.env)
        if not w.expect(code == 0 and status == "OK", "its last line is BOOTSTRAP=OK python=<path> (exit %s, last line: %s)" % (
                code, "BOOTSTRAP=%s" % status if status else value)):
            return False
        self.python = value
        if self.windows:
            branch = git_branch(out)
            wanted = ("present", "used-directly") if self.fresh_pc else ("used-directly",)
            fine = w.expect(branch in wanted, "about Git, the first step ruled: %s" % branch)
            fine = w.expect("\\" not in value and "�" not in out,
                            "the Python path is printed with forward slashes and as readable UTF-8: %s" % value) and fine
            if fine and self.powershell_version.startswith("5.1."):
                w.note("WINDOWS_FIRST_STEP=PASS powershell=%s git_hidden=%s branch=%s" % (
                    self.powershell_version, "no (it was uninstalled, then installed by the first step)" if self.fresh_pc else "yes", branch))
        w.expect(Path(value).is_file(), "that Python exists: %s" % value)
        code, out, _ = w.run([value, "-c", "import sys, tomllib, sqlite3, venv; print(list(sys.version_info[:3])); print(sys.executable)"],
                             self.env, timeout=120)
        lines = out.splitlines()
        version = tuple(json_document(lines[0]) or (0, 0, 0)) if code == 0 and lines else (0, 0, 0)
        here = [sys.executable, getattr(sys, "_base_executable", None), which("python3", self.base), which("python", self.base)]
        w.note("Pythons this machine already had: %s" % [p for p in here if p])
        w.none_of(python_problems(version, value, here),
                  "it runs, is %s, and is not a Python this machine already had" % ".".join(str(v) for v in version))
        return code == 0

    def plan_and_apply(self):
        w = self.w
        project = self.project
        w.section("plan, apply --all, scan --record")
        code, plan = self.setup("plan", "--project", project)
        first = verdicts(plan)
        w.expect(code == 0, "plan exits 0")
        w.none_of(plan_problems(plan), "the plan has the twelve items, each with one of the six verdicts: %s" % first)
        for item, wanted in (("jq", "install"), ("project-folder", "install"), ("marketplace", "ready"),
                             ("team-plugin", "install"), ("engine-env", "install")):
            w.expect(first.get(item) == wanted, "%s is planned as %s" % (item, wanted))
        if self.windows and not self.fresh_pc:
            row = next((r for r in (plan or {}).get("items", []) if r.get("id") == "git"), {})
            w.expect(row.get("verdict") == "ready" and "(not on PATH; used directly)" in row.get("detail", ""),
                     "Git kept off PATH is ready and used where it is: %s" % row.get("detail"))
        if self.windows:
            self.plan_from_git_bash()

        w.expect(not project.exists(), "the project folder does not exist before apply")
        code, applied = self.setup("apply", "--project", project, "--all", timeout=3000)
        results = {r.get("id"): r for r in (applied or {}).get("results", []) if isinstance(r, dict)}
        w.expect(code == 0 and (applied or {}).get("stopped_at") is None and len(results) == len(ITEMS),
                 "apply --all exits 0 and walks all twelve items (stopped at: %s)" % (applied or {}).get("stopped_at", "no document"))
        acted = acted_on(applied)
        w.expect({"jq", "project-folder", "team-plugin", "engine-env"} <= set(acted),
                 "apply fetched jq, created the folder, installed the team and built the engine's workspace (acted on: %s)" % acted)
        jq = results.get("jq", {})
        w.expect(jq.get("before") == "install" and jq.get("after") == "ready",
                 "the jq item was install, and is ready after it: %s" % jq)
        landed = self.tools / ("jq.exe" if self.windows else "jq")
        w.expect(landed.is_file(), "jq landed in the tools folder: %s" % landed)
        code, _, _ = w.run([landed, "--version"], self.env, timeout=120)
        w.expect(code == 0, "that jq runs")
        w.expect(project.is_dir(), "the project folder exists: %s" % project)
        w.expect((applied or {}).get("restart_required") is True, "apply says a restart is required")

        code, scan = self.setup("scan", "--project", project, "--record")
        w.expect(code == 0, "scan --record exits 0")
        w.none_of(plan_problems(scan), "the re-scan has the twelve items")
        w.expect(not not_ready(scan), "every item is ready in the re-scan (not ready: %s)" % (not_ready(scan) or "none"))
        record = project / "core_text" / "setup-scan.json"
        w.expect(record.is_file(), "the scan record is written: %s" % record)
        if record.is_file():
            w.note(record.read_text(encoding="utf-8"))
            tools = (json_document(record.read_text(encoding="utf-8")) or {}).get("tools") or {}
            w.expect(all(tools.get(name) for name in ("python", "uv", "jq", "git", "claude")),
                     "the record says where python, uv, jq, git and claude are")
            if self.windows and not self.fresh_pc:
                root = _plain(self.git_root) + "\\"
                w.expect(_plain(tools.get("git", "")).startswith(root),
                         "the record names the Git that is kept off PATH: %s" % tools.get("git"))

    def plan_from_git_bash(self):
        """The command line the setup skill gives the agent, typed into Git
        Bash: the Python as the first step printed it, in double quotes."""
        w = self.w
        bash = self.git_root / "bin" / "bash.exe"
        line = '"%s" "%s/installer/nc_setup.py" plan --project "%s"' % (self.python, self.setup_root, self.project)
        w.note("\n-- the same plan, typed into Git Bash as the setup skill writes it")
        # The line travels in the environment: a double quote in a Windows
        # command line does not reach bash intact, and the quotes are the point.
        code, out, _ = w.run([bash, "-c", "eval $NC_WALK_LINE"], dict(self.env, NC_WALK_LINE=line), timeout=300,
                             label="(Git Bash, %s) %s" % (bash, line))
        doc = json_document(out)
        w.expect(code == 0 and not plan_problems(doc),
                 "from Git Bash, the forward-slash Python path in double quotes runs the install script and gives a plan")
        w.note("GIT_BASH_PLAN=%s" % ("PASS" if code == 0 and not plan_problems(doc) else "FAIL"))

    def installed_team(self):
        w = self.w
        project = self.project
        w.section("What is installed in the project")
        code, out, _ = w.run([self.claude(self.env), "plugin", "list", "--json"], self.env, cwd=project, timeout=300)
        entries = json_document(out)
        w.none_of(plugin_problems(entries, [TEAM, ENGINE]),
                  "`claude plugin list --json` in the project shows the team and Hyperspace Engine enabled with no errors")
        engine = plugin_entry(entries, ENGINE) or {}
        w.expect(engine.get("version") == ENGINE_VERSION,
                 "Hyperspace Engine is the pinned release %s (installed: %s)" % (ENGINE_VERSION, engine.get("version")))
        env_dir = project / ".hyperspace" / "env"
        python = env_dir / "Scripts" / "python.exe" if self.windows else env_dir / "bin" / "python"
        code, _, _ = w.run([python, "-c", "import hyperspace, sys; print(hyperspace.__file__); print(sys.version)"],
                           self.env, timeout=300)
        w.expect(code == 0, "the workspace's Python runs and imports hyperspace")
        return entries

    def second_apply(self):
        w = self.w
        w.section("A second apply --all")
        before = snapshot(self.project)
        code, again = self.setup("apply", "--project", self.project, "--all", timeout=3000)
        after = snapshot(self.project)
        w.expect(code == 0 and (again or {}).get("stopped_at") is None, "the second apply --all exits 0 and stops nowhere")
        w.expect(isinstance(again, dict) and not acted_on(again), "it acts on nothing (acted on: %s)" % acted_on(again))
        found = changes(before, after)
        w.expect(not found, "it changes no file in the project (%d entries compared)%s" % (
            len(before), "" if not found else ": " + "; ".join(found)))

    def team_plugin(self, entries):
        w = self.w
        project = self.project
        w.section("The team plugin, as installed")
        team = plugin_entry(entries, TEAM)
        if not w.expect(team is not None, "the team plugin's installPath is known"):
            return
        root = team["installPath"]
        env = dict(self.env, CLAUDE_PROJECT_DIR=str(project), CLAUDE_PLUGIN_ROOT=str(root))

        command = server_command(team, "cofounder", project=project, plugin_root=root)
        if w.expect(command is not None, "the team plugin declares its `cofounder` server: %s" % command):
            summary = "install walk %s" % uuid.uuid4().hex
            code, out, _ = w.run(command, env, cwd=project, timeout=300, text_in=server_requests(summary, project))
            w.expect(code == 0, "the server, started with the project's workspace Python, ends cleanly when its input closes")
            w.none_of(server_problems(out, summary),
                      "it answers `initialize`, takes one worklog entry and gives the same entry back")

        declared = json_document((Path(root) / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        commands = [c for c in hook_commands(declared, "SessionStart") if c.endswith("/hooks/session-preload.sh")]
        if not w.expect(len(commands) == 1, "the team plugin declares its session briefing for SessionStart: %s" % commands):
            return
        # Run the way Claude Code runs a hook: the declared command under bash
        # (Git Bash on Windows), the event on standard input. The command
        # travels in the environment so its own quotes reach bash intact.
        bash = self.git_root / "bin" / "bash.exe" if self.windows else which("bash", env) or "bash"
        event = json.dumps({"session_id": "install-walk", "hook_event_name": "SessionStart", "cwd": str(project), "source": "startup"})
        code, out, _ = w.run([bash, "-c", "eval $NC_WALK_LINE"], dict(env, NC_WALK_LINE=commands[0]), cwd=project,
                             timeout=300, text_in=event, label="(bash, %s) %s" % (bash, commands[0]))
        w.expect(code == 0, "the session briefing exits 0")
        w.expect("- technical-cofounder: present" in out, "its live primer ran, which takes a Python that works")
        w.expect(not health_lines(out), "it prints no `## Health` block on a healthy install (found: %s)" % (health_lines(out) or "none"))

    def windows_extras(self, stale):
        """Windows, three-system job: the two rules about a Git this session
        cannot see, in the install script, on a real Windows."""
        w = self.w
        w.section("Windows: the install script and a Git this session cannot see")
        w.note("-- Git's folders off PATH, and the saved PATH read from the registry")
        env = dict(self.env)
        env.pop("NC_PERSISTED_PATH")
        code, plan = self.setup("plan", "--project", self.root / "work" / "registry-check", env=env)
        row = next((r for r in (plan or {}).get("items", []) if r.get("id") == "git"), {})
        wanted = "needs-restart" if stale else "ready"
        agrees = w.expect(code == 0 and row.get("verdict") == wanted,
                          "the install script rules %s for Git, as the first-step script did from the same registry: %s" % (
                              wanted, row.get("detail")))
        w.note("REGISTRY_RULE_AGREES=%s" % ("yes" if agrees else "no"))

        w.note("\n-- a catalog that has to be cloned, added by the install script with Git on neither PATH")
        config = self.root / "claude-config-clone"
        config.mkdir()
        env = dict(self.env, CLAUDE_CONFIG_DIR=str(config), NC_MARKETPLACE_SOURCE=GIT_CATALOG)
        claude = self.claude(env)
        w.run([claude, "plugin", "marketplace", "list", "--json"], env, cwd=self.root, timeout=300,
              label="claude plugin marketplace list --json   # first call in a fresh config")
        self.setup("apply", "--project", self.root / "work" / "clone-check", "--item", "marketplace", env=env, timeout=900)
        w.note("(that catalog is not named nova-caelum, so the item itself does not turn ready; the clone is what is checked)")
        code, out, _ = w.run([claude, "plugin", "marketplace", "list", "--json"], env, cwd=self.root, timeout=300)
        listed = json_document(out) or []
        cloned = [m for m in listed if isinstance(m, dict) and "technical-cofounder" in json.dumps(m)]
        fine = w.expect(code == 0 and bool(cloned),
                        "`claude plugin marketplace add <a Git address>`, started by the install script, cloned the catalog")
        w.note("CLONE_WITH_GIT_OFF_PATH=%s" % ("PASS" if fine else "FAIL"))
        control = self.root / "claude-config-control"
        control.mkdir()
        env = dict(env, CLAUDE_CONFIG_DIR=str(control))
        code, _, _ = w.run([claude, "plugin", "marketplace", "add", GIT_CATALOG], env, cwd=self.root, timeout=900,
                           label="claude plugin marketplace add %s   # the same, without the install script's PATH" % GIT_CATALOG)
        w.note("for the record, not a check: without the install script putting Git's folder on PATH, the same command exits %s" % code)

    # -- the order ----------------------------------------------------------------
    def go(self):
        w = self.w
        self.facts()
        self.build_catalog()
        stale = None
        if self.fresh_pc:
            if not self.fresh_pc_first_run():
                return
        elif self.windows:
            self.hide_git()
            if self.git_root is None:
                return
        else:
            w.section("jq hidden from PATH")
            self.hide_jq(self.env)
        if not self.message_commands():
            return
        if self.windows and not self.fresh_pc:
            stale = self.git_hidden_first_step()
            self.keep_git_off_path()
        if not self.real_first_step():
            return
        self.plan_and_apply()
        entries = self.installed_team()
        self.second_apply()
        self.team_plugin(entries)
        if self.windows and not self.fresh_pc:
            self.windows_extras(stale)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):   # Windows consoles default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                        help="the checkout whose plugins are walked (default: the one this script is in)")
    parser.add_argument("--fresh-pc", action="store_true",
                        help="Windows runner whose Git was uninstalled: let the first step install it")
    args = parser.parse_args(argv)
    if args.fresh_pc and not (sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"):
        print("ci_install_walk.py: --fresh-pc installs Git for real; it runs only on a Windows runner in continuous integration",
              file=sys.stderr)
        return 2
    walk = Walk()
    try:
        Install(walk, args.repo, args.fresh_pc).go()
    except Exception:   # a crash in the walk is a failed walk, with its trail kept
        traceback.print_exc(file=sys.stdout)
        walk.failures.append("the walk itself raised an error (the traceback is above)")
    walk.section("Result")
    for failure in walk.failures:
        print("FAIL: " + failure)
    if not walk.failures:
        print("no failures")
    print("INSTALL_WALK=%s" % ("FAIL" if walk.failures else "PASS"), flush=True)
    return 1 if walk.failures else 0


if __name__ == "__main__":
    sys.exit(main())
