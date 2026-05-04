<#
.SYNOPSIS
  Actualiza bot-baileys al último commit del repo y reinicia el servicio.

.DESCRIPTION
  Pasos:
    1. Detiene el servicio Windows.
    2. git pull --ff-only.
    3. npm install (solo si package-lock.json cambió).
    4. Reinicia el servicio.
    5. Muestra los últimos logs.

  Pensado para correrse rutinariamente desde PowerShell elevado en el
  Windows Server cuando sale un cambio importante en el repo.

.PARAMETER InstallDir
  Carpeta raíz donde está el deploy. Default: C:\yoko-bot

.PARAMETER ServiceName
  Nombre del servicio Windows. Default: YokoBot

.PARAMETER ForceNpmInstall
  Corre npm install aunque package-lock no haya cambiado. Útil si rompiste
  node_modules a mano.

.EXAMPLE
  .\update-windows.ps1
  .\update-windows.ps1 -ForceNpmInstall
#>
[CmdletBinding()]
param(
    [string]$InstallDir  = "C:\yoko-bot",
    [string]$ServiceName = "YokoBot",
    [switch]$ForceNpmInstall
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# ── Admin check ──────────────────────────────────────────────────────────
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$prin = New-Object Security.Principal.WindowsPrincipal($me)
if (-not $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Este script requiere PowerShell elevado (Run as Administrator)." -ForegroundColor Red
    exit 1
}

$repoDir = Join-Path $InstallDir "yoko_chat"
$botDir  = Join-Path $repoDir   "bot-service"
$logsDir = Join-Path $InstallDir "logs"
$nssmExe = Join-Path $InstallDir "nssm.exe"
$lockFile = Join-Path $botDir "package-lock.json"

if (-not (Test-Path $botDir))  { Write-Host "No existe $botDir. ¿Corriste install-windows.ps1 antes?" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $nssmExe)) { Write-Host "No existe $nssmExe." -ForegroundColor Red; exit 1 }

# ── 1. Hash actual del lockfile ──────────────────────────────────────────
$lockHashBefore = ""
if (Test-Path $lockFile) {
    $lockHashBefore = (Get-FileHash $lockFile -Algorithm SHA256).Hash
}

# ── 2. Stop ──────────────────────────────────────────────────────────────
Write-Step "Deteniendo $ServiceName"
& $nssmExe stop $ServiceName
Start-Sleep -Seconds 2

# ── 3. Pull ──────────────────────────────────────────────────────────────
Write-Step "git pull"
Push-Location $repoDir
git pull --ff-only
Pop-Location

# ── 4. npm install (condicional) ─────────────────────────────────────────
$lockHashAfter = ""
if (Test-Path $lockFile) {
    $lockHashAfter = (Get-FileHash $lockFile -Algorithm SHA256).Hash
}
if ($ForceNpmInstall -or $lockHashBefore -ne $lockHashAfter) {
    Write-Step "Instalando dependencias (lockfile cambió$(if($ForceNpmInstall){' o -ForceNpmInstall'}))"
    Push-Location $botDir
    npm install --no-fund --no-audit
    Pop-Location
} else {
    Write-Step "Dependencias sin cambios — skip npm install"
}

# ── 5. Start ─────────────────────────────────────────────────────────────
Write-Step "Iniciando $ServiceName"
& $nssmExe start $ServiceName
Start-Sleep -Seconds 3
# Get-Service da output limpio y locale-independent — NSSM en es_PE
# imprime UTF-16 LE que se interpreta como "S E R V I C E _ R U N N I N G".
$svcInfo = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
$status  = if ($svcInfo) { $svcInfo.Status.ToString() } else { 'Unknown' }
Write-Ok "Status: $status"

# ── 6. Logs recientes ────────────────────────────────────────────────────
$outLog = Join-Path $logsDir "bot.out.log"
if (Test-Path $outLog) {
    Write-Step "Últimas 20 líneas del log"
    Get-Content $outLog -Tail 20
}

if ($status -ne "Running") {
    $errLog = Join-Path $logsDir "bot.err.log"
    Write-Warn "Servicio NO está corriendo. Logs de error:"
    if (Test-Path $errLog) { Get-Content $errLog -Tail 30 }
    exit 1
}

Write-Host ""
Write-Host "Update completo. Servicio corriendo." -ForegroundColor Green
