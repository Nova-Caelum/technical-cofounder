# This workspace

This project runs on the `base-novacaelum` Claude Code plugin.

- `.claude/rules/` — five behavior rules that load automatically every
  session. Each file's header says what it enforces and why.
- `user.md` — your personalization profile. Run `/base-novacaelum:onboard`
  to fill it in; agents read it at the start of every session.
- `worklog/` — the shared memory across sessions and agents. See
  `worklog/README.md` for how entries work.

Re-run `/base-novacaelum:setup` any time — it never overwrites a file
that's already here.
