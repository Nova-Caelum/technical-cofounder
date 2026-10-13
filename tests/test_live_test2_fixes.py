"""Live install test 2 (2026-10-11): what a first-time Windows user ran into
during setup, held as text and behaviour so none of it comes back.

L14 the guide is a link, never opened   L15 one Obsidian viewer question
L16 a new session in the new folder     L17 the team is already active
L18 a pasted secret stays invisible     L10 uv's Python outside AppData
L2  the first question is the folder    L7  Ctrl-C cancels the GitHub login
L12 one contact command                 F14b a failure shows git's real error

Standard library only.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS = REPO_ROOT / "plugins"
SETUP = PLUGINS / "technical-cofounder-setup"
TEAM = PLUGINS / "technical-cofounder"
SKILL = SETUP / "skills" / "setup" / "SKILL.md"
STEPS = SETUP / "setup" / "steps.json"
BOOTSTRAP_PS1 = SETUP / "installer" / "bootstrap.ps1"
PRELOAD = TEAM / "hooks" / "session-preload.sh"
WALK = REPO_ROOT / "scripts" / "ci_install_walk.py"
CONTACT = "/technical-cofounder:contact-nova-caelum"
WINDOWS = sys.platform == "win32"
FOLDER_QUESTION = ("We're going to make a specific folder for your agents to live and own. "
                   "Where would you like it to be? And what would you like it to be called?")
FOLDER_WHY = ("It will make things more secure to confine your agents to one folder where they can "
              "work freely without having to touch everything else in your computer.")


def flat(text):
    return " ".join(text.split())


def skill():
    return SKILL.read_text(encoding="utf-8")


def section(text, heading):
    """The body under the first heading containing `heading`, up to the next
    heading of the same or a higher level."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        mark = re.match(r"(#+) ", line)
        if mark and heading in line:
            body = []
            for nxt in lines[i + 1:]:
                other = re.match(r"(#+) ", nxt)
                if other and len(other.group(1)) <= len(mark.group(1)):
                    break
                body.append(nxt)
            return flat("\n".join(body))
    raise AssertionError("no heading containing %r" % heading)


def shipped_text_files():
    for path in sorted(list(PLUGINS.rglob("*")) + [REPO_ROOT / "README.md"]):
        if path.is_file() and path.suffix in (".md", ".sh", ".py", ".json") and "template/.claude" not in path.as_posix():
            yield path


def load_nc_setup():
    spec = importlib.util.spec_from_file_location("nc_setup_lt2", SETUP / "installer" / "nc_setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class L14GuideIsALinkNotAWindow(unittest.TestCase):
    def test_setup_never_opens_the_guide_itself(self):
        text = skill()
        for opener in ("xdg-open", 'start ""', "run `open`"):
            with self.subTest(opener=opener):
                self.assertNotIn(opener, text)

    def test_the_link_is_given_when_they_ask_where_the_steps_are_and_is_clickable(self):
        guide = section(skill(), "Open the guide")
        self.assertIn("where to see the steps", guide)
        self.assertIn("file:///", guide)
        self.assertIn("Never print the HTML in the chat.", guide)

    def test_the_closing_gives_the_guide_link_once_as_a_reference(self):
        closing = section(skill(), "Closing")
        self.assertIn("GUIDE:", closing)
        self.assertIn("file:///", closing)


class L15OneObsidianViewerQuestion(unittest.TestCase):
    def setUp(self):
        self.step = section(skill(), "(`obsidian`)")

    def test_no_one_at_a_time_questions(self):
        self.assertNotIn("one at a time", self.step)

    def test_one_prompt_lists_every_file_type_and_keep_my_usual_apps(self):
        self.assertIn("one question", self.step.lower())
        self.assertIn("keep my usual apps", self.step.lower())
        for kind in ("Word", "PowerPoint", "SQLite", "JSON", "HTML"):
            with self.subTest(kind=kind):
                self.assertIn(kind, self.step)

    def test_it_says_all_in_one_viewer_free_and_the_security_stance(self):
        lower = self.step.lower()
        for needle in ("all-in-one", "free", "independent", "trust"):
            with self.subTest(needle=needle):
                self.assertIn(needle, lower)


class L16NewSessionInTheNewFolder(unittest.TestCase):
    def test_the_handover_says_new_session_in_that_folder_and_why(self):
        closing = section(skill(), "Closing")
        self.assertIn("NEW session", closing)
        self.assertIn("`<absolute project path>`", closing)
        self.assertIn("Code tab", closing)
        self.assertIn("New session", closing)
        self.assertRegex(closing, r"team, its memory and its hooks only load in a session started in that folder")


class L17TheTeamIsAlreadyActive(unittest.TestCase):
    LINE = "already active"

    def test_the_goodbye_says_it(self):
        closing = section(skill(), "Closing")
        self.assertIn(self.LINE, closing)
        self.assertIn("/goal", closing)
        self.assertIn("describe what you want", closing)

    def preload(self, project):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR")}
        env.update(CLAUDE_PROJECT_DIR=str(project), HOME=str(project / "home"))
        bash = shutil.which("bash") or "bash"
        r = subprocess.run([bash, str(PRELOAD)], input="{}", capture_output=True, text=True,
                           encoding="utf-8", env=env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def project(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "home").mkdir()
        (root / "core_text").mkdir()
        (root / "core_text" / "user.md").write_text("# profile\n", encoding="utf-8")
        return root

    def test_the_first_session_briefing_says_it(self):
        out = self.preload(self.project())
        self.assertIn(self.LINE, out)
        self.assertIn("/goal", out)

    def test_a_session_after_work_was_logged_does_not(self):
        project = self.project()
        (project / "worklog" / "entries").mkdir(parents=True)
        (project / "worklog" / "entries" / "2026-10-12T10-00-00-first.md").write_text(
            "---\nsummary: first\n---\n", encoding="utf-8")
        self.assertNotIn(self.LINE, self.preload(project))


class L18PastedSecretsStayInvisible(unittest.TestCase):
    def test_every_hidden_field_is_announced(self):
        found = []
        for path in PLUGINS.rglob("SKILL.md"):
            text = flat(path.read_text(encoding="utf-8"))
            if "hidden field" in text:
                found.append(path)
                with self.subTest(skill=str(path.relative_to(REPO_ROOT))):
                    self.assertIn("nothing will show", text)
                    self.assertIn("that's normal", text)
                    self.assertIn("press Enter", text)
        names = sorted(p.parent.name for p in found)
        self.assertEqual(names, ["get-api-keys", "super-setup"])


class L10UvPythonOutsideAppData(unittest.TestCase):
    def setUp(self):
        self.text = BOOTSTRAP_PS1.read_text(encoding="utf-8")

    def test_the_install_dir_is_set_under_the_profile_before_uv_installs_python(self):
        assign = self.text.find("$env:UV_PYTHON_INSTALL_DIR = ")
        self.assertGreater(assign, 0)
        line = self.text[assign:].splitlines()[0]
        self.assertIn(r".local\share\uv\python", line)
        self.assertNotIn("APPDATA", line.upper())
        self.assertLess(assign, self.text.index("& $uv python install 3.12"))
        self.assertLess(assign, self.text.index("Say \"would run: $uv python install 3.12\""))

    def test_the_install_walk_checks_where_the_product_put_python(self):
        walk = WALK.read_text(encoding="utf-8")
        self.assertIn("PYTHON_UNDER_PROFILE", walk)
        self.assertIn(r".local\\share\\uv\\python", walk)


@unittest.skipUnless(WINDOWS, "bootstrap.ps1 runs only on Windows")
class L10UvPythonOutsideAppDataOnWindows(unittest.TestCase):
    """bootstrap.ps1 for real, against a stand-in uv that records the
    install folder it was given."""

    STAND_IN = (
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(%r, 'a', encoding='utf-8') as log:\n"
        "    log.write(' '.join(args) + '|' + os.environ.get('UV_PYTHON_INSTALL_DIR', '') + '\\n')\n"
        "if args == ['python', 'find', '3.12']:\n"
        "    print(%r)\n"
        "sys.exit(0 if args[:1] == ['python'] else 64)\n"
    )

    def test_uv_is_given_a_folder_under_the_profile(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shims, log = root / "shims", root / "uv.log"
        shims.mkdir()
        (shims / "stand_in.py").write_text(self.STAND_IN % (str(log), sys.executable), encoding="utf-8")
        (shims / "uv.cmd").write_text('@echo off\n"%s" "%%~dp0stand_in.py" %%*\nexit /b %%ERRORLEVEL%%\n' % sys.executable,
                                      encoding="ascii", newline="\r\n")
        env = dict(os.environ)
        env.pop("UV_PYTHON_INSTALL_DIR", None)
        env["PATH"] = str(shims) + os.pathsep + env.get("PATH", "")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BOOTSTRAP_PS1)],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        wanted = os.path.join(os.environ["USERPROFILE"], ".local", "share", "uv", "python")
        for line in log.read_text(encoding="utf-8").splitlines():
            with self.subTest(call=line):
                self.assertEqual(line.split("|", 1)[1].lower(), wanted.lower())


class L2TheFirstQuestionIsTheFolder(unittest.TestCase):
    def test_the_skill_asks_it_verbatim_and_answers_why(self):
        where = section(skill(), "Where the project goes")
        self.assertIn(FOLDER_QUESTION, where)
        self.assertIn(FOLDER_WHY, where)
        self.assertNotIn("Ask what they want to call the project", where)

    def test_the_descriptions_no_longer_say_it_asks_what_to_call_your_project(self):
        steps = json.loads(STEPS.read_text(encoding="utf-8"))["steps"]
        does = next(s for s in steps if s["id"] == "prerequisites")["does"]
        self.assertNotIn("call your project", does)
        self.assertIn("folder", does)
        self.assertNotIn("asks what to call your project", (REPO_ROOT / "README.md").read_text(encoding="utf-8"))


class L7CtrlCCancelsTheGitHubLogin(unittest.TestCase):
    def test_the_login_step_warns_and_waits(self):
        github = section(skill(), "(`github`)")
        for needle in ("gh auth login --clipboard", "Ctrl-C", "cancels the login", "right-click",
                       "Ctrl-Shift-C", "Logged in as", "gh auth status"):
            with self.subTest(needle=needle):
                self.assertIn(needle, github)


class L12OneContactCommand(unittest.TestCase):
    BARE = re.compile(r"(?<![\w-])/(?:technical-cofounder:)?contact(?![\w-])")

    def test_the_bare_command_is_gone(self):
        self.assertFalse((TEAM / "commands" / "contact.md").exists())

    def test_nothing_points_at_it(self):
        for path in shipped_text_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertIsNone(self.BARE.search(text), self.BARE.search(text))

    def test_setup_goodbye_names_it_once(self):
        self.assertEqual(section(skill(), "Closing").count(CONTACT), 1)

    def test_the_session_briefing_names_it(self):
        self.assertIn(CONTACT, PRELOAD.read_text(encoding="utf-8"))


class F14bTheRealErrorLine(unittest.TestCase):
    GIT = ("Cloning into 'x'...\n"
           "error: unable to create file a/b.md: Filename too long\n"
           "fatal: unable to checkout working tree\n"
           "warning: Clone succeeded, but checkout failed.\n"
           "and retry with 'git restore --source=HEAD :/'\n")

    def setUp(self):
        self.nc = load_nc_setup()

    def test_the_first_error_or_fatal_line_wins(self):
        self.assertEqual(self.nc.failure_line(self.GIT), "error: unable to create file a/b.md: Filename too long")
        self.assertEqual(self.nc.failure_line("one\nFATAL: no\nError: later\n"), "FATAL: no")

    def test_without_one_it_is_the_last_line(self):
        self.assertEqual(self.nc.failure_line("first\n  last  \n\n"), "last")
        self.assertEqual(self.nc.failure_line(""), "")

    def test_a_failed_install_reports_it(self):
        failed = self.nc.Result(1, "", self.GIT)

        class Ctx:
            def run(self, argv, **options):
                return failed
        note = self.nc.run_install(Ctx(), ["git", "clone", "x"])
        self.assertIn("Filename too long", note)
        self.assertNotIn("git restore", note)


class Versions(unittest.TestCase):
    def test_every_changed_plugin_was_bumped(self):
        for plugin, before in (("technical-cofounder", "0.2.1"), ("technical-cofounder-setup", "0.1.1"),
                               ("super-novacaelum", "0.1.0")):
            with self.subTest(plugin=plugin):
                manifest = json.loads((PLUGINS / plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
                self.assertNotEqual(manifest["version"], before)


if __name__ == "__main__":
    unittest.main()
