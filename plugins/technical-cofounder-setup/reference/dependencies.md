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
  - the `cofounder` worklog server, which gives your team its memory across sessions
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

- **Used by:** Hyperspace Engine (the working loop, the task graph and the check that closes each task), and the team's `cofounder` worklog server, which runs on this environment's Python.
- **Without it:** the loop can't run and the worklog tools don't appear.
- **Check:** the environment's Python runs and can load Hyperspace Engine.
- **Install:** run `/technical-cofounder-setup:start` inside the project. It rebuilds the workspace.

### Obsidian (optional)

Setup never installs Obsidian. It only looks for it, so it can offer the worklog view without asking you to look.

- **Used by:** the optional worklog view. Your worklog entries open as linked notes.
- **Without it:** nothing breaks. The worklog stays as plain files in `worklog/entries/`.
- **Check:** setup looks in the usual install places.
- **Install:** obsidian.md.
