$ErrorActionPreference = "Stop"
$RepoUrl = if ($env:SFLASHER_REPO_URL) { $env:SFLASHER_REPO_URL } else { "https://github.com/primenimoo-alt/ShlepaFlash-CLI.git" }
$InstallDir = if ($env:SFLASHER_INSTALL_DIR) { $env:SFLASHER_INSTALL_DIR } else { Join-Path $HOME ".shlepaflash-cli" }
$BinDir = if ($env:SFLASHER_BIN_DIR) { $env:SFLASHER_BIN_DIR } else { Join-Path $HOME ".local\bin" }
$VenvDir = Join-Path $InstallDir "venv"
$RepoDir = Join-Path $InstallDir "repo"

Write-Host "[ShlepaFlash] Installing ShlepaFlash CLI..." -ForegroundColor DarkYellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.10+ not found" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found" }

New-Item -ItemType Directory -Force -Path $InstallDir, $BinDir | Out-Null
if (Test-Path (Join-Path $RepoDir ".git")) {
  Write-Host "[ShlepaFlash] Updating existing repo..." -ForegroundColor DarkYellow
  git -C $RepoDir pull --ff-only | Out-Null
} else {
  if (Test-Path $RepoDir) { Remove-Item -Recurse -Force $RepoDir }
  Write-Host "[ShlepaFlash] Cloning repository..." -ForegroundColor DarkYellow
  git clone --depth 1 $RepoUrl $RepoDir | Out-Null
}

Write-Host "[ShlepaFlash] Creating virtual environment..." -ForegroundColor DarkYellow
python -m venv $VenvDir
& (Join-Path $VenvDir "Scripts\python.exe") -m pip install --upgrade pip | Out-Null
& (Join-Path $VenvDir "Scripts\python.exe") -m pip install $RepoDir | Out-Null

$Launcher = Join-Path $BinDir "sflasher.cmd"
"@echo off`r`n`"$VenvDir\Scripts\sflasher.exe`" %*" | Set-Content -Encoding ASCII $Launcher
Write-Host "[ShlepaFlash] Installed. Add $BinDir to PATH if needed." -ForegroundColor Green
Write-Host "[ShlepaFlash] Run: sflasher" -ForegroundColor Green
