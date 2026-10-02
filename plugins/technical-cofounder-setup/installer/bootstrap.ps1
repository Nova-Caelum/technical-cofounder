# First step of Technical Cofounder setup on Windows.
#
# It does only what cannot wait for Python:
#   1. installs Git for Windows if it is missing (then asks for a restart)
#   2. installs uv if it is missing
#   3. has uv fetch Python 3.12
#   4. proves that Python by running it
# then hands over to nc_setup.py, passing along the arguments it was given.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap.ps1 [-DryRun] [nc_setup.py arguments...]
#
# Progress lines start with "bootstrap:". The last line this script prints is
# always exactly one of:
#   BOOTSTRAP=OK python=<absolute path>
#   BOOTSTRAP=NEEDS_RESTART reason=<text>      (exit 4)
#   BOOTSTRAP=NEEDS_YOU reason=<text>          (exit 3)
# After OK, whatever nc_setup.py prints follows.
#
# -DryRun prints each decision it would take and changes nothing.
#
# Written for Windows PowerShell 5.1, the one every Windows 11 has. Keep this
# file plain ASCII and free of anything newer.
param([switch]$DryRun)

# Read and print UTF-8. Without this, a Windows account name with an accent
# in it arrives garbled in the Python path, both from uv and in the last line.
# A session with no console has no encoding to set, and must not fail on it.
try {
    $OutputEncoding = New-Object System.Text.UTF8Encoding $false
    [Console]::OutputEncoding = $OutputEncoding
} catch { }

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$SetupArgs = @($args)

$WingetGit = 'winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements'
$UvInstall = 'irm https://astral.sh/uv/install.ps1 | iex'
$Proof = 'import sys, tomllib, sqlite3, venv; print(sys.version)'
# A Claude Code started from a terminal window keeps that window's old PATH,
# so every sentence that asks for a restart says to close the window too.
$RestartAfterInstall = 'Git was installed. Close Claude Code completely, open it again, and paste the same message. If you started Claude Code from a terminal window, close that window too.'
$RestartStaleSession = 'Git is installed, but this session started before it was. Close Claude Code completely, open it again, and paste the same message. If you started Claude Code from a terminal window, close that window too.'
$GitByHand = 'Git could not be installed automatically. Download and run the installer from https://git-scm.com/downloads/win, then close Claude Code completely, open it again, and paste the same message. If you started Claude Code from a terminal window, close that window too.'

function Say([string]$Text) {
    Write-Host "bootstrap: $Text"
}

function Stop-NeedsYou([string]$Reason) {
    Write-Output "BOOTSTRAP=NEEDS_YOU reason=$Reason"
    exit 3
}

function Stop-NeedsRestart([string]$Reason) {
    Write-Output "BOOTSTRAP=NEEDS_RESTART reason=$Reason"
    exit 4
}

function Find-App([string]$Name) {
    $found = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.Path }
    return $null
}

# Windows ships its own bash.exe that is not Git Bash.
function Test-WindowsStandIn([string]$Path) {
    return ($Path -match '\\Windows\\System32\\') -or ($Path -match '\\WindowsApps\\')
}

# Git's own bash.exe: beside git.exe the way Git for Windows lays itself out
# (which is how Claude Code finds it), or on PATH and not Windows' stand-in.
# By default Git for Windows puts only Git\cmd on PATH, so a "bash" that
# resolves to the stand-in says nothing about Git.
function Find-GitBash([string]$Git) {
    $folder = Split-Path -Parent $Git
    foreach ($step in 1..3) {
        if (-not $folder) { break }
        $candidate = Join-Path $folder 'bin\bash.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        $folder = Split-Path -Parent $folder
    }
    $bash = Find-App 'bash'
    if ($bash -and -not (Test-WindowsStandIn $bash)) { return $bash }
    return $null
}

# A Git for Windows in one of the places its installer uses, whether or not
# this session's PATH knows about it.
function Find-InstalledGit {
    $roots = @($env:ProgramFiles, $env:ProgramW6432, ${env:ProgramFiles(x86)})
    if ($env:LOCALAPPDATA) { $roots += (Join-Path $env:LOCALAPPDATA 'Programs') }
    foreach ($root in $roots) {
        if (-not $root) { continue }
        $candidate = Join-Path $root 'Git\cmd\git.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

# The PATH new programs will get, which a running session does not see.
# NC_PERSISTED_PATH stands in for it in tests.
function Get-PersistedPath {
    if ($null -ne $env:NC_PERSISTED_PATH) { return $env:NC_PERSISTED_PATH }
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    return "$machine;$user"
}

function Test-OnPersistedPath([string]$Folder) {
    foreach ($entry in (Get-PersistedPath).Split(';')) {
        if ($entry.Trim().TrimEnd('\') -ieq $Folder.TrimEnd('\')) { return $true }
    }
    return $false
}

# Returns $true when a Git for Windows exists afterwards. An installer's own
# word is not proof; looking for git.exe is.
function Install-Git {
    $winget = Find-App 'winget'
    if ($winget) {
        Say "running: $WingetGit"
        & $winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements | Out-Host
        if (Find-InstalledGit) { return $true }
        Say "winget did not leave a working Git (exit $LASTEXITCODE); trying the installer from GitHub"
    } else {
        Say 'winget is missing; downloading the Git for Windows installer instead'
    }
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $release = Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'nc-setup' } -ErrorAction Stop
        $asset = $release.assets | Where-Object { $_.name -match '^Git-[0-9.]+-64-bit\.exe$' } | Select-Object -First 1
        if (-not $asset) { throw 'the latest release has no 64-bit installer' }
        $installer = Join-Path $env:TEMP $asset.name
        Say "downloading $($asset.browser_download_url)"
        Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $installer -ErrorAction Stop
        $switches = @('/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS')
        $process = Start-Process -FilePath $installer -ArgumentList $switches -Wait -PassThru -ErrorAction Stop
        Say "the Git installer finished (exit $($process.ExitCode))"
    } catch {
        Say "the Git installer could not be downloaded or run: $($_.Exception.Message)"
    }
    return [bool](Find-InstalledGit)
}

function Find-Uv {
    $uv = Find-App 'uv'
    if ($uv) { return $uv }
    $folders = @($env:XDG_BIN_HOME)
    if ($env:USERPROFILE) { $folders += (Join-Path $env:USERPROFILE '.local\bin') }
    foreach ($folder in $folders) {
        if (-not $folder) { continue }
        $candidate = Join-Path $folder 'uv.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

# -- 1. Git -------------------------------------------------------------------
$git = Find-App 'git'
if ($git -and (Find-GitBash $git)) {
    Say "Git is already here: $git"
} else {
    $installed = Find-InstalledGit
    if ($installed -and (Find-GitBash $installed)) {
        $folder = Split-Path -Parent $installed
        if (Test-OnPersistedPath $folder) {
            Stop-NeedsRestart $RestartStaleSession
        }
        # Installed, but set up to stay off PATH: use it where it is.
        Say "Git is already here: $installed (not on PATH; using it directly)"
        $env:Path = "$folder;$env:Path"
    } else {
        Say "Installing Git because you're on Windows: it gives your team the command line its safety checks run in."
        if ($DryRun) {
            if (Find-App 'winget') {
                Say "would run: $WingetGit"
            } else {
                Say 'would download the 64-bit Git for Windows installer from the latest git-for-windows/git release and run it silently (winget is missing)'
            }
            Stop-NeedsRestart $RestartAfterInstall
        }
        if (Install-Git) {
            Stop-NeedsRestart $RestartAfterInstall
        }
        Stop-NeedsYou $GitByHand
    }
}

# -- 2. uv --------------------------------------------------------------------
$uv = Find-Uv
if ($uv) {
    Say "uv is already here: $uv"
} elseif ($DryRun) {
    Say "would run: powershell -ExecutionPolicy ByPass -c `"$UvInstall`""
    $uv = 'uv'
} else {
    Say 'Installing uv, a small tool that fetches the right Python for your team without touching the one your computer came with.'
    Say "running: powershell -ExecutionPolicy ByPass -c `"$UvInstall`""
    & powershell.exe -NoProfile -ExecutionPolicy ByPass -c $UvInstall | Out-Host
    # Look for uv again, by full path: this session's PATH has not caught up
    # with what was just installed.
    $uv = Find-Uv
    if (-not $uv) {
        Stop-NeedsYou 'uv could not be installed from https://astral.sh/uv/install.ps1. Check the internet connection, then paste the same message again. If the connection is fine, an antivirus that blocked the installer is the other common cause, and uv can be installed by hand from https://docs.astral.sh/uv/ before pasting the message again.'
    }
}

# -- 3. Python ----------------------------------------------------------------
if ($DryRun) {
    Say "would run: $uv python install 3.12"
    Say "would run: $uv python find 3.12"
    Say 'would prove that Python by running it'
    if ($SetupArgs.Count -gt 0) { Say "would run: nc_setup.py $($SetupArgs -join ' ')" }
    Write-Output 'BOOTSTRAP=OK python=dry-run'
    exit 0
}

Say "Installing Python so your team's memory and safety checks can run."
Say "running: $uv python install 3.12"
& $uv python install 3.12 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Stop-NeedsYou 'uv could not install Python 3.12. Check the internet connection, then paste the same message again.'
}
$env:UV_PYTHON_PREFERENCE = 'only-managed'
$python = @(& $uv python find 3.12)[0]
$env:UV_PYTHON_PREFERENCE = $null
if (-not $python -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Stop-NeedsYou 'Python 3.12 was installed, but uv could not say where it is. Paste the same message again.'
}

# -- 4. Prove it ----------------------------------------------------------------
$version = @(& $python -c $Proof)
if ($LASTEXITCODE -ne 0) {
    Stop-NeedsYou "The new Python at $python did not run (exit $LASTEXITCODE). Paste the same message again; if it fails the same way, this computer is blocking it."
}
Say "Python is ready: $($version[0])"

# Printed with forward slashes, which every shell on Windows takes inside
# double quotes; a backslash is an escape in Git Bash. This script keeps
# using the path as uv gave it.
Write-Output "BOOTSTRAP=OK python=$($python.Replace('\', '/'))"
if ($SetupArgs.Count -gt 0) {
    & $python (Join-Path $PSScriptRoot 'nc_setup.py') @SetupArgs
    exit $LASTEXITCODE
}
exit 0
