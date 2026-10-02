To install Technical Cofounder, paste this one message into Claude Code:

```text
Set up Technical Cofounder for me, from https://github.com/Nova-Caelum/plugins

1. If `claude --version` does not work here, install Claude Code's command line first (macOS or Linux: curl -fsSL https://claude.ai/install.sh | bash   Windows PowerShell: irm https://claude.ai/install.ps1 | iex).
2. If I am on Windows and `git --version` does not work, run this in PowerShell, then tell me to close Claude Code completely, open it again and paste this same message:
   winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
3. Run these two commands:
   claude plugin marketplace add Nova-Caelum/plugins
   claude plugin install technical-cofounder-setup@nova-caelum
4. Run `claude plugin list --json`, find the installPath of technical-cofounder-setup, read skills/setup/SKILL.md inside it, and follow it from the top. Tell me what each step is for before you run it, and go one step at a time.
```
