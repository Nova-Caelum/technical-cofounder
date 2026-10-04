To install Technical Cofounder, paste this one message into Claude Code:

```text
Set up Technical Cofounder for me, from https://github.com/Nova-Caelum/plugins
This message is for Claude Code. If you cannot run commands on this computer, for example because this is the Chat tab of the Claude desktop app, stop here and tell me to open the Code tab, click New session, choose Local, leave the folder empty, and paste this same message there.

1. If `claude --version` does not work here, install Claude Code's command line first (macOS or Linux: curl -fsSL https://claude.ai/install.sh | bash   Windows PowerShell: irm https://claude.ai/install.ps1 | iex). If `claude` is still not found after that, use its full path in the steps below: ~/.local/bin/claude on macOS or Linux, %USERPROFILE%\.local\bin\claude.exe on Windows.
   Once `claude --version` works, make sure Claude Code is version 2.1.110 or newer, both the command line (`claude --version`) and, if this session is in the Claude desktop app, the app's own copy (run the program named in the `CLAUDE_CODE_EXECPATH` environment variable with `--version`). If the command line is older, run `claude update`; if it is still older, run the install command above again and use its full path. If the app's copy is older, tell me to open Claude > Check for Updates on a Mac or Help > Check for Updates on Windows, then close the app, open it again and paste this same message.
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
