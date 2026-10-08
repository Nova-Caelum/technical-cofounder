Type this into Claude Code (in the desktop app, the Code tab, not Chat) and press Enter. If it asks where to install, choose Install for you (user scope):

```text
/plugin install technical-cofounder-setup --marketplace Nova-Caelum/plugins
```

Then paste this message. If the command showed an error (Git missing, an unknown command, or Claude Code older than 2.1.275), paste it anyway: it fixes what is missing.

```text
Set up Technical Cofounder for me. I want you to install these plugins from Nova Caelum's catalog at https://github.com/Nova-Caelum/plugins, which I trust: technical-cofounder-setup now, then technical-cofounder (my team; it brings hyperspace-engine with it), and super-novacaelum only if I say yes to the research extras.
Claude Code may ask me to approve a command or press Run. That is expected; I will.
This message is for Claude Code. If you cannot run commands here (for example, this is the Chat tab of the Claude desktop app), stop and tell me to open the Code tab, click New session, choose Local, leave the folder empty, and paste this message there.

1. Claude Code: `claude --version` must work and be 2.1.110 or newer. In the Claude desktop app, also check the app's own copy (the program named in the CLAUDE_CODE_EXECPATH environment variable, run with --version). Missing or older command line: run `claude update`, or install it (macOS or Linux: curl -fsSL https://claude.ai/install.sh | bash; Windows PowerShell: irm https://claude.ai/install.ps1 | iex), and use ~/.local/bin/claude or %USERPROFILE%\.local\bin\claude.exe if `claude` is still not found. Older app: tell me to choose Claude > Check for Updates on a Mac or Help > Check for Updates on Windows, reopen the app, and paste this message again.
2. Git must be installed before anything downloads. Mac: if `xcode-select -p` fails, run `xcode-select --install`, tell me to click Install, and tell you when it is done; then carry on. Windows: if `git --version` fails, look for C:\Program Files\Git\cmd\git.exe or %LOCALAPPDATA%\Programs\Git\cmd\git.exe; if neither exists, run `winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements` (no winget: tell me to install it from https://git-scm.com/downloads/win). Whether you just installed it or found it there, tell me to close Claude Code completely (and its terminal window, if I used one), reopen it, and paste this message again; if I say I already did, put that Git's cmd folder on PATH for your own commands and carry on.
3. If technical-cofounder-setup is not installed yet, install it: `claude plugin marketplace add https://github.com/Nova-Caelum/plugins.git`, then `claude plugin install technical-cofounder-setup@nova-caelum`.
4. Run `claude plugin list --json`, find the installPath of technical-cofounder-setup, read skills/setup/SKILL.md inside it, and follow it from the top, one step at a time. Tell me what each step is for before you run it.
```
