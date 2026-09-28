---
name: setup
description: Use when a project needs setting up on this plugin or setup needs finishing — the user says "set up", "install", "get started", "onboard me" or "continue setup", or a session starts with no core_text/user.md.
---

# Setup

The only conversational surface for setting up a project.
`/base-novacaelum:setup` and `/base-novacaelum:onboard` point here.

What each step does, why it matters, whether it's safe to skip, what skipping
costs and how long it takes all live in `${CLAUDE_PLUGIN_ROOT}/setup/steps.json`.
Read it first. This skill says how to run each step.

Every step:
- Ask one question at a time, and wait for the answer.
- Never overwrite or delete a file. Move or copy a user's file only on their yes.
- Never ask for a key, token or password in the chat.
- After every step, record it, which also refreshes the guide:

  ```
  python3 "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" set "<project-dir>" <step-id> done|skipped|pending [--choice key=value]
  ```

  `done` when it happened, `skipped` when they chose to skip, `pending` to
  reopen. A step accepts only the choice keys steps.json declares for it, and
  a value is one plain word (`yes`, `no`, `vscode`, `csv`). The script refuses
  anything else, so free text never lands in `core_text/setup.json`.

## Start here: the guide (`guide`)

1. **An old profile.** If `user.md` sits at the project root and
   `core_text/user.md` doesn't exist, say profiles now live in `core_text/`
   and offer to move it. Only on their yes:
   `mkdir -p core_text && mv user.md core_text/user.md`. If both exist, touch
   neither, and say the session preload reads `core_text/user.md`.
2. **Render the guide:** `python3 "${CLAUDE_PLUGIN_ROOT}/bin/setup_record.py" render "<project-dir>"`.
   It creates `core_text/setup.json` if absent and writes
   `core_text/setup-guide.html`, one plain page listing every step.
3. **Offer to open it** in their browser, and only on their yes run `open`
   (macOS), `xdg-open` (Linux) or `start` (Windows) with
   `core_text/setup-guide.html`.
4. **Show the table of contents in chat:** one line per step with its title,
   its minutes, and whether it can wait.
5. **Ask: "How much time do you have?"** Then propose the steps that fit,
   adding up their `minutes`. `prerequisites` and `workspace` can't be
   skipped, so they always come first; offer to leave the rest for later.
   Anything they don't reach stays `pending` and waits for "continue setup".
6. `set … guide done`.

## Continue setup

When the user says "continue setup", or the preload's `Setup:` line brought
them here, run `setup_record.py status "<project-dir>"`, which reads
`core_text/setup.json`. Resume at the first step that is `pending` or
`skipped`, in steps.json order. Name it and its minutes. For a skipped step,
give one line on what it gets them now; they can skip it again.

## 1. Prerequisites (`prerequisites`) and an editor (`editor`)

Open with one question: "Mac or Windows PC?" (Linux counts too), and use
the matching commands from here on.

Check `python3` and `git` are on PATH (`python3 --version`, `git --version`).
If `python3` is missing, stop and help them install it first: the plugin's
tools and this record both need it.

Then check install scope. Read `~/.claude/settings.json` — **read only, never
edit it.** If `base-novacaelum@technical-cofounder` is enabled there at user
scope, say in one line that this makes it the main agent in *every* project
on the machine. Offer the two commands that move it to just this project;
the user runs them, not you:

```
claude plugin uninstall base-novacaelum@technical-cofounder --scope user
claude plugin install base-novacaelum@technical-cofounder --scope project
```

`set … prerequisites done --choice os=mac|windows|linux`.

### Editor

Markdown (`.md`) is the core file type here, not "notes": the profile,
plans, worklog, rules and skills are all Markdown. A user who can't open it
goes quiet rather than asking.

Look before asking. On a Mac, `ls /Applications | grep -iE "obsidian|visual
studio code|typora|zed|sublime"`; on Windows, check `%LOCALAPPDATA%\Programs`.
If something is there, say which and move on.

If nothing is, recommend one, a line each:

- **Obsidian** — free, our recommendation, and step 2 builds on it.
- **VS Code** or **Zed** — free, and code editors too.
- **Typora** — paid, the cleanest single-document view.
- **The fallback** — TextEdit (Mac) or Notepad (Windows) opens `.md` today
  as raw text, without formatting, links or search. Say so: a user who
  thinks a special app is required stalls on installing one.

They install it; offer the download page, don't install it for them.
`set … editor done --choice editor=<obsidian|vscode|zed|typora|textedit|notepad|other>`,
or `skipped` if they want none.

## 2. Obsidian (`obsidian`)

If they have Obsidian or just chose it, yes is the easy call: they get a
minimal `.obsidian/` config (the core Bases plugin, no community plugins) and
`worklog/worklog.base`, a table over every worklog entry. If they don't use
Obsidian, don't sell it. `set … obsidian done --choice obsidian=yes`, or
`skipped --choice obsidian=no`. Step 4 uses this answer.

On a **no**, say one line before moving on: the guide lives at
`${CLAUDE_PLUGIN_ROOT}/template/OBSIDIAN.md` if they ever change their mind.
Saying yes copies it into their project; saying no does not, so without that
pointer the person most likely to want it later is the one person who cannot
find it.

## 3. GitHub (`github`)

Optional, never blocking, and worth pitching: every change is backed up
off this computer and can be undone, which solves backups and lost files
for good, and it's free.

Look first: `gh --version`, then `gh auth status`. If both succeed, say
they're connected, `set … github done --choice github=yes` and move on.

Otherwise ask whether they want to connect GitHub now. On a no, ask once:
"Are you sure? It's free, it's your project's backup off this computer, and
it takes about ten minutes." A second no is final:
`set … github skipped --choice github=no`, and continue.

On a yes, walk them through it. They run every command:

1. **An account:** a free one at github.com, if they don't have one.
2. **The GitHub CLI (`gh`):** `brew install gh` on macOS,
   `winget install --id GitHub.cli` on Windows (then open a new terminal
   window), or their Linux package manager (cli.github.com lists each).
3. **Log in:** `gh auth login`, choose GitHub.com, then log in with a web
   browser. No token is needed; `gh` keeps its own login in the system's
   credential store.

Confirm with `gh auth status`, then `set … github done --choice github=yes`.

## 4. The starter workspace (`workspace`)

The worklog view is `obsidian` if they said yes in step 2, otherwise `csv`
(the plain `worklog/worklog.csv` index). Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/init_workspace.py" "<project-dir>" --obsidian|--no-obsidian --no-super
```

`--no-super`, because step 5 handles super itself. The script copies every
template file that isn't already there, skips the rest and refreshes the
guide. Report what it printed: every `COPIED:` and `SKIPPED:` line, and the
`INIT_SUMMARY` line.

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

If they want super, run the `super-setup` skill. It asks whether they've used
an API key before and where they keep passwords, then walks through each
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

After each answer, write it into the matching section of the profile,
replacing the placeholder, so nothing is lost if the session ends. Setup never
overwrites it again: to change it later, they edit the file or run
`/base-novacaelum:onboard`. `set … profile done`.

## 7. What to try first (`first-steps`)

Close with three lines, concrete to what was just set up: one thing to ask
the default agent, one skill worth trying, and where the worklog lives (or
the `worklog.base` view, if they chose Obsidian). `set … first-steps done`.
If anything is still `pending` or `skipped`, say that "continue setup" picks
it up any time.

Source: Nova Caelum (Apache-2.0).
