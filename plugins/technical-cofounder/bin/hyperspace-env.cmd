@echo off
rem hyperspace-env.cmd: start this project's Hyperspace environment
rem (.hyperspace\env) only after launch_env.py, beside this file, has checked
rem that setup built it on this computer. Claude Code runs this file on Windows
rem when .mcp.json names bin/hyperspace-env; the file without .cmd does the
rem same on macOS and Linux.
rem
rem Source: Nova Caelum (2026). License: MIT.
rem
rem The check runs on this computer's own Python, never one inside the project:
rem the first of these that starts (each is tried once, with nothing to read):
rem   %USERPROFILE%\.local\bin\python3.13.exe, python3.12.exe, python3.11.exe
rem   py -3
rem   python3, python
rem Each is found by its full path, never by a bare name: a bare name would
rem also find a program in the current folder, which is the project.
rem Then that Python runs launch_env.py (isolated, -I) with run, --, and the
rem arguments given here, and its exit code is this file's exit code.

setlocal EnableExtensions DisableDelayedExpansion
set "NC_PROJECT=%CLAUDE_PROJECT_DIR%"
if not defined NC_PROJECT set "NC_PROJECT=%CD%"
set "NC_PROJECT=%NC_PROJECT:/=\%"
if "%NC_PROJECT:~-1%"=="\" set "NC_PROJECT=%NC_PROJECT:~0,-1%"
set "NC_PY="

for %%V in (13 12 11) do if not defined NC_PY call :try "%USERPROFILE%\.local\bin\python3.%%V.exe"
for %%N in (py.exe) do if not defined NC_PY if not "%%~$PATH:N"=="" call :try "%%~$PATH:N" -3
for %%N in (python3.exe python.exe) do if not defined NC_PY if not "%%~$PATH:N"=="" call :try "%%~$PATH:N"

if not defined NC_PY goto none
%NC_PY% -I "%~dp0launch_env.py" run -- %*
exit /b %errorlevel%

:none
echo No Python was found on this computer, so Hyperspace could not start. Run /technical-cofounder-setup:start to install one. 1>&2
exit /b 1

rem The first argument is a Python (the second, -3, is for the py launcher).
rem It is used when it is a file outside the project and it starts.
:try
set "NC_CANDIDATE=%~1"
if not exist "%NC_CANDIDATE%" exit /b 0
call set "NC_REST=%%NC_CANDIDATE:*%NC_PROJECT%\=%%"
if not "%NC_REST%"=="%NC_CANDIDATE%" exit /b 0
"%NC_CANDIDATE%" %~2 -S -c "" <nul >nul 2>&1
if not "%errorlevel%"=="0" exit /b 0
set NC_PY="%NC_CANDIDATE%" %~2
exit /b 0
