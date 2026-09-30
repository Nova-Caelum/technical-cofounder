# What gets installed, and why

Technical Cofounder runs on a few free tools. This page lists each one:
- **Why:** the line Claude says before installing it.
- **Used by:** what in the plugin depends on it.
- **Without it:** what stops working.
- **Check:** how setup tests for it.
- **Install:** how to add it by hand.

Setup installs only what's missing and skips anything you already have.

## At a glance

| Tool | Needed on | Why (what Claude tells you) |
|---|---|---|
| Claude Code (command line) | Mac and Windows | Installing Claude Code's command line so your team can be installed and updated reliably. |
| Git for Windows | Windows only | Installing Git because you're on Windows: it gives your team the command line its safety checks run in. |
| Git | Mac | Installing Git so your team can tell exactly what changed in your project. |
| Python 3 | Mac and Windows | Installing Python so your team's memory and safety checks can run. |
| jq | Mac and Windows (recommended) | Installing jq so your team's guardrails can read what's happening in a session. |
| Node.js | Only with the super plugin | Installing Node.js so the super plugin's step-by-step thinking tool can start. |
| Obsidian | Optional | Installing Obsidian so you can browse your team's worklog as linked notes. |

## Each tool in detail

### Claude Code (command line)

- **Used by:** installing and updating plugins (`claude plugin marketplace add`, `claude plugin install`).
- **Without it:** you depend on the desktop app's plugin screen, which currently has known bugs. It doesn't list plugins you haven't installed yet ([anthropics/claude-code#89984](https://github.com/anthropics/claude-code/issues/89984)), and on Windows plugin skills may not load ([#64763](https://github.com/anthropics/claude-code/issues/64763)). The command line installs the same plugins reliably. You can keep working in the desktop app afterwards.
- **Check:** `claude --version` prints a version.
- **Install:**
  - Mac: `curl -fsSL https://claude.ai/install.sh | bash`
  - Windows PowerShell: `irm https://claude.ai/install.ps1 | iex`
  - Then open a new terminal window.

### Git for Windows (Windows only)

- **Used by:** every plugin hook, meaning the session-start briefing and the guardrails. Claude Code runs them in Git Bash, the command line that comes with Git for Windows. It also provides `git` itself.
- **Without it:** Claude Code runs commands in PowerShell instead ([Claude Code setup docs](https://code.claude.com/docs/en/setup)). The plugin's hooks are bash scripts, so they can't run the way they were written. *Unverified:* exactly what you see when that happens; our Windows test covers it.
- **Check:** `git --version` prints a version, and Claude Code can find Git Bash.
- **Install:** `winget install Git.Git`, accepting the defaults, then restart Claude Code.

### Git (Mac)

- **Used by:** the verifier's "something actually changed" check (`git status`). Downloading plugins from GitHub may also use it (*unverified*).
- **Without it:** the verifier can't confirm that a change happened, so those checks come back uncertain rather than passed.
- **Check:** `git --version` prints a version. On a new Mac, the first `git` offers to install Apple's Command Line Tools. Accept it.
- **Install:** run `xcode-select --install`, or accept the prompt the first time you run `git`.

### Python 3

- **Used by:**
  - the `cofounder` worklog server, which gives your team its memory across sessions
  - the session-start briefing (`hooks/session-preload.sh`)
  - the setup scripts
  - `/base-novacaelum:contact`
  - the verifier and the working-loop gates
- **Without it:**
  - the worklog tools don't appear
  - sessions start without your context (the briefing prints `plugin stack unavailable: python3 could not run`)
  - setup can't finish
- **Check:** `python3 --version` must print a real version. On Windows, a Microsoft Store placeholder answers to `python3` without being Python. That doesn't count.
- **Install:**
  - Mac: `xcode-select --install`, or python.org.
  - Windows: python.org → *Python Install Manager*, then check `python3 --version` in a new window. If the Microsoft Store opens instead, click Start, open *Manage app execution aliases*, and turn on the *Python (default)* aliases.

### jq

- **Used by:** the guardrail hooks:
  - the circuit breaker, which stops Claude repeating a failing action
  - the concision hooks, which keep answers to a sensible length
- **Without it:** those hooks switch themselves off quietly for that session, by design, so a missing tool never blocks your work. Everything else runs, but the guardrails are off.
- **Check:** `jq --version` prints a version. On Windows, check inside Git Bash. *Unverified:* whether Git for Windows includes jq.
- **Install:**
  - Mac: `brew install jq`
  - Windows: `winget install jqlang.jq`

### Node.js (super plugin only)

- **Used by:** the super plugin's sequential-thinking server, which runs through `npx`.
- **Without it:** that one tool fails to connect. The super plugin's other tools and the whole base plugin still work.
- **Check:** `node --version` prints a version.
- **Install:**
  - Mac: `brew install node`
  - Windows: `winget install OpenJS.NodeJS.LTS`
  - Any OS: nodejs.org (the LTS version)

### Obsidian (optional)

- **Used by:** the optional worklog view. Your worklog entries open as linked notes.
- **Without it:** nothing breaks. The worklog stays as plain files in `worklog/entries/`.
- **Check:** chosen during setup.
- **Install:** obsidian.md.

## Coming in a later version

These aren't used yet. They're listed so this page stays the single reference as setup changes.

- **uv:** installs Python for you, without admin rights and without the Microsoft Store trap. Why: "Installing uv so Python can be set up for you without admin rights."
- **Hyperspace Engine:** the full working loop, with a task graph, a closure verifier and a browser console. It will install alongside the base plugin and needs Python 3.11 or newer. Why: "Installing the Hyperspace Engine so every task is checked before it's called done."
