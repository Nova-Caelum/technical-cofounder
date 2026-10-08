---
name: setup
description: Use when Technical Cofounder needs setting up, finishing or repairing on this computer — the user says "set me up", "set up", "get started", "install", "onboard me", "continue setup", "start another project", "something is broken with my setup", "turn on the judge" or "turn off the judge", or pasted the install message that says to read this file.
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
- Every choice you ask them to make ends with one more option, **Explain the
  difference**: what they gain or lose with each. When they pick it, say the
  step's `explain` lines from `steps.json` for the options in front of them,
  then ask the same question again. A step with no `explain` lines is
  explained from its `does`, `why` and `if_skipped`.
- Plain words. Define a term the first time you use it: "a plugin (an add-on
  for Claude Code)".
- Never ask for a key, token or password in chat.
- Never overwrite or delete a file. Move or copy a user's file only on their
  yes.
- Say early: "If anything is unclear, just ask me." Say it again at the end.

## Where the project goes

1. Ask what they want to call the project.
2. Offer where it will live, and let them change it: a folder with that name
   in `Projects` inside their home folder, on every system. Not Documents:
   on Windows that is usually a OneDrive folder, and a workspace with
   thousands of files does badly under sync. A folder they already have is
   fine too. If the folder they choose has `OneDrive` in its path, say once
   that synced folders slow the workspace down and offer the `Projects`
   default again; their choice stands. Offer **Explain the difference** too:
   the `prerequisites` step's `explain` lines.
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

   Run it with a ten-minute timeout on the tool call. A shell call is cut off
   after two minutes unless you ask for longer, and a first Python download
   can take longer than that on a slow connection. A call that ends with no
   `BOOTSTRAP=` last line was cut off, not failed: run the same command
   again.
3. Act on that line:
   - `BOOTSTRAP=OK python=<path>`: keep the path. It is `<python>` in every
     command below. On Windows it comes with forward slashes: use it as
     printed, always inside double quotes.
   - `BOOTSTRAP=NEEDS_RESTART`: tell the user exactly what to do: close Claude
     Code completely, open it again, and paste the same message. If they
     started Claude Code from a terminal window, they close that window too.
     Then stop.
   - `BOOTSTRAP=NEEDS_YOU reason=...`: say the one thing they need to do, in
     plain words, and wait. When they say it is done, run the first step again.

## Scan, plan, apply, re-scan

The install script has five verbs. Each prints one JSON document. Read it;
never guess what it says.

```
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" plan --project "<project>"
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" apply --project "<project>" --item <id>
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" ack --project "<project>" --item <id>
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" scan --project "<project>" --record
"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" judge --project "<project>" --set claude-code|none
```

Run every `apply` with a ten-minute timeout on the tool call. A shell call is
cut off after two minutes unless you ask for longer, and building the engine's
workspace can take longer than that on a slow connection. A call that ends
with no JSON document was cut off, not failed: run the same command again.

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
     and opened again, and the same message pasted. If they started Claude
     Code from a terminal window, they close that window too. Then stop.
   - **`engine-env` when its verdict is `install`** (the first build) comes
     with a question. Before you run it, say the `judge` line of the
     `engine-env` entry in `steps.json` and ask: Judge on / No judge /
     **Explain the difference** (that entry's `explain` lines). On No judge,
     first run
     `"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" judge --project "<project>" --set none`;
     the build keeps that choice. Then run `apply` as above. Its document
     carries a `judge` object: say its `detail`. When its `why` is
     `not-signed-in` or `no-answer`, offer to fix it now: they run
     `claude auth login` in their own terminal window (Terminal on a Mac,
     PowerShell on Windows), which opens a browser page to sign in. When they
     say it is done, run
     `"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" judge --project "<project>" --set claude-code`
     and say its `detail`.
4. **Finish.** Run `scan` with `--record` and say what it shows: how many
   items are `ready`, anything that is not, and where the record is
   (`recorded`). A row that is not `ready` goes back through step 3. Then say
   the `prerequisites` step's `verify` line from `steps.json`, so they can
   check it themselves.

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

When an `apply` or `judge` document carried a judge, add the last one you
saw: `--choice judge=<judge> --choice judge_why=<why>`.

## The guide and the questions

The guide is two pages in `<project>/core_text/`. Part 1 takes about 20
minutes, and the install above was the first part of it. Part 2 is the
optional extras and waits for later.

Every step below:

- Before you start it, say its title, its `why` and its `minutes` from the
  `steps` list in `steps.json`.
- End with its `verify` line from `steps.json`, the one place they can check
  it themselves, then one line: they can ask you anything about it, right in
  the chat.
- Work on `<project>` by its absolute path.
- Record it afterwards, which also refreshes the guide:

  ```
  "<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project>" <step-id> done|skipped|pending [--choice key=value]
  ```

  `done` when it happened, `skipped` when they chose to skip, `pending` to
  reopen. A step takes only the choice keys `steps.json` declares for it, each
  one plain word (`yes`, `no`, `vscode`, `files`); the script refuses anything
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
   guide first: wait until they have read it / Explain the difference) and
   "How much time do you have?". Say: Part 1 takes about 20 minutes and the
   install is already behind them. Part 2 (research extras) is optional and
   lives in `setup-extras.html`, at the absolute `EXTRAS:` path. Steps they don't
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
and move on. If nothing is, recommend one, with **Explain the difference** as
the last option:

- **Obsidian**: free, our recommendation, and the next step builds on it.
- **VS Code** or **Zed**: free. **Typora**: paid, the cleanest view.
- **The fallback**: TextEdit (Mac) or Notepad (Windows) opens `.md` today as
  raw text, without formatting, links or search. Say so: nobody needs a
  special app to finish setup.

They install it; offer the download page (https://obsidian.md/download for
Obsidian). If they pick Obsidian, say: "Great:
everything you need is in OBSIDIAN.md (<absolute path>), or you can just ask
me." The path is `<project>/OBSIDIAN.md` if it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md`.
`set … editor done --choice editor=<obsidian|vscode|zed|typora|textedit|notepad|other>`
(a fallback counts as done, never `skipped`).

### 2. Obsidian (`obsidian`)

This is also the worklog choice, so say first, in one sentence, what the
worklog is: the team's diary, one short Markdown file per piece of work in
`worklog/`, so the next session knows what happened. Everyone gets those files
and reads them in the worklog tab of Hyperspace Engine's console; with
Obsidian they also show as one table.

Pitch Obsidian in one line, to everyone: "Obsidian is free, it keeps everything
on your computer, and it reads every file in this project." When the plan's
`obsidian` row says it is not installed, add the download page,
https://obsidian.md/download. Then ask Yes / No / **Explain the difference**.
A yes gets a minimal `.obsidian/` folder and `worklog/worklog.base`, that table
over every worklog entry.

Offer OBSIDIAN.md without being asked, on either answer: "There's a short guide
to Obsidian for this project, OBSIDIAN.md. Want me to open it?" Its path is
`<project>/OBSIDIAN.md` once step 4 has run, and until then
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md` (give the absolute path). On a no,
add that "continue setup" switches them over later.

**Viewers (a yes only).** Obsidian opens Markdown and PDFs on its own. Word,
PowerPoint, SQLite, JSON and HTML files each need a small add-on, a community
plugin: code written by other people, which runs inside Obsidian with
Obsidian's access to their files. So offer only the ones on setup's own list,
each read-only and at a version we checked. Nothing is copied from us: each
file comes from its author's GitHub page and must match the checked copy.

1. `"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/obsidian_plugins.py" list` prints
   them, each with a `name` and a `for` line.
2. Ask about each one, one at a time, with its `name` and `for` line: Yes / No /
   **Explain the difference**. A viewer is optional; with No those files keep
   opening in their own apps. Install a plugin only after a yes to that
   plugin, in their own words: a yes to Obsidian is not a yes to a plugin.
   Never install one that is not on that list.
3. On a yes, run
   `"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/obsidian_plugins.py" install --project "<project>" --plugin <id>`
   and say its `detail`. When its `result` is `failed`, say the `detail`:
   nothing was left half-installed, so offer to try again.
4. When any are installed, say what Obsidian will ask. They choose "Open
   folder as vault" and pick the project folder, and Obsidian asks "Do you
   trust the author of this vault?" with two buttons: **Trust author and
   enable plugins** and "Browse vault in Restricted Mode". They choose Trust
   author and enable plugins, because they said yes to each one. If they chose
   Restricted Mode, or a viewer does nothing: Settings → Community plugins →
   **Turn on community plugins**. Say that the HTML viewer opens pages with its
   scripts off, and that they leave that switch off for any page they did not
   write.

The theme is a pointer, not a download: Settings → Appearance → Themes →
Manage, then Minimal (free, made for reading) → Use.

Then `set … obsidian done --choice obsidian=yes`, or, on a no,
`skipped --choice obsidian=no`. Step 4 uses this answer.

### 3. GitHub (`github`)

Optional, never blocking, and worth offering: every change is backed up off
this computer and can be undone, and it is free.

Look first: `gh --version`, then `gh auth status`. If both succeed, they are
connected: `set … github done --choice github=yes` and move on.

Otherwise ask whether they want to connect GitHub now (Yes / Not now /
**Explain the difference**). On a no, ask once:
"Are you sure? It's free, and it's your project's backup off this computer."
A second no is final: `set … github skipped --choice github=no`, and continue.

On a yes, walk them through it. They run every command:

1. **An account:** a free one at github.com, if they don't have one.
2. **The GitHub command line (`gh`):** `winget install --id GitHub.cli` on
   Windows, or their Linux package manager (cli.github.com lists each). A
   terminal window opened before the install can't find it: they open a new
   one. On a Mac it comes through Homebrew, a free app installer for the Mac,
   so read the plan's `homebrew` row first; its `detail` is the answer:
   - **Homebrew is not installed** (or it **does not run**): say so, and that
     GitHub is optional, so they can get Homebrew now or leave GitHub for
     later. If they want it now, they run this in Terminal:
     `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`.
     It explains what it will do and waits for Enter. Then it asks for their
     Mac password: nothing shows as they type, and that is normal. No password
     goes in the chat. It takes a few minutes and ends with a "Next steps"
     section: they run the commands it lists, then open a new Terminal window.
     `brew --version` printing a version means it worked. Then run `plan`
     again and read the `homebrew` row: the re-scan decides, not their word.
   - **Homebrew at <path>**: it is there. In Terminal they run
     `brew install gh`.
3. **Log in:** in a terminal window (Terminal on a Mac, PowerShell on
   Windows), `gh auth login`. It asks four questions; give them every answer
   before they start. Arrow keys move, Enter picks.
   1. "Where do you use GitHub?" **GitHub.com**
   2. "What is your preferred protocol for Git operations on this host?"
      **HTTPS**
   3. "Authenticate Git with your GitHub credentials?" **Yes**
   4. "How would you like to authenticate GitHub CLI?" **Login with a web
      browser**

   Then it prints a one-time code, like `ABCD-1234`: they copy it, press
   Enter, paste it on the page that opens (github.com/login/device), and
   authorize GitHub CLI. No token or password goes in the chat.

**`gh` on Windows, just installed.** This session's PATH was fixed when Claude
Code started, so a `gh` installed since is not found here even though it
works. Don't ask for a restart: look for
`C:\Program Files\GitHub CLI\gh.exe`, and if it is there, use that full path,
in double quotes, for every `gh` command you run yourself (or put its folder
first on PATH for your own commands). The terminal window they open for step 3
finds `gh` by name.

**`gh` on a Mac, just installed.** Homebrew puts it in `/opt/homebrew/bin`
(Apple Silicon) or `/usr/local/bin` (Intel), and this session's PATH may
predate that. For every `gh` command you run yourself, use
`/opt/homebrew/bin/gh` or `/usr/local/bin/gh`, whichever exists, in double
quotes. The terminal window they open for step 3 finds `gh` by name.

Confirm with `gh auth status` (by its full path on Windows or a Mac, as above), then
`set … github done --choice github=yes`.

### 4. The starter workspace (`workspace`)

The worklog view is `obsidian` if they said yes in step 2, otherwise `files`:
the worklog's Markdown files in `worklog/`, read in the worklog tab of
Hyperspace Engine's console. Nothing is asked here. Run:

```
"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project>" --obsidian|--no-obsidian --no-super
```

`--no-super`, because Part 2 handles the extras. The script copies every
starter file that is not already there and refreshes the guide. Report what
it printed: every `COPIED:` and `SKIPPED:` line, and the `INIT_SUMMARY` line.

`set … workspace done --choice worklog_view=obsidian|files`.

### 5. What to try first (`first-steps`)

Say plainly first: no run is open yet in a new project, and the first step of
any piece of work is Understand. They say what they want; the team works out
the real problem and what "done" means before anything is built. Then three
lines for their first session in the project: one thing to ask the technical
cofounder, one skill worth trying, and where the worklog lives (`worklog/`,
and `worklog.base` if they chose Obsidian). `set … first-steps done`.

### 6. Their profile (`profile`)

`<project>/core_text/user.md` is their profile, copied in at step 4 (an old
`<project>/user.md` is the profile instead). It already holds two defaults,
so don't ask about them: `steady` is the working mode until they say
otherwise, and agents give options with a recommendation and a short why, and
say plainly when uncertain. Ask one question at a time, in this order, each
choice with **Explain the difference** as its last option:

1. Offer a test drive: they don't need to know what they're building yet. In
   their first session they pick something small, and the team takes it from
   Understand to done, so they see how it works. If they already know what
   they're building, ask what it is and their role on it instead.
2. What machine(s) do you work from?
3. Do you use Claude Code's desktop app or the command line (CLI), or both?
   Ask it: an agent can't tell from inside a session, and the steps it gives
   depend on it.
4. Timezone, and any batching or checkpoint preferences?
5. Anything else that would change how an agent should work with you?

After each answer, write it into the matching section, replacing the
placeholder; a test drive goes in as "not decided yet: starting with a test
drive". They can change it later by editing the file.
`set … profile done`.

## Closing

1. Thank them for setting up. Keep it short.
2. Say where Part 2 lives, by absolute path: "Setup part 2 (extras) is here:
   <the `EXTRAS:` path>". Name what it adds, one line each: web research with
   sources (Exa); live library docs, today's documentation for the tools
   their project uses (Context7); and a cloud browser for pages that need
   clicks or a login (Browserbase).
3. Give the one next action: "Open Claude Code in `<absolute project path>`.
   Your technical cofounder will be there." Then how, for the app their
   profile names (both if it names neither):
   - Desktop app: the Code tab, then new session, then choose the project
     folder, `<absolute project path>`.
   - Command line (CLI): `cd` into `<absolute project path>`, then run
     `claude`.
4. The first time Claude Code opens that folder it asks whether they trust it
   (it may read "Is this a project you created or one you trust?"). Say what
   that means: Claude Code is asking whether the settings saved in this
   folder may take effect, and here they are the team's. It is their own
   project, so they choose to trust this folder (the option reads something
   like "Yes, I trust this folder").
5. Say where work starts: no run is open yet, and the first step of any piece
   of work is Understand. If they chose a test drive, that is where they
   start.
6. If a restart is required, say that this new session is that restart:
   nothing else needs closing or reopening.
7. Say it once more: "If anything is unclear, just ask me."

## Repair and another project

When the user runs `/technical-cofounder-setup:start` later, look at where
this session is running:

- **Inside a project that was set up** (the current folder has
  `core_text/setup-scan.json`, or `core_text/setup.json` from an earlier
  setup): `<project>` is the current folder. Run the
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

**Turn the judge on or off.** When they say "turn on the judge" or "turn
off the judge": `<project>` is the current folder; get `<python>` from the
**First step**, then run
`"<python>" "${CLAUDE_PLUGIN_ROOT}/installer/nc_setup.py" judge --project "<project>" --set claude-code`
(`--set none` turns it off) and say its `detail`. A `why` of
`not-signed-in` or `no-answer` gets the same offer as at the first build:
`claude auth login` in their own terminal window, then try again. Record
what it printed:
`"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project>" prerequisites done --choice judge=<judge> --choice judge_why=<why>`.
The next task that closes uses the new setting; nothing needs restarting.

**Obsidian later.** Someone who said no at step 2 and uses Obsidian now moves
over without moving anything: their worklog is already Markdown files in
`worklog/`. Run
`"<python>" "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project>" --obsidian --no-super`
(it adds `.obsidian/`, `worklog/worklog.base` and `OBSIDIAN.md`, and never
overwrites a file), offer the viewers exactly as in step 2
(`obsidian_plugins.py list`), then `set … obsidian done --choice obsidian=yes` and
`set … workspace done --choice worklog_view=obsidian`. In Obsidian they choose
"Open folder as vault" and pick the project folder.

## Part 2: the extras (`super`)

Part 2 runs from inside the project, in a later session: the skill that does
it, `super-setup`, belongs to the team, which is installed there. If this
session is somewhere else, say so, and that "set up the extras" starts it
once they are in the project.

Explain super in one line per service. `super-novacaelum` (opt-in) adds, on
the user's own accounts:

- **Web research** with sources (Exa): agents search the web and cite what
  they found.
- **Live library docs** (Context7): today's documentation for the libraries
  and tools their project uses, instead of what a model remembers.
- **A cloud browser** (Browserbase): for pages that need clicks, a login or
  JavaScript.

Context7 and Exa have free tiers, and a key only raises their limits;
Browserbase needs a key, and its free plan includes one browser hour a month.
Ask Yes / Not now / **Explain the difference**.

If they want it, run the team's `super-setup` skill: it walks through each
account, the project-scope install and entering keys through Claude Code's
hidden configure prompt. `set … super done --choice super=yes` once it
finishes, or `pending --choice super=yes` if they stop partway. If they don't
want it, `set … super skipped --choice super=no`.

Source: Nova Caelum (Apache-2.0).
