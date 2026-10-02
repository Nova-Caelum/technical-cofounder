To install Technical Cofounder, paste this one message into Claude Code:

```text
Set up Technical Cofounder for me, from https://github.com/Nova-Caelum/plugins

1. If `claude --version` does not work here, install Claude Code's command line first (macOS or Linux: curl -fsSL https://claude.ai/install.sh | bash   Windows PowerShell: irm https://claude.ai/install.ps1 | iex). If `claude` is still not found after that, use its full path in the steps below: ~/.local/bin/claude on macOS or Linux, %USERPROFILE%\.local\bin\claude.exe on Windows.
2. Git has to be on this computer before anything can be downloaded. Check it first:
   - On a Mac, if `xcode-select -p` fails: run `xcode-select --install`, tell me to click Install in the window that opens and to tell you when it has finished, then carry on from step 3.
   - On Windows, if `git --version` does not work: look for C:\Program Files\Git\cmd\git.exe and %LOCALAPPDATA%\Programs\Git\cmd\git.exe. If neither is there, run this in PowerShell:
   winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
     If winget is not found, tell me to download the installer from https://git-scm.com/downloads/win and run it with its default choices.
     Then, or if one of those two files was already there, tell me to close Claude Code completely, open it again and paste this same message. If I started Claude Code from a terminal window, I have to close that window too. If I tell you I already did that, put that Git's cmd folder on PATH for your own commands and carry on from step 3.
3. Run these two commands:
   claude plugin marketplace add https://github.com/Nova-Caelum/plugins.git
   claude plugin install technical-cofounder-setup@nova-caelum
4. Run `claude plugin list --json`, find the installPath of technical-cofounder-setup, read skills/setup/SKILL.md inside it, and follow it from the top. Tell me what each step is for before you run it, and go one step at a time.
```
