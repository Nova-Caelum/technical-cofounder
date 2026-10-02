---
name: setup
description: Use when Technical Cofounder needs setting up, finishing or repairing on this computer — the user says "set me up", "set up", "get started", "install", "onboard me", "continue setup", "start another project" or "something is broken with my setup", or pasted the install message that says to read this file.
---

# Setup

If `${CLAUDE_PLUGIN_ROOT}` is not set, the plugin root is the folder two levels above this file; use that absolute path wherever this skill says `${CLAUDE_PLUGIN_ROOT}`.
That folder holds `skills/`, `installer/`, `setup/` and `bin/`. If a real path
already stands where that name was, Claude Code filled it in and there is
nothing to do.

This is the one conversation that sets Technical Cofounder up. In one session
it installs what this computer is missing, creates the project folder with the
team in it, walks the setup guide, and hands over to the team.

Two things are not yours to decide:

- **What this computer needs.** The install script decides. You say what it is
  about to do, run it, and report what it found. You never work out a verdict
  yourself.
- **Why, and how long.** Every reason and every time is in
  `${CLAUDE_PLUGIN_ROOT}/setup/steps.json`: `install` has one entry for each
  item the script can plan, `steps` one for each step of the guide. Say them
  as written. Never make one up.

Came here through `/technical-cofounder-setup:start` in a later session, or to
continue or repair? Read **Repair and another project** first.

## How to talk

- One question at a time, and wait for the answer. Ask a multiple-choice
  question with the `AskUserQuestion` tool when it is available (it shows a
  pop-up), otherwise in chat.
- Plain words. Define a term the first time you use it: "a plugin (an add-on
  for Claude Code)".
- Never ask for a key, token or password in chat.
- Never overwrite or delete a file. Move or copy a user's file only on their
  yes.
- Say early: "If anything is unclear, just ask me." Say it again at the end.

## Where the project goes

1. Ask what they want to call the project.
2. Offer where it will live, and let them change it: a folder with that name
   in their Documents folder on Windows, or in `Projects` inside their home
   folder on a Mac or Linux. A folder they already have is fine too.
3. Create nothing yet. The install script creates the folder. It refuses the
   home folder itself and system folders; when it does, say its sentence and
   ask for another folder.

From here on, `<project>` is that folder's absolute path. Every command below
takes it in full, because this session is not running inside it.

## First step

The install script needs a Python that works, and the one that came with the
computer may be too old or missing. The first step is one script that fetches
one, and changes only what is missing.

1. Read `${CLAUDE_PLUGIN_ROOT}/setup/steps.json`. From its `install` list, say
   the `why` and the `minutes` of `uv` and of `python`. On Windows, say `git`
   first, with its `why_windows`.
2. Run the script for this system and read the last line it prints:
   - Mac or Linux, `installer/bootstrap.sh`:
     `bash "${CLAUDE_PLUGIN_ROOT}/installer/bootstrap.sh"`
   - Windows, `installer/bootstrap.ps1`, through PowerShell, with the path in
     Windows form (`C:\...`):
     `powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}\installer\bootstrap.ps1"`
3. Act on that line:
   - `BOOTSTRAP=OK python=<path>`: keep the path. It is `<python>` in every
     command below.
   - `BOOTSTRAP=NEEDS_RESTART`: tell the user exactly what to do: close Claude
     Code completely, open it again, and paste the same message. Then stop.
   - `BOOTSTRAP=NEEDS_YOU reason=...`: say the one thing they need to do, in
     plain words, and wait. When they say it is done, run the first step again.

## Scan, plan, apply, re-scan

The install script has four verbs. Each prints one JSON document. Read it;
never guess what it says.

```
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" plan --project "<project>"
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" apply --project "<project>" --item <id>
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" ack --project "<project>" --item <id>
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" scan --project "<project>" --record
```

1. **Plan.** Run `plan`. Every row in `items` has an `id`, a `verdict`, a
   `detail`, a `why` and `minutes`. The verdict is one of `ready`, `install`,
   `upgrade`, `repair`, `needs-you` and `needs-restart`.
2. **Say the plan** in two sentences: what is already fine, and what will be
   installed, with the total minutes (add up `minutes` for the rows that are
   not `ready`).
3. **Walk the rows that are not `ready`, in the plan's order.** One step at a
   time. For each row:
   - `install`, `upgrade` or `repair`: Say the reason and the time before you
     run the step. The reason is the row's `why`, as written; the time is its
     `minutes`. Then run `apply` for that one `id` and report the verdict in
     `results[0].after`:
     - `ready`: say it is done. When `acted` is false it was already there;
       say that instead.
     - anything else: say its `detail` in plain words and stop there, because
       the rows after it wait on this one. Offer to try that step again.
   - `needs-you`: the `detail` is the question, or the one thing to do. For
     `existing-config`, ask its question; on a yes, run `ack` for it; on a no,
     go back to **Where the project goes**. For any other row, say it and
     wait; when they have done it, run `plan` again and carry on from that
     row. If the detail says to run the first-step script, go back to
     **First step**.
   - `needs-restart`: explain that Claude Code has to be closed completely
     and opened again, and the same message pasted. Then stop.
4. **Finish.** Run `scan` with `--record` and say what it shows: how many
   items are `ready`, anything that is not, and where the record is
   (`recorded`). A row that is not `ready` goes back through step 3.

What makes this trustworthy:

- The re-scan is the only source of "done". `apply` checks the item again
  after it acts, and `after` is that second check. A command that printed
  success proves nothing. Never tell the user something is installed until the
  script's verdict says `ready`.
- Never run a step the plan did not ask for, and never install anything by
  another route.
- Never skip the re-check, and never decide a verdict yourself.

A restart is required when any `apply` printed `"restart_required": true`, or
when the record file, `<project>/core_text/setup-scan.json`, says so. Read
the file: a later `scan` prints its own answer and leaves the file's alone.
Remember it for the closing.

When every row is `ready`, record it (`macos` in the plan's `platform` is
`mac` here):

```
"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project>" prerequisites done --choice os=mac|windows|linux
```

## The guide and the questions

The guide is two pages in `<project>/core_text/`. Part 1 takes about 20
minutes, and the install above was the first part of it. Part 2 is the
optional extras and waits for later.

Every step below:

- Before you start it, say its title, its `why` and its `minutes` from the
  `steps` list in `steps.json`.
- End with one line: they can ask you anything about it, right in the chat.
- Work on `<project>` by its absolute path.
- Record it afterwards, which also refreshes the guide:

  ```
  "<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project>" <step-id> done|skipped|pending [--choice key=value]
  ```

  `done` when it happened, `skipped` when they chose to skip, `pending` to
  reopen. A step takes only the choice keys `steps.json` declares for it, each
  one plain word (`yes`, `no`, `vscode`, `csv`); the script refuses anything
  else. When a step is skipped, say its `if_skipped` line, so they know what
  they are leaving for later. `skipped` writes that line into
  `core_text/setup.json`, where the team's session briefing reads it.

### Open the guide (`guide`)

1. **An old profile.** If `<project>/user.md` exists and
   `<project>/core_text/user.md` does not, say profiles now live in
   `core_text/` and offer to move it. Move it only on their yes. If both
   exist, touch neither.
2. **Render the guide:**
   `"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" render "<project>"`.
   It writes the two pages and prints `GUIDE: <absolute path>` and
   `EXTRAS: <absolute path>`. Keep both.
3. **Open the guide as a page, never as text.** Straight away, with no yes
   needed, run `open` (Mac), `start ""` (Windows) or `xdg-open` (Linux) on the
   `GUIDE:` path. Never print the HTML in the chat. If the command fails or
   there is no desktop, say "You can view the setup guide here:" and the
   absolute `GUIDE:` path.
4. **Quick questions**, as pop-ups: "Ready for the rest?" (Yes / Show me the
   guide first: wait until they have read it) and "How much time do you
   have?". Say: Part 1 takes about 20 minutes and the install is already
   behind them. Part 2 (research extras) is optional and lives in
   `setup-extras.html`, at the absolute `EXTRAS:` path. Steps they don't
   reach stay `pending` for "continue setup".
5. `set … guide done`.

### 1. Where they read Markdown (`editor`)

Markdown (`.md`) is the core file type here: the profile, plans, worklog,
rules and skills are all Markdown. Required: every user picks an app, and
TextEdit or Notepad counts.

Look before asking. The plan's `obsidian` row already says whether Obsidian
is installed. For the others: on a Mac,
`ls /Applications | grep -iE "visual studio code|typora|zed|sublime"`; on
Windows, look in `%LOCALAPPDATA%\Programs`. If something is there, say which
and move on. If nothing is, recommend one:

- **Obsidian**: free, our recommendation, and the next step builds on it.
- **VS Code** or **Zed**: free. **Typora**: paid, the cleanest view.
- **The fallback**: TextEdit (Mac) or Notepad (Windows) opens `.md` today as
  raw text, without formatting, links or search. Say so: nobody needs a
  special app to finish setup.

They install it; offer the download page. If they pick Obsidian, say: "Great:
everything you need is in OBSIDIAN.md (<absolute path>), or you can just ask
me." The path is `<project>/OBSIDIAN.md` if it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md`.
`set … editor done --choice editor=<obsidian|vscode|zed|typora|textedit|notepad|other>`
(a fallback counts as done, never `skipped`).

### 2. Obsidian (`obsidian`)

If they have Obsidian or just chose it, yes is the easy call: they get a
minimal `.obsidian/` folder and `worklog/worklog.base`, a table over every
worklog entry. If they don't use Obsidian, don't sell it.
`set … obsidian done --choice obsidian=yes`, or
`skipped --choice obsidian=no`. Step 4 uses this answer.

On a no, say one line: OBSIDIAN.md is at
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md` (give the absolute path) if they
change their mind.

### 3. GitHub (`github`)

Optional, never blocking, and worth offering: every change is backed up off
this computer and can be undone, and it is free.

Look first: `gh --version`, then `gh auth status`. If both succeed, they are
connected: `set … github done --choice github=yes` and move on.

Otherwise ask whether they want to connect GitHub now. On a no, ask once:
"Are you sure? It's free, and it's your project's backup off this computer."
A second no is final: `set … github skipped --choice github=no`, and continue.

On a yes, walk them through it. They run every command:

1. **An account:** a free one at github.com, if they don't have one.
2. **The GitHub command line (`gh`):** `brew install gh` on a Mac,
   `winget install --id GitHub.cli` on Windows (then a new terminal window),
   or their Linux package manager (cli.github.com lists each).
3. **Log in:** `gh auth login`, choose GitHub.com, then log in with a web
   browser. No token is needed.

Confirm with `gh auth status`, then `set … github done --choice github=yes`.

### 4. The starter workspace (`workspace`)

The worklog view is `obsidian` if they said yes in step 2, otherwise `csv`
(the plain `worklog/worklog.csv` index). Run:

```
"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project>" --obsidian|--no-obsidian --no-super
```

`--no-super`, because Part 2 handles the extras. The script copies every
starter file that is not already there and refreshes the guide. Report what
it printed: every `COPIED:` and `SKIPPED:` line, and the `INIT_SUMMARY` line.

`set … workspace done --choice worklog_view=obsidian|csv`.

### 5. What to try first (`first-steps`)

Three lines for their first session in the project: one thing to ask the
technical cofounder, one skill worth trying, and where the worklog lives (or
`worklog.base`, if they chose Obsidian). `set … first-steps done`.

### 6. Their profile (`profile`)

`<project>/core_text/user.md` is their profile, copied in at step 4 (an old
`<project>/user.md` is the profile instead). Ask one question at a time, in
this order:

1. What are you building, and what's your role on it?
2. What machine(s) do you work from?
3. How do you signal when you're `sharp`, `steady` or `tired`, and how should
   the agent's shape change for each?
4. Options presented, or a recommendation with reasoning? How should
   uncertainty be flagged?
5. Timezone, and any batching or checkpoint preferences?
6. Anything else that would change how an agent should work with you?

After each answer, write it into the matching section, replacing the
placeholder. They can change it later by editing the file.
`set … profile done`.

## Closing

1. Thank them for setting up. Keep it short.
2. Say where Part 2 lives, by absolute path: "Setup part 2 (extras) is here:
   <the `EXTRAS:` path>".
3. Give the one next action: "Open Claude Code in `<absolute project path>`.
   Your technical cofounder will be there."
4. If a restart is required, say that this new session is that restart:
   nothing else needs closing or reopening.
5. Say it once more: "If anything is unclear, just ask me."

## Repair and another project

When the user runs `/technical-cofounder-setup:start` later, look at where
this session is running:

- **Inside a project that was set up** (the current folder has
  `core_text/setup-scan.json`): `<project>` is the current folder. Run the
  **First step** again to get `<python>` (it is quick when everything is
  there), then `plan`, and fix what is not `ready` with the same protocol,
  ending with `scan --record`. If everything is `ready`, say so, then offer to
  continue setup if the guide has steps left.
- **Somewhere else:** ask whether they want a new project. On a yes, start
  from **Where the project goes**. "Start another project" is the same, from
  anywhere.

**Continue setup.** `<project>` is the current folder when it has
`core_text/setup.json`; otherwise ask which project. In a new session, get
`<python>` from the **First step**. Then run
`"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" status "<project>"`
and resume the guide at the first step that is `pending` or `skipped`, in
`steps.json` order. Name it and its minutes. For a skipped step, give one line
on what it gets them now.

## Part 2: the extras (`super`)

Part 2 runs from inside the project, in a later session: the skill that does
it, `super-setup`, belongs to the team, which is installed there. If this
session is somewhere else, say so, and that "set up the extras" starts it
once they are in the project.

Explain super in one line: `super-novacaelum` (opt-in) adds Context7
documentation lookup, Exa web search and the Browserbase cloud browser, on
the user's own keys. Context7 and Exa have free tiers; Browserbase needs a
key.

If they want it, run the team's `super-setup` skill: it walks through each
account, the project-scope install and entering keys through Claude Code's
hidden configure prompt. `set … super done --choice super=yes` once it
finishes, or `pending --choice super=yes` if they stop partway. If they don't
want it, `set … super skipped --choice super=no`.

Source: Nova Caelum (Apache-2.0).
