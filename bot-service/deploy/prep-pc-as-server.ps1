<#
.SYNOPSIS
  Configura una PC personal Windows 10/11 para que se comporte como un mini-server
  24/7. Desactiva sleep, hibernate y (en laptops) la suspensión por cierre de tapa.

.DESCRIPTION
  Idempotente. Pensado para correrse UNA vez (o cuando agregues una PC nueva al
  bot). Si después querés volver a usar la PC en modo "personal" con sleep
  normal, mirá la sección REVERT al final.

  Cambios aplicados:
    1. Sleep AC/DC = 0 (nunca dormir)
    2. Hibernate AC/DC = 0 (nunca hibernar)
    3. Hibernación globalmente OFF → libera hiberfil.sys (varios GB)
    4. Si la PC es laptop: cierre de tapa = "no hacer nada"

  Notas:
    - El monitor SÍ se sigue apagando (no afecta al servicio del bot, ahorra
      energía y vida de la pantalla).
    - Si la PC es laptop con batería: cuando esté desenchufada el bot se queda
      sin red WiFi en algún momento — es esperado. Ideal: dejarla enchufada.

.NOTES
  Requiere PowerShell elevado (Run as Administrator).

  Para REVERTIR los cambios después:
    powercfg /change standby-timeout-ac 30      # 30 min antes de dormir
    powercfg /change standby-timeout-dc 15
    powercfg /change hibernate-timeout-ac 60
    powercfg /change hibernate-timeout-dc 30
    powercfg /hibernate on                       # reactivar hiberfil.sys
    powercfg -setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1   # suspend on lid close
    powercfg -setactive SCHEME_CURRENT
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }

# ── Admin check ──────────────────────────────────────────────────────────
$me   = [Security.Principal.WindowsIdentity]::GetCurrent()
$prin = New-Object Security.Principal.WindowsPrincipal($me)
if (-not $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Este script requiere PowerShell elevado (Run as Administrator)."
    exit 1
}

# ── 1. Power timeouts (sleep + hibernate, AC y DC) ───────────────────────
Write-Step "Desactivando sleep e hibernación por timeout"

powercfg /change standby-timeout-ac 0     | Out-Null
powercfg /change standby-timeout-dc 0     | Out-Null
powercfg /change hibernate-timeout-ac 0   | Out-Null
powercfg /change hibernate-timeout-dc 0   | Out-Null
Write-Ok "Sleep AC/DC = 0 (nunca)"
Write-Ok "Hibernate AC/DC = 0 (nunca)"

# ── 2. Hibernación globalmente off (libera hiberfil.sys) ─────────────────
Write-Step "Desactivando hibernación globalmente"
powercfg /hibernate off | Out-Null
Write-Ok "Hibernación OFF — hiberfil.sys removido (libera varios GB)"

# ── 3. Detectar si es laptop y configurar cierre de tapa ─────────────────
Write-Step "Detectando tipo de chasis"
try {
    # ChassisTypes: 9=Laptop, 10=Notebook, 14=SubNotebook, 8=Portable
    $chassisTypes = (Get-CimInstance -ClassName Win32_SystemEnclosure).ChassisTypes
    $laptopTypes  = @(8, 9, 10, 14)
    $isLaptop     = $false
    foreach ($ct in $chassisTypes) {
        if ($laptopTypes -contains [int]$ct) { $isLaptop = $true }
    }
} catch {
    Write-Warn "No pude detectar chasis vía WMI. Asumiendo desktop."
    $isLaptop = $false
}

if ($isLaptop) {
    Write-Ok "Detectado: laptop. Aplicando 'no hacer nada' al cerrar tapa."
    # GUID SUB_BUTTONS / LIDACTION
    # 0=Do nothing, 1=Sleep, 2=Hibernate, 3=Shutdown
    powercfg -setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0  | Out-Null
    powercfg -setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0  | Out-Null
    powercfg -setactive SCHEME_CURRENT                                | Out-Null
    Write-Ok "Cierre de tapa: 'No hacer nada' tanto enchufado como en batería"
    Write-Warn "Recordá dejar la laptop ENCHUFADA permanentemente para que el bot ande 24/7."
} else {
    Write-Ok "Detectado: desktop. No hay tapa que configurar."
}

# ── 4. Resumen ───────────────────────────────────────────────────────────
Write-Step "Resumen de configuración actual"
Write-Host ""
powercfg /q SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String -Pattern "Power Setting|AC|DC" | ForEach-Object { Write-Host "    $_" }
Write-Host ""

Write-Host "════════════════════════════════════════════════════════════════"
Write-Host "  PC configurada como mini-server." -ForegroundColor Green
Write-Host ""
Write-Host "  La pantalla puede apagarse (eso no apaga la PC ni al servicio)."
Write-Host "  La PC NO va a entrar a sleep/hibernate por inactividad."
if ($isLaptop) {
    Write-Host "  Podés cerrar la tapa sin que se suspenda — pero dejala enchufada."
}
Write-Host ""
Write-Host "  Próximo paso: si todavía no instalaste el servicio del bot,"
Write-Host "    .\install-windows.ps1"
Write-Host ""
Write-Host "  Para REVERTIR estos cambios cuando quieras volver a usar la PC"
Write-Host "  en modo normal, mirá la sección NOTES del header de este script."
Write-Host "════════════════════════════════════════════════════════════════"
