<#
.SYNOPSIS
  Instala bot-baileys como servicio Windows usando NSSM.

.DESCRIPTION
  Script idempotente. Hace:
    1. Verifica que Node, Git y NSSM estén disponibles.
    2. Clona o actualiza el repo en -InstallDir.
    3. Corre npm install.
    4. Verifica que .env exista (no lo crea — el usuario lo provee).
    5. Registra el servicio Windows con NSSM si no existe.
    6. Lo arranca.

  Funciona tanto en Windows Server (RDP corporativo) como en Windows
  10/11 personal. NSSM corre el servicio como LocalSystem, así que
  arranca al boot incluso sin que un usuario inicie sesión.

  Si esto es una PC personal, conviene correr ANTES `prep-pc-as-server.ps1`
  para desactivar sleep/hibernate y evitar que el bot se caiga cuando no
  estés frente a la PC.

.PARAMETER InstallDir
  Carpeta raíz donde vive todo (repo + logs + nssm.exe).
  Default: C:\yoko-bot

.PARAMETER ServiceName
  Nombre del servicio Windows. Default: YokoBot

.PARAMETER RepoUrl
  URL del repo. Default: https://github.com/Zetrix1111/yoko_ai.git

.EXAMPLE
  .\install-windows.ps1
  .\install-windows.ps1 -InstallDir D:\bots\yoko -ServiceName YokoBotProd

.NOTES
  Pre-requisitos manuales (NO los instala el script):
    - Node.js 20+ desde nodejs.org
    - Git for Windows desde git-scm.com
    - nssm.exe (descargar zip de nssm.cc/download, copiar win64\nssm.exe a $InstallDir\nssm.exe)
#>
[CmdletBinding()]
param(
    [string]$InstallDir   = "C:\yoko-bot",
    [string]$ServiceName  = "YokoBot",
    [string]$RepoUrl      = "https://github.com/Zetrix1111/yoko_ai.git"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }

# ── 0. Admin check ───────────────────────────────────────────────────────
$me = [Security.Principal.WindowsIdentity]::GetCurrent()
$prin = New-Object Security.Principal.WindowsPrincipal($me)
if (-not $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Este script requiere PowerShell elevado (Run as Administrator)."
    exit 1
}

# ── 1. Pre-requisitos ────────────────────────────────────────────────────
Write-Step "Verificando pre-requisitos"

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Err "Node.js no está instalado o no está en PATH."
    Write-Err "Instalá Node.js LTS 20+ desde https://nodejs.org/ y volvé a correr este script."
    exit 1
}
$nodeVersion = (node --version).TrimStart('v').Split('.')[0]
if ([int]$nodeVersion -lt 20) {
    Write-Err "Node.js v$nodeVersion detectado. Se requiere v20 o superior."
    exit 1
}
Write-Ok "Node $(node --version) en $($nodeCmd.Source)"

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Err "Git no está instalado o no está en PATH."
    Write-Err "Instalá Git for Windows desde https://git-scm.com/ y volvé a correr este script."
    exit 1
}
Write-Ok "$(git --version)"

# ── 2. Estructura de carpetas ────────────────────────────────────────────
Write-Step "Preparando $InstallDir"
$logsDir   = Join-Path $InstallDir "logs"
# Cloneamos en una carpeta llamada "yoko_chat" (mismo nombre que en la PC del
# desarrollador), aunque el repo GitHub se llame "yoko_ai". Mantiene un mental
# model consistente entre dev local y server.
$repoDir   = Join-Path $InstallDir "yoko_chat"
$botDir    = Join-Path $repoDir   "bot-service"
$envFile   = Join-Path $botDir    ".env"
$nssmExe   = Join-Path $InstallDir "nssm.exe"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $logsDir    | Out-Null
Write-Ok "Carpetas creadas: $InstallDir, $logsDir"

if (-not (Test-Path $nssmExe)) {
    Write-Err "Falta $nssmExe"
    Write-Err "Descargá el zip de https://nssm.cc/download , extraé win64\nssm.exe a $InstallDir\nssm.exe y volvé a correr el script."
    exit 1
}
Write-Ok "NSSM en $nssmExe"

# ── 3. Clonar o actualizar repo ──────────────────────────────────────────
Write-Step "Sincronizando repo desde $RepoUrl"
if (Test-Path (Join-Path $repoDir ".git")) {
    Write-Ok "Repo ya existe — haciendo git pull"
    Push-Location $repoDir
    git pull --ff-only
    Pop-Location
} else {
    git clone $RepoUrl $repoDir
    Write-Ok "Clonado en $repoDir"
}

# ── 4. Instalar dependencias ─────────────────────────────────────────────
Write-Step "Instalando dependencias de bot-service"
Push-Location $botDir
npm install --no-fund --no-audit
Pop-Location
Write-Ok "node_modules listo"

# ── 5. Verificar .env ────────────────────────────────────────────────────
Write-Step "Verificando .env"
if (-not (Test-Path $envFile)) {
    $exampleFile = Join-Path $botDir ".env.example"
    if (Test-Path $exampleFile) {
        Copy-Item $exampleFile $envFile
        Write-Warn ".env no existía. Copié .env.example a .env."
    }
    Write-Err "DETENIENDO. Editá $envFile con tus credenciales reales antes de continuar:"
    Write-Err "  AIRTABLE_TOKEN=patXXXXXXXXXX"
    Write-Err "  AIRTABLE_BASE_ID=app9s5KuEvlAlZJgl"
    Write-Err "  YOKO_BASE_URL=https://yokochat.vercel.app"
    Write-Err "  LOG_LEVEL=info"
    Write-Err ""
    Write-Err "Después volvé a correr este script."
    notepad $envFile
    exit 1
}
Write-Ok ".env presente — recordá restringir permisos NTFS si compartís el server"

# ── 6. Registrar servicio NSSM ───────────────────────────────────────────
Write-Step "Configurando servicio Windows '$ServiceName'"

$nodeExe = $nodeCmd.Source
$tsxCli  = Join-Path $botDir "node_modules\tsx\dist\cli.mjs"
$entryTs = "src/index.ts"
$outLog  = Join-Path $logsDir "bot.out.log"
$errLog  = Join-Path $logsDir "bot.err.log"

if (-not (Test-Path $tsxCli)) {
    Write-Err "No encontré $tsxCli — npm install puede haber fallado. Revisá los logs."
    exit 1
}

# Get-Service maneja "no existe" devolviendo $null limpiamente.
# Usar `nssm status` directo se interrumpe con $ErrorActionPreference=Stop
# porque NSSM imprime a stderr "Can't open service!" cuando no existe.
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Ok "Servicio ya existe (status: $($existingService.Status)). Aplicando configuración por si cambió algo."
    if ($existingService.Status -eq 'Running') {
        & $nssmExe stop $ServiceName | Out-Null
        Start-Sleep -Seconds 2
    }
} else {
    & $nssmExe install $ServiceName $nodeExe $tsxCli $entryTs
    if ($LASTEXITCODE -ne 0) {
        Write-Err "nssm install fallo (exit $LASTEXITCODE). Necesita PowerShell elevado (Run as Administrator)."
        exit 1
    }
    Write-Ok "Servicio instalado"
}

& $nssmExe set $ServiceName AppDirectory       $botDir            | Out-Null
& $nssmExe set $ServiceName AppStdout          $outLog            | Out-Null
& $nssmExe set $ServiceName AppStderr          $errLog            | Out-Null
& $nssmExe set $ServiceName AppStdoutCreationDisposition 4        | Out-Null  # APPEND
& $nssmExe set $ServiceName AppStderrCreationDisposition 4        | Out-Null
& $nssmExe set $ServiceName AppRotateFiles     1                  | Out-Null
& $nssmExe set $ServiceName AppRotateBytes     10485760           | Out-Null  # 10MB
& $nssmExe set $ServiceName AppExit Default    Restart            | Out-Null
& $nssmExe set $ServiceName AppRestartDelay    5000               | Out-Null
& $nssmExe set $ServiceName Start              SERVICE_AUTO_START | Out-Null
& $nssmExe set $ServiceName Description "bot-baileys que conecta WhatsApp con Yoko (Vercel)" | Out-Null
& $nssmExe set $ServiceName DisplayName  "Yoko WhatsApp Bot"      | Out-Null
Write-Ok "Configuración aplicada"

# ── 7. Arrancar ──────────────────────────────────────────────────────────
Write-Step "Arrancando servicio"
& $nssmExe start $ServiceName
Start-Sleep -Seconds 3
$status = & $nssmExe status $ServiceName
Write-Ok "Status: $status"

if ($status -ne "SERVICE_RUNNING") {
    Write-Warn "El servicio no quedó en SERVICE_RUNNING. Revisá:"
    Write-Warn "  Get-Content '$errLog' -Tail 50"
}

# ── 8. Final ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════"
Write-Host "  Deploy listo." -ForegroundColor Green
Write-Host ""
Write-Host "  Logs en vivo:"
Write-Host "    Get-Content '$outLog' -Tail 50 -Wait"
Write-Host ""
Write-Host "  Comandos útiles:"
Write-Host "    & '$nssmExe' status   $ServiceName"
Write-Host "    & '$nssmExe' restart  $ServiceName"
Write-Host "    & '$nssmExe' stop     $ServiceName"
Write-Host ""
Write-Host "  Para actualizar a la última versión del repo:"
Write-Host "    .\update-windows.ps1"
Write-Host ""
Write-Host "  Si esto es una PC personal (no un Windows Server)," -ForegroundColor Yellow
Write-Host "  corré también para desactivar sleep/hibernate:"  -ForegroundColor Yellow
Write-Host "    .\prep-pc-as-server.ps1"                       -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════"
