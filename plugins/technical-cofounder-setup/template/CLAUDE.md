# This workspace

This project runs on the `technical-cofounder` Claude Code plugin: a team of four
agents (`technical-cofounder` leads; `engineer` builds, `devops-lead` audits,
`lead-fde` sets up and teaches) and a worklog that carries what was decided
from one session to the next. The working loop is Hyperspace Engine's, which
arrives with the team: it takes a goal from framing to a tested build, and its
closing check compares each task with the files on disk before the task is
called done.

Where each piece lives:

- `core_text/` — about you and this setup. `core_text/user.md` is your
  profile, which agents read at the start of every session (run
  `/technical-cofounder-setup:start` and say "continue setup" to fill it in).
  `setup.json` records which setup steps are done, and `setup-guide.html`
  shows them as a page you can open in any browser.
- `worklog/` — the shared memory across sessions and agents. See
  `worklog/README.md` for how entries work.
- `.claude/rules/` — five behavior rules that load automatically every
  session. Each file's header says what it enforces and why.
- `_templates/` — starting points for your own skills, agents, rules and
  acceptance criteria.

At the start of every session the plugin's preload prints your profile, the
latest worklog entries and a live tech primer: which Nova Caelum plugins are
present or missing, and how far setup has got.

Run `/technical-cofounder-setup:start`, or say "continue setup", any time. It
never overwrites a file that's already here. Stuck, found a bug, or have an idea?
`/technical-cofounder:contact` reaches Nova Caelum.
