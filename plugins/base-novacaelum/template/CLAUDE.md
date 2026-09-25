# This workspace

This project runs on the `technical-cofounder` Claude Code plugin.

- `.claude/rules/` — five behavior rules that load automatically every
  session. Each file's header says what it enforces and why.
- `user.md` — your personalization profile. Run `/technical-cofounder:onboard`
  to fill it in; agents read it at the start of every session.
- `worklog/` — the shared memory across sessions and agents. See
  `worklog/README.md` for how entries work.

Re-run `/technical-cofounder:init` any time — it never overwrites a file
that's already here.
