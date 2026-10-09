# What gets installed, and why

Technical Cofounder runs on a few free tools. This page lists each one:
- **Why:** the line Claude says before installing or checking it.
- **Used by:** what depends on it.
- **Without it:** what stops working.
- **Check:** how setup tests for it.
- **Install:** how to add it by hand.

Setup installs only what's missing and skips anything you already have. Each "why" below is the line in `setup/steps.json`, word for word; a test fails when this page and that file disagree.

## At a glance

| Tool | Setup item | Needed on | Why (what Claude tells you) |
|---|---|---|---|
| Claude Code (command line) | `claude-cli` | Mac and Windows | Installing Claude Code's command line so your team can be installed and updated reliably. |
| Git for Windows | `git` | Windows only | Installing Git because you're on Windows: it gives your team the command line its safety checks run in. |
| Git | `git` | Mac | Installing Git so your team can tell exactly what changed in your project. |
| uv | `uv` | Mac and Windows | Installing uv, a small tool that fetches the right Python for your team without touching the one your computer came with. |
| Python | `python` | Mac and Windows | Installing Python so your team's memory and safety checks can run. |
| jq | `jq` | Mac and Windows | Installing jq so your team's guardrails can read what's happening in a session. |
| Hyperspace Engine's workspace | `engine-env` | Mac and Windows | Building Hyperspace Engine's private workspace, where your task graph and its checks run. |
| Obsidian | `obsidian` | Optional | Checking whether Obsidian is installed, so setup can offer it without asking you to look. |
| Homebrew | `homebrew` | Mac only | Checking whether Homebrew is installed, so setup can show you the easy way to add GitHub's command line on a Mac. |

Technical Cofounder itself needs no Node.js. A project of your own may need it; the engineer installs it when a project actually needs it.

## Each tool in detail

### Claude Code (command line)

- **Used by:** installing and updating plugins (`claude plugin marketplace add`, `claude plugin install`).
- **Without it:** you depend on the desktop app's plugin screen, which currently has known bugs. It doesn't list plugins you haven't installed yet ([anthropics/claude-code#89984](https://github.com/anthropics/claude-code/issues/89984)), and on Windows plugin skills may not load ([#64763](https://github.com/anthropics/claude-code/issues/64763)). The command line installs the same plugins reliably. You can keep working in the desktop app afterwards.
- **Check:** `claude --version` prints a version. Setup looks on your PATH and in the per-user folder the installer writes to.
- **Install:**
  - Mac: `curl -fsSL https://claude.ai/install.sh | bash`
  - Windows PowerShell: `irm https://claude.ai/install.ps1 | iex`
  - Then open a new terminal window.

### Git for Windows (Windows only)

- **Used by:** every plugin hook, meaning the session-start briefing and the guardrails. Claude Code runs them in Git Bash, the command line that comes with Git for Windows. It also provides `git` itself.
- **Without it:** Claude Code runs commands in PowerShell instead ([Claude Code setup docs](https://code.claude.com/docs/en/setup)). The plugin's hooks are bash scripts, so they can't run the way they were written. *Unverified:* exactly what you see when that happens; our Windows test covers it.
- **Check:** `git --version` prints a version, and Git's own Git Bash sits beside it.
- **Install:** `winget install --id Git.Git -e --source winget`, accepting the defaults, then close Claude Code completely and open it again.

### Git (Mac)

- **Used by:** your team and Hyperspace Engine, to tell exactly what changed in your project. Downloading plugins from GitHub may also use it (*unverified*).
- **Without it:** nothing can confirm what a change touched. Setup stops and asks you to install it.
- **Check:** `git --version` prints a version. On a new Mac, Git comes with Apple's Command Line Tools; setup asks you to install them if they are missing.
- **Install:** run `xcode-select --install` and accept the window that opens.

### uv

- **Used by:** setup's first step, which has uv fetch Python, and the build of Hyperspace Engine's workspace.
- **Without it:** setup can't fetch Python, so nothing after the first step runs.
- **Check:** `uv --version` prints a version. Setup looks on your PATH and in the per-user folder the installer writes to.
- **Install:**
  - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows PowerShell: `irm https://astral.sh/uv/install.ps1 | iex`

### Python 3.11 or newer

Python is installed for you: setup's first step has uv fetch Python 3.12 into uv's own folder, with no admin rights, and proves it by running it. The Python that came with your computer isn't used and isn't changed.

- **Used by:**
  - the `caelum-dev-team` worklog server, which gives your team its memory across sessions
  - the session-start briefing (`hooks/session-preload.sh`)
  - the setup scripts
  - `/technical-cofounder:contact`
  - Hyperspace Engine, which runs the working loop and checks each task before it is called done
- **Without it:**
  - the worklog tools don't appear
  - sessions start without your context (the briefing prints `plugin stack unavailable: python3 could not run`)
  - setup can't finish
- **Check:** setup runs the interpreter and has it load the modules it needs. A `python3` that is already on the computer doesn't count: it may be years old, and on Windows a Microsoft Store placeholder answers to `python3` without being Python.
- **Install:** `uv python install 3.12`.

### jq

- **Used by:** the guardrail hooks:
  - the circuit breaker, which stops Claude repeating a failing action
  - the concision hooks, which keep answers to a sensible length
- **Without it:** those hooks switch themselves off for that session, by design, so a missing tool never blocks your work. Everything else runs, but the guardrails are off.
- **Check:** `jq --version` prints a version. Setup looks on your PATH and in the per-user folder it downloads jq to.
- **Install:** setup downloads the official build from jq's releases on GitHub. By hand:
  - Mac: `brew install jq`
  - Windows: `winget install jqlang.jq`

### Hyperspace Engine's workspace

Hyperspace Engine arrives with your team: it is the team plugin's dependency, so one install brings both. Its workspace is a private Python environment inside your project, at `.hyperspace/env`, built by the engine's own setup script.

- **Used by:** Hyperspace Engine (the working loop, the task graph and the check that closes each task), and the team's `caelum-dev-team` worklog server, which runs on this environment's Python.
- **Without it:** the loop can't run and the worklog tools don't appear.
- **Check:** the environment's Python runs and can load Hyperspace Engine.
- **Install:** run `/technical-cofounder-setup:start` inside the project. It rebuilds the workspace.

### Obsidian (optional)

Setup never installs Obsidian. It only looks for it, so it can offer the worklog view without asking you to look.

- **Used by:** the optional worklog view. Your worklog entries open as linked notes.
- **Without it:** nothing breaks. The worklog stays as plain files in `worklog/entries/`.
- **Check:** setup looks in the usual install places.
- **Install:** obsidian.md.

### Homebrew (Mac only, optional)

Homebrew is a free app installer for the Mac. Setup never installs it: its installer asks for your Mac password in Terminal, so setup tells you how and waits.

- **Used by:** the optional GitHub step. On a Mac, `brew install gh` is the way GitHub's own docs recommend for adding its command line ([GitHub CLI on macOS](https://github.com/cli/cli/blob/trunk/docs/install_macos.md)).
- **Without it:** nothing in setup stops. You can't run `brew install gh`, so connecting GitHub waits until you install Homebrew; GitHub is optional.
- **Check:** `brew --version` prints a version. Setup looks on your PATH and in the two places Homebrew's installer puts it (`/opt/homebrew/bin` on Apple Silicon, `/usr/local/bin` on Intel), because a session that started before Homebrew was installed doesn't have them on its PATH.
- **Install:** paste this in Terminal (it is the command on [brew.sh](https://brew.sh)):
  - `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
  - It explains what it will do and waits for Enter, then asks for your Mac password (nothing shows as you type) and takes a few minutes.
  - It ends with a "Next steps" section: run the commands it lists, open a new Terminal window, and `brew --version` prints a version.
  - Homebrew supports macOS 15 (Sequoia) or newer; an older Mac may still work but is unsupported ([Homebrew installation docs](https://docs.brew.sh/Installation)).

## Research extras (optional, part 2)

Part 2 of setup offers `super-novacaelum`, an opt-in plugin that gives your agents three services, each on your own account. Nothing in part 1 needs them.

| Service | What it buys | Account and key |
|---|---|---|
| Exa | Web research with sources: agents search the web and cite what they found. | Free tier. A key is optional and raises your limit (dashboard.exa.ai). |
| Context7 | Live library docs: today's documentation for the libraries and tools your project uses, instead of what a model remembers. | Free tier. A key is optional and raises your limit (context7.com/dashboard). |
| Browserbase | A cloud browser for pages that need clicks, a login or JavaScript. | Needs a key. The free plan includes one browser hour a month ([pricing](https://www.browserbase.com/pricing)). |

- **Install:** in a session inside your project, say "set up the extras". The team's `super-setup` skill walks through each account, installs the plugin for this project only, and has you enter each key in Claude Code's own hidden prompt, never in the chat.
- **Check:** in a session in your project, type `/mcp`: context7, exa and browserbase are listed, marked as coming from a plugin.
- **Without them:** agents use Claude Code's built-in web search and web fetch, and anything that needs a real browser comes back to you.

## Staying current (a check every two weeks)

Once every 14 days, at the start of a session, your team looks up whether the tools above have a newer version. If one does, Claude tells you in plain words and gives you the one command that updates it, and runs it only if you say yes. If nothing is out of date, you are offline, or it checked recently, you see nothing.

- **Checked:** Claude Code (only if it will not update itself: automatic updates are switched off, or it came from Homebrew or WinGet), uv, jq, GitHub's command line (`gh`), and Git for Windows. A tool counts as out of date when a newer minor version exists (Claude Code, which only numbers its builds: seven or more releases behind); a patch alone is not worth a message.
- **Never checked:** anything your computer's system owns, such as Apple's Git on a Mac, because it updates with macOS. Homebrew, which updates itself. Python, which uv fetched and keeps current. jq that setup downloaded for you, which has no safe one-line update.
- **Cost:** a few hundred milliseconds, once a fortnight, with a hard stop at a few seconds; no network means no check and no message. It looks versions up with `curl` on GitHub's public pages and on Claude Code's download site; each is an ordinary web request with nothing from your project in it.
- **Where it keeps its place:** `cli-freshness.json` in the team plugin's data folder (`~/.claude/plugins/data/`, in the folder named for the team plugin), with the time of the last check and the last try. Delete it to be checked at your next session.
- **Switch it off:** set `TC_CLI_FRESHNESS=off` in your environment.
