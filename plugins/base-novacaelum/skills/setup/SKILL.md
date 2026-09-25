---
name: setup
description: Use when a project needs setting up on this plugin — the user says "set up", "install", "get started", "onboard me", or a session starts with no user.md at the project root.
---

# Setup

The only conversational surface for turning on a project's starter workspace.
`/base-novacaelum:setup` and `/base-novacaelum:onboard` both point here; the
commands are one-line pointers, this skill is where the questions live.

Ask one question at a time. Wait for each answer before asking the next.
Nothing here overwrites a file that already exists at the destination —
`init_workspace.py` skips and reports every file it finds already in place.

## 1. Prerequisites and install scope

Check `python3` and `git` are on PATH (`python3 --version`, `git --version`).
If the user is leaning toward super in step 3, also check `node --version` —
super's `sequential-thinking` server needs Node; the other three super
services are hosted and need nothing local.

Then check install scope. Read `~/.claude/settings.json` — **read only,
never edit it.** If `base-novacaelum@technical-cofounder` is enabled there
at user scope, say in one line: enabled at user scope makes this the main
agent in *every* project on the machine, not just this one. Then offer the
two commands that move it to just this project — the user runs them, not
you:

```
claude plugin uninstall base-novacaelum@technical-cofounder --scope user
claude plugin install base-novacaelum@technical-cofounder --scope project
```

## 2. Obsidian?

Ask whether they want the Obsidian starter view: a minimal `.obsidian/`
config (core Bases plugin enabled, no community plugins needed) plus
`worklog/worklog.base`, a table view over every worklog entry's frontmatter
(date, author, summary, tags). Skip it and they still get the plain
`worklog/entries/*.md` files and `worklog.csv` index — just no Obsidian
view over them.

## 3. Base only, or base plus super?

Explain in one line each:
- **base** (already running this conversation): four agents, guardrail
  hooks, the working loop, a local verifier — no accounts, no servers.
- **super** (opt-in, `super-novacaelum`): Context7 documentation lookup, Exa
  web search, Browserbase cloud browser and step-by-step thinking, on the
  user's own keys — Context7 and Exa have usable free tiers before any key
  exists, Browserbase needs one to do anything.

## 4. Run the copy

Run, with the two flags this conversation just settled:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project-dir>" --obsidian|--no-obsidian --super|--no-super
```

`${CLAUDE_PLUGIN_ROOT}` resolves here — in skill content — even though it
does not resolve inside a slash command's own markdown body; that is why
this script call lives in the skill and the commands are one-line pointers
to it. Report exactly what the script printed: every `COPIED:` and
`SKIPPED:` line, and the `INIT_SUMMARY` line at the end.

## 5. If super: install it

When the user chose super in step 3, show the install command (project
scope, matching this plugin's own install — see "Install scope" in step 1
for why project scope is the default everywhere this skill speaks):

```
claude plugin install super-novacaelum@technical-cofounder --scope project
```

Then hand off to the `get-api-keys` skill (in `super-novacaelum`) to walk
through getting each service's key. `init_workspace.py --super` already
printed this same command and pointer — this step is where you actually
run it with the user.

## 6. Onboarding interview

Run this once `user.md` exists (step 4 copies it in from the template).
Ask one question at a time, in this order, and wait for each answer:

1. What are you building, and what's your role on it?
2. What machine(s)/OS do you work from?
3. How do you want to signal when you're `sharp`, `steady`, or `tired` —
   and how should the agent's shape change for each?
4. Do you want options presented, or a recommendation with the reasoning
   shown? How should uncertainty be flagged?
5. Timezone, and any batching or checkpoint preferences on long sessions?
6. Anything else that would change how an agent should work with you?

After each answer, write it into the matching section of `user.md`,
replacing the placeholder text — don't wait until the end to write
everything at once. When done, confirm the file is filled in, and mention
that `/base-novacaelum:setup` never overwrites it again, so updating it
later means editing `user.md` directly (or re-running `/base-novacaelum:onboard`).

## 7. What to try first

Close with three lines, concrete to what was just set up: one thing to ask
the default agent, one skill worth trying, and where the worklog lives (or
the worklog.base view, if Obsidian was chosen).

Source: Nova Caelum (MIT).
