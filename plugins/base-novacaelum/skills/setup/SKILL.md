---
name: setup
description: Use when a project needs setting up on this plugin or setup needs finishing — the user says "set up", "install", "get started", "onboard me" or "continue setup", or a session starts with no core_text/user.md.
---

# Setup

The only conversational surface for setting up a project.
`/base-novacaelum:quick-start` and `/base-novacaelum:onboard` point here.

What each step does, why, whether it can be skipped and how long it takes
live in `${CLAUDE_PLUGIN_ROOT}/setup/steps.json`. Read it first. This skill
says how to run each step.

Every step:
- Ask one question at a time, and wait for the answer. Ask every multiple-choice
  question with the `AskUserQuestion` tool when it is available (it shows a
  pop-up), otherwise in chat.
- End with one line: they can ask you anything about it, right in the chat.
- Never overwrite or delete a file. Move or copy a user's file only on their yes.
- Never ask for a key, token or password in the chat.
- After every step, record it, which also refreshes the guide:

  ```
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project-dir>" <step-id> done|skipped|pending [--choice key=value]
  ```

  `done` when it happened, `skipped` when they chose to skip, `pending` to
  reopen. A step accepts only the choice keys steps.json declares, each one
  plain word (`yes`, `no`, `vscode`, `csv`); the script refuses anything else.

## Start here: the guide (`guide`)

1. **An old profile.** If `user.md` sits at the project root and
   `core_text/user.md` doesn't exist, say profiles now live in `core_text/`
   and offer to move it; only on their yes:
   `mkdir -p core_text && mv user.md core_text/user.md`. If both exist, touch
   neither.
2. **Render the guide:** `python3 "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" render "<project-dir>"`.
   It creates `core_text/setup.json` if absent, writes the two pages and
   prints `GUIDE: <absolute path>` and `EXTRAS: <absolute path>`.
3. **Open the guide as a page, never as text.** Straight away, no yes needed,
   run `open` (macOS), `start ""` (Windows) or `xdg-open` (Linux) on the
   `GUIDE:` path. Never print the HTML in the chat. If the command fails or
   there is no desktop, say "You can view the setup guide here:" and the
   absolute `GUIDE:` path.
4. **Quick questions**, as pop-ups: "Ready to start?" (Yes / Show me the
   guide first: wait until they've read it), "Mac or Windows PC?" (Linux
   counts too) and "How much time do you have?". Say: Part 1 takes about 20
   minutes. Part 2 (research extras) is optional and lives in
   `setup-extras.html`, at the absolute `EXTRAS:` path. Steps they don't reach
   stay `pending` for "continue setup".
5. `set … guide done`.

## Continue setup

When the user says "continue setup", or the preload's `Setup:` line brought
them here, run `setup_record.py status "<project-dir>"`. Resume at the first
step that is `pending` or `skipped`, in steps.json order. Name it and its
minutes. For a skipped step, give one line on what it gets them now.

## 1. Prerequisites (`prerequisites`) and an editor (`editor`)

Use the commands for the computer they named. Check `python3` and `git` are on
PATH (`python3 --version`, `git --version`). If `python3` is missing, stop and
help them install it first.
On Windows that means Python from python.org (the Python Install Manager). If
`python3` opens the Microsoft Store instead, have them open "Manage app execution
aliases" and turn off the `python.exe`/`python3.exe` Store aliases, leaving the
install manager's "Python (default)" aliases on.

Then check install scope. Read `~/.claude/settings.json` — **read only, never
edit it.** If `base-novacaelum@technical-cofounder` is enabled there at user
scope, say in one line that this makes it the main agent in *every* project.
Offer the two commands that move it to just this project; the user runs them:

```
claude plugin uninstall base-novacaelum@technical-cofounder --scope user
claude plugin install base-novacaelum@technical-cofounder --scope project
```

`set … prerequisites done --choice os=mac|windows|linux`.

### Editor

Markdown (`.md`) is the core file type here: the profile, plans, worklog,
rules and skills are all Markdown. Required: every user picks an app, and
TextEdit or Notepad counts.

Look before asking. On a Mac, `ls /Applications | grep -iE "obsidian|visual
studio code|typora|zed|sublime"`; on Windows, check `%LOCALAPPDATA%\Programs`.
If something is there, say which and move on. If nothing is, recommend one:

- **Obsidian** — free, our recommendation, and step 2 builds on it.
- **VS Code** or **Zed** — free. **Typora** — paid, the cleanest view.
- **The fallback** — TextEdit (Mac) or Notepad (Windows) opens `.md` today
  as raw text, without formatting, links or search. Say so: nobody needs a
  special app to finish setup.

They install it; offer the download page. If they pick Obsidian, say: "Great: everything you need is in OBSIDIAN.md
(<absolute path>), or you can just ask me." The path is the project's
`OBSIDIAN.md` if it exists, else `${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md`.
`set … editor done --choice editor=<obsidian|vscode|zed|typora|textedit|notepad|other>`
(a fallback counts as done, never `skipped`).

## 2. Obsidian (`obsidian`)

If they have Obsidian or just chose it, yes is the easy call: they get a
minimal `.obsidian/` config and `worklog/worklog.base`, a table over every
worklog entry. If they don't use Obsidian, don't sell it. `set … obsidian done --choice obsidian=yes`, or
`skipped --choice obsidian=no`. Step 4 uses this answer.

On a **no**, say one line: OBSIDIAN.md lives at
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md` (absolute path) if they change
their mind.

## 3. GitHub (`github`)

Optional, never blocking, and worth pitching: every change is backed up
off this computer and can be undone, and it's free. About 5 minutes with an
account, longer without.

Look first: `gh --version`, then `gh auth status`. If both succeed, they're
connected: `set … github done --choice github=yes` and move on.

Otherwise ask whether they want to connect GitHub now. On a no, ask once:
"Are you sure? It's free, and it's your project's backup off this computer."
A second no is final: `set … github skipped --choice github=no`, and continue.

On a yes, walk them through it. They run every command:

1. **An account:** a free one at github.com, if they don't have one.
2. **The GitHub CLI (`gh`):** `brew install gh` on macOS,
   `winget install --id GitHub.cli` on Windows (then open a new terminal
   window), or their Linux package manager (cli.github.com lists each).
3. **Log in:** `gh auth login`, choose GitHub.com, then log in with a web
   browser. No token is needed.

Confirm with `gh auth status`, then `set … github done --choice github=yes`.

## 4. The starter workspace (`workspace`)

The worklog view is `obsidian` if they said yes in step 2, otherwise `csv`
(the plain `worklog/worklog.csv` index). Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project-dir>" --obsidian|--no-obsidian --no-super
```

`--no-super`, because Part 2 handles super itself. The script copies every
template file that isn't already there and refreshes the guide. Report what it
printed: every `COPIED:` and `SKIPPED:` line, and the `INIT_SUMMARY` line.

`set … workspace done --choice worklog_view=obsidian|csv`.

## 5. What to try first (`first-steps`)

Three lines, concrete to what was just set up: one thing to ask the default
agent, one skill worth trying, and where the worklog lives (or `worklog.base`,
if they chose Obsidian). `set … first-steps done`.

## 6. Your profile (`profile`)

`core_text/user.md` is their profile, copied in at step 4 (an old root
`user.md` is the profile instead). Ask one question at a time, in this order:

1. What are you building, and what's your role on it?
2. What machine(s)/OS do you work from?
3. How do you signal when you're `sharp`, `steady` or `tired`, and how should
   the agent's shape change for each?
4. Options presented, or a recommendation with reasoning? How should
   uncertainty be flagged?
5. Timezone, and any batching or checkpoint preferences?
6. Anything else that would change how an agent should work with you?

After each answer, write it into the matching section, replacing the
placeholder. They can change it later by editing the file. `set … profile done`.

## Closing

Thank them for setting up. Point to Part 2 with the absolute `EXTRAS:` path
("Setup part 2 (extras) is here: <path>"); "set up the extras" starts it, and
"continue setup" picks up anything `pending` or `skipped`. Say once more that
they can ask you anything, in the chat.

## Part 2: the extras (`super`)

Reached by "continue setup" once Part 1 is done, or straight away on "set up
the extras". Explain in one line each:
- **base** (already running): four agents, guardrail hooks, the working
  loop and a local verifier. No accounts.
- **super** (`super-novacaelum`, opt-in): Context7 documentation lookup, Exa
  web search, the Browserbase cloud browser and step-by-step thinking, on the
  user's own keys. Context7 and Exa have free tiers, Browserbase needs a key,
  and `sequential-thinking` needs Node (`node --version`).

If they want super, run the `super-setup` skill: it walks through each
account, the project-scope install and entering keys through Claude Code's
hidden configure prompt. `set … super done --choice super=yes` once it
finishes, or `pending --choice super=yes` if they stop partway. If they don't want it,
`set … super skipped --choice super=no`; agents then use
`reference/without-super.md`.

Source: Nova Caelum (Apache-2.0).
