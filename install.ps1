# ShlepaFlash CLI Installer for Windows
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$RepoUrl = if ($env:SFLASHER_REPO_URL) { $env:SFLASHER_REPO_URL } else { "https://github.com/primenimoo/ShlepaFlash-CLI.git" }
$InstallDir = if ($env:SFLASHER_INSTALL_DIR) { $env:SFLASHER_INSTALL_DIR } else { Join-Path $HOME ".shlepaflash-cli" }
$BinDir = if ($env:SFLASHER_BIN_DIR) { $env:SFLASHER_BIN_DIR } else { Join-Path $HOME ".local\bin" }
$VenvDir = Join-Path $InstallDir "venv"
$RepoDir = Join-Path $InstallDir "repo"
$LogFile = Join-Path $InstallDir "install.log"

function Write-Step($msg) { Write-Host "  • $msg" -ForegroundColor DarkYellow }
function Write-Ok($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Err($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }
function Show-Bar($pct, $label) {
  $w = 28; $filled = [int]($w * $pct / 100)
  $bar = ("█" * $filled) + ("░" * ($w - $filled))
  Write-Host ("`r  [" + $bar + "] $pct% $label".PadRight(70)) -NoNewline -ForegroundColor DarkYellow
}

try {
  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  "" | Set-Content -Path $LogFile -Encoding UTF8
  Write-Host ""
  Write-Host "  🐾 ShlepaFlash CLI" -ForegroundColor DarkYellow
  Write-Host "     Compact installer" -ForegroundColor Gray
  Write-Host ""

  Show-Bar 5 "Проверка окружения"
  if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python 3.10+ не найден. Установи Python с https://python.org и отметь 'Add Python to PATH'."
  }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git не найден. Установи Git с https://git-scm.com/download/win"
  }
  $pyCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py -3" }

  Show-Bar 15 "Подготовка каталогов"
  New-Item -ItemType Directory -Force -Path $InstallDir, $BinDir | Out-Null

  function Invoke-Native($cmd, $cmdArgs) {
    & $cmd @cmdArgs 2>&1 | ForEach-Object { $_.ToString() } | Out-File -Append -FilePath $LogFile
    return $LASTEXITCODE
  }

  Show-Bar 30 "Загрузка исходников"
  if (Test-Path (Join-Path $RepoDir ".git")) {
    [void](Invoke-Native "git" @("-C", $RepoDir, "fetch", "--depth", "1", "origin", "main"))
    [void](Invoke-Native "git" @("-C", $RepoDir, "reset", "--hard", "origin/main"))
  } else {
    if (Test-Path $RepoDir) { Remove-Item -Recurse -Force $RepoDir }
    $code = Invoke-Native "git" @("clone", "--depth", "1", "--branch", "main", $RepoUrl, $RepoDir)
    if ($code -ne 0) { throw "Не удалось скачать репозиторий. Лог: $LogFile" }
  }

  Show-Bar 55 "Создание окружения"
  if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    if ($pyCmd -eq "python") { $code = Invoke-Native "python" @("-m","venv",$VenvDir) } else { $code = Invoke-Native "py" @("-3","-m","venv",$VenvDir) }
    if ($code -ne 0) { throw "Не удалось создать venv. Лог: $LogFile" }
  }

  Show-Bar 75 "Установка пакета"
  $venvPy = Join-Path $VenvDir "Scripts\python.exe"
  [void](Invoke-Native $venvPy @("-m","pip","install","--upgrade","pip","--disable-pip-version-check"))
  $code = Invoke-Native $venvPy @("-m","pip","install","--upgrade","--force-reinstall",$RepoDir,"--disable-pip-version-check")
  if ($code -ne 0) { throw "Не удалось установить пакет. Лог: $LogFile" }

  Show-Bar 90 "Создание команды sflasher"
  $launcherCmd = Join-Path $BinDir "sflasher.cmd"
  "@echo off`r`n`"$VenvDir\Scripts\sflasher.exe`" %*" | Set-Content -Path $launcherCmd -Encoding ASCII
  $launcherPs1 = Join-Path $BinDir "sflasher.ps1"
  "& `"$VenvDir\Scripts\sflasher.exe`" @args" | Set-Content -Path $launcherPs1 -Encoding UTF8

  # Add BinDir to User PATH persistently
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (-not $userPath) { $userPath = "" }
  $pathParts = $userPath.Split(';') | Where-Object { $_ -and $_.Trim() -ne "" }
  $hasBin = $false
  foreach ($p in $pathParts) { if ($p.TrimEnd('\').ToLower() -eq $BinDir.TrimEnd('\').ToLower()) { $hasBin = $true } }
  if (-not $hasBin) {
    $newUserPath = (($pathParts + $BinDir) -join ';')
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
  }
  # Refresh current session PATH
  $env:Path = ([Environment]::GetEnvironmentVariable("Path","User") + ";" + [Environment]::GetEnvironmentVariable("Path","Machine"))

  Show-Bar 100 "Готово"
  Write-Host ""
  Write-Host ""
  Write-Ok "ShlepaFlash CLI установлен"
  Write-Host "  Запуск: " -NoNewline -ForegroundColor Gray
  Write-Host "sflasher" -ForegroundColor White
  Write-Host "  Если команда не найдена, перезапусти терминал." -ForegroundColor Gray
  Write-Host ""
} catch {
  Write-Host ""
  Write-Host ""
  Write-Err $_.Exception.Message
  Write-Host "  Лог: $LogFile" -ForegroundColor Gray
  exit 1
}
