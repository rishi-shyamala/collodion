<#
.SYNOPSIS
  Install the collodion AI assistant on Windows: creates a venv under
  darktable's config directory, installs the dt-ai-helper Python package
  into it, copies the Lua front-end into darktable's lua\ directory, and
  registers it in darktable's luarc if it isn't already there.

.DESCRIPTION
  Mirrors scripts/install.sh (Linux/macOS). Safe to re-run: every step is
  idempotent. See README.md's "Install" section for what to do by hand
  afterwards (set python_path / helper prefs inside darktable so the Lua
  side finds this venv).

.PARAMETER DarktableConfigDir
  darktable's config directory. Default: $env:LOCALAPPDATA\darktable

.PARAMETER VenvDir
  Where to create the helper's venv. Default: <DarktableConfigDir>\ai-assistant-venv

.PARAMETER Python
  Python interpreter to build the venv with. Default: python

.EXAMPLE
  .\scripts\install.ps1
.EXAMPLE
  .\scripts\install.ps1 -DarktableConfigDir "C:\Users\me\AppData\Local\darktable" -Python "py -3.12"
#>

[CmdletBinding()]
param(
    [string]$DarktableConfigDir = (Join-Path $env:LOCALAPPDATA "darktable"),
    [string]$VenvDir = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    $VenvDir = Join-Path $DarktableConfigDir "ai-assistant-venv"
}

Write-Host "collodion install"
Write-Host "  repo root:              $RepoRoot"
Write-Host "  darktable config dir:   $DarktableConfigDir"
Write-Host "  helper venv:            $VenvDir"
Write-Host "  python interpreter:     $Python"
Write-Host ""

# Resolve the python launcher into an argv array so "py -3.12" works the
# same as a plain "python"/"python3" executable name.
$PythonParts = $Python -split '\s+'
$PythonExe = $PythonParts[0]
$PythonArgs = $PythonParts[1..($PythonParts.Length - 1)]

if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
    Write-Error "python interpreter '$PythonExe' not found on PATH"
    exit 1
}

# ---------------------------------------------------------------------------
# 1. Create (or reuse) the venv, install the helper package into it
# ---------------------------------------------------------------------------
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Host "==> creating venv at $VenvDir"
    & $PythonExe @PythonArgs -m venv $VenvDir
} else {
    Write-Host "==> reusing existing venv at $VenvDir"
}

if (-not (Test-Path $VenvPython)) {
    Write-Error "venv creation did not produce $VenvPython"
    exit 1
}

Write-Host "==> installing dt-ai-helper into the venv (editable, from $RepoRoot\helper)"
& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -e (Join-Path $RepoRoot "helper")

# ---------------------------------------------------------------------------
# 2. Copy the Lua front-end into darktable's lua\ directory
# ---------------------------------------------------------------------------
$DtLuaDir = Join-Path $DarktableConfigDir "lua"
New-Item -ItemType Directory -Force -Path $DtLuaDir | Out-Null

Write-Host "==> copying lua\dt-ai-assistant.lua to $DtLuaDir\"
Copy-Item -Force (Join-Path $RepoRoot "lua\dt-ai-assistant.lua") (Join-Path $DtLuaDir "dt-ai-assistant.lua")

# ---------------------------------------------------------------------------
# 3. Register the script in darktable's luarc, if not already there
# ---------------------------------------------------------------------------
$Luarc = Join-Path $DarktableConfigDir "luarc"
$RequireLine = 'require "dt-ai-assistant"'

New-Item -ItemType Directory -Force -Path $DarktableConfigDir | Out-Null
if (-not (Test-Path $Luarc)) {
    New-Item -ItemType File -Path $Luarc | Out-Null
}

$LuarcContent = Get-Content -Path $Luarc -Raw -ErrorAction SilentlyContinue
if ($LuarcContent -and $LuarcContent.Contains($RequireLine)) {
    Write-Host "==> $Luarc already requires dt-ai-assistant, leaving it alone"
} else {
    Write-Host "==> appending '$RequireLine' to $Luarc"
    Add-Content -Path $Luarc -Value $RequireLine
}

Write-Host ""
Write-Host "Done."
Write-Host ""
Write-Host "Next steps inside darktable's AI assistant preferences (lua options tab):"
Write-Host "  - 'python interpreter'                -> $VenvPython"
Write-Host "  - or leave it empty and set 'helper launch command override' to:"
Write-Host "      $VenvPython -m dt_ai_helper.main"
Write-Host "  - add at least one model preset (base URL / model / API key)"
Write-Host "(Re)start darktable to load the plugin."
