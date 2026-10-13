@echo off
rem team-server.cmd: start the team's worklog server (mcp\server.py) through
rem hyperspace-env.cmd, beside this file. Claude Code runs this file on Windows
rem when .mcp.json names bin/team-server; the file without .cmd does the same
rem on macOS and Linux.
rem
rem Source: Nova Caelum (2026). License: MIT.

call "%~dp0hyperspace-env.cmd" "%~dp0..\mcp\server.py" %*
exit /b %errorlevel%
