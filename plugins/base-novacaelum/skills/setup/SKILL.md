---
name: setup
description: Use when a project needs setting up on this plugin or setup needs finishing — the user says "set up", "install", "get started", "onboard me" or "continue setup", or a session starts with no core_text/user.md.
---

# Setup

The only conversational surface for setting up a project.
`/base-novacaelum:setup` and `/base-novacaelum:onboard` point here.

Each step's purpose, cost, time and skip rules live in
`${CLAUDE_PLUGIN_ROOT}/setup/steps.json`: read it first. This skill says how
to run each step.

Every step:
- Ask one question at a time, and wait for the answer.
- Never overwrite or delete a file. Move or copy a user's file only on their yes.
- Never ask for a key, token or password in the chat.
- After every step, record it, which also refreshes the guide:

  ```
  <python> "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project-dir>" <step-id> done|skipped|pending [--choice key=value]
  ```

  `pending` reopens a step. A step accepts only the choice keys steps.json
  declares, each value one plain word (`yes`, `vscode`); the script refuses
  anything else, so free text never lands in `core_text/setup.json`.

## The Python from setup

Every Python command here is `<python> "<script>" args`, the same in sh,
PowerShell and cmd. `<python>` is the `python` choice in
`core_text/setup.json`: `env` is `.cofounder/env/bin/python` (from the project
root), `py` is `py -3`, `python3` and `python` are themselves. Unrecorded, it
is the first of `python3 -c "import sys"`, `python -c "import sys"` and
`py -3 -c "import sys"` that exits 0 (on Windows `python3` can be the Store
placeholder, which fails).

## Start here: the guide (`guide`)

1. **An old profile.** If `user.md` sits at the project root and
   `core_text/user.md` doesn't exist, say profiles now live in `core_text/`
   and offer to move it. Only on their yes:
   `mkdir core_text` if it's missing, then `mv user.md core_text/user.md`.
   If both exist, touch neither: the preload reads `core_text/user.md`.
2. **Render the guide:** `<python> "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" render "<project-dir>"`.
   It creates `core_text/setup.json` if absent and writes
   `core_text/setup-guide.html`.
3. **Offer to open it** in their browser, and only on their yes run `open`
   (macOS), `xdg-open` (Linux) or `start` (Windows) with
   `core_text/setup-guide.html`.
4. **Show the table of contents in chat:** per step, its title, minutes and
   whether it can wait.
5. **Ask: "How much time do you have?"** Then propose the steps that fit,
   adding up their `minutes`. `prerequisites` and `workspace` can't be
   skipped, so they always come first.
   Anything they don't reach stays `pending` and waits for "continue setup".
6. `set … guide done`.

## Continue setup

When the user says "continue setup", or the preload's `Setup:` line brought
them here, run `setup_record.py status "<project-dir>"`, which reads
`core_text/setup.json`. Resume at the first step that is `pending` or
`skipped`, in steps.json order. Name it and its minutes. For a skipped step,
give one line on what it gets them now; they can skip it again. If the
preload says `.cofounder/env` is missing, run step 1's `project_env.py` first.

## 1. Prerequisites (`prerequisites`) and an editor (`editor`)

Open with one question: "Mac or Windows PC?" (Linux counts too), and use
the matching commands from here on.

Check `git --version` and `<python>` (above). If either is missing, stop and
help install it: Python 3 from python.org (not the Microsoft Store) and, on
Windows, Git for Windows, which runs the hooks. Then create the environment
the `cofounder` MCP server runs on:

```
<python> "${CLAUDE_PLUGIN_ROOT}/bin/project_env.py" "<project-dir>"
```

`ENV_OK`: `<python>` is now `env`; the server connects after a Claude Code
restart. `ENV_FAIL`: keep the word that ran; the worklog and
verify tools wait for a fix.

Then check install scope: read `~/.claude/settings.json` — **never edit
it.** If `base-novacaelum@technical-cofounder` is enabled there, say in one
line that it is then the main agent in *every* project, and offer the two
commands that move it to this project; the user runs them, not you:

```
claude plugin uninstall base-novacaelum@technical-cofounder --scope user
claude plugin install base-novacaelum@technical-cofounder --scope project
```

`set … prerequisites done --choice os=mac|windows|linux --choice python=env|python3|python|py`.

### Editor

Markdown (`.md`) is the core file type here: profile, plans, worklog, rules
and skills. A user who can't open it goes quiet rather than asking.

Look first. On a Mac, `ls /Applications | grep -iE "obsidian|visual
studio code|typora|zed|sublime"`; on Windows, check `%LOCALAPPDATA%\Programs`.
If something is there, say which.

If nothing is, recommend one, a line each:

- **Obsidian** — free, our recommendation, and step 2 builds on it.
- **VS Code** or **Zed** — free, and code editors too.
- **Typora** — paid, the cleanest single-document view.
- **The fallback** — TextEdit (Mac) or Notepad (Windows) opens `.md` today
  as raw text. Say so: a user who thinks an app is required stalls.

They install it; offer the download page.
`set … editor done --choice editor=<obsidian|vscode|zed|typora|textedit|notepad|other>`,
or `skipped` if they want none.

## 2. Obsidian (`obsidian`)

If they have Obsidian or just chose it, yes is the easy call: a minimal
`.obsidian/` config (core Bases plugin only) and `worklog/worklog.base`, a
table over every worklog entry. If they don't use
Obsidian, don't sell it. `set … obsidian done --choice obsidian=yes`, or
`skipped --choice obsidian=no`. Step 4 uses this answer.

## 3. GitHub (`github`)

Optional, never blocking, and worth pitching: every change is backed up off
this computer and can be undone, and it's free.

Look first: `gh --version`, then `gh auth status`. If both succeed, say
they're connected, `set … github done --choice github=yes` and move on.

Otherwise ask whether to connect GitHub now. On a no, ask once:
"Are you sure? It's free, it's your project's backup off this computer, and
it takes about ten minutes." A second no is final:
`set … github skipped --choice github=no`, and continue.

On a yes, walk them through it. They run every command:

1. **An account:** a free one at github.com, if they don't have one.
2. **The GitHub CLI (`gh`):** `brew install gh` on macOS,
   `winget install --id GitHub.cli` on Windows (then open a new terminal
   window), or their Linux package manager (cli.github.com lists each).
3. **Log in:** `gh auth login`, choose GitHub.com, then a web browser. No
   token is needed; `gh` keeps its own login.

Confirm with `gh auth status`, then `set … github done --choice github=yes`.

## 4. The starter workspace (`workspace`)

The worklog view is `obsidian` if they said yes in step 2, otherwise `csv`
(the plain `worklog/worklog.csv` index). Run:

```
<python> "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project-dir>" --obsidian|--no-obsidian --no-super
```

`--no-super`: step 5 handles super. The script copies every template file
that isn't already there and refreshes the guide. Report every `COPIED:` and
`SKIPPED:` line it printed, and the `INIT_SUMMARY` line.

`set … workspace done --choice worklog_view=obsidian|csv`.

## 5. Super (`super`)

Explain in one line each:
- **base** (already running): four agents, guardrail hooks, the working
  loop and a local verifier. No accounts, no servers.
- **super** (`super-novacaelum`, opt-in): Context7 documentation lookup, Exa
  web search, the Browserbase cloud browser and step-by-step thinking, on the
  user's own keys. Context7 and Exa have usable free tiers, Browserbase needs
  a key to do anything, and `sequential-thinking` needs Node
  (`node --version`).

If they want super, run the `super-setup` skill: it walks through each
account, the project-scope install and entering keys through Claude Code's
hidden configure prompt. `set … super done --choice super=yes` once it
finishes, or `pending --choice super=yes` if they stop partway: the preload
then shows super as expected but missing. If they don't want it,
`set … super skipped --choice super=no`; agents then use
`reference/without-super.md`.

## 6. Your profile (`profile`)

`core_text/user.md` is their profile, copied in at step 4 (if they kept an
old `user.md` at the project root, that file is the profile instead). Ask one
question at a time, in this order:

1. What are you building, and what's your role on it?
2. What machine(s)/OS do you work from?
3. How do you want to signal when you're `sharp`, `steady` or `tired`, and
   how should the agent's shape change for each?
4. Do you want options presented, or a recommendation with the reasoning
   shown? How should uncertainty be flagged?
5. Timezone, and any batching or checkpoint preferences on long sessions?
6. Anything else that would change how an agent should work with you?

Write each answer into its section of the profile as you go, so nothing is
lost if the session ends. To change it later, they edit the file or run
`/base-novacaelum:onboard`. `set … profile done`.

## 7. What to try first (`first-steps`)

Close with three lines, concrete to this setup: one thing to ask the
default agent, one skill worth trying, and where the worklog lives (or the
`worklog.base` view, with Obsidian). `set … first-steps done`.
If anything is still `pending` or `skipped`, say that "continue setup" picks
it up any time.

Source: Nova Caelum (Apache-2.0).
