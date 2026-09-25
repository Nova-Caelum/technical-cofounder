---
description: Copy the technical-cofounder starter workspace into this project
---

Set up this project with the technical-cofounder starter workspace: a short
`CLAUDE.md`, five behavior rules under `.claude/rules/`, a `user.md`
personalization profile, and a `worklog/` folder.

**Finding, not an assumption:** `${CLAUDE_PLUGIN_ROOT}` does not resolve
inside a command's own body, and it is not present in the environment of
Bash-tool commands either. Per Claude Code's documented substitution table
(code.claude.com/docs/en/plugins-reference, "Environment variables"),
`${CLAUDE_PLUGIN_ROOT}` only resolves in skill/agent content, hook and
monitor commands, and MCP/LSP server configs — slash commands are not one
of the listed components. So do this instead:

1. Locate this plugin's installed directory yourself. Run:
   `find ~/.claude -maxdepth 8 -type f -name init_workspace.py 2>/dev/null | grep base-novacaelum`
2. If that finds nothing (a local dev checkout, or a marketplace installed
   at a different root), widen the search until you find a file named
   `init_workspace.py` inside a `base-novacaelum/bin/` folder.
3. The plugin root is two directories up from that file
   (`<plugin-root>/bin/init_workspace.py`).
4. Run `python3 "<plugin-root>/bin/init_workspace.py" "$(pwd)"`.
5. Report exactly what it printed — every `COPIED:` and `SKIPPED:` line.
   It never overwrites a file that's already here; don't work around that.
