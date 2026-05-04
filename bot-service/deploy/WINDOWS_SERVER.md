# Deploy de bot-baileys en Windows (Server o PC personal)

Esta guía es para correr `bot-baileys` como un **servicio Windows** que arranca solo al boot, se reinicia si crashea, y queda corriendo aunque nadie tenga sesión iniciada. Sirve igual para Windows Server corporativo o para Windows 10/11 en una PC personal usada como mini-server transitorio.

> Para desarrollo local en tu propia PC sin servicializarlo, mirá `bot-service/README.md`.

---

## ¿PC personal o Windows Server? ¿Qué cambia?

El **código y los scripts son los mismos**. Lo que cambia es la preparación del OS:

| Aspecto                  | Windows Server                      | PC personal (Win 10/11)             |
|--------------------------|-------------------------------------|-------------------------------------|
| Acceso típico            | RDP corporativo                     | Frente al teclado / Remote Desktop  |
| Sleep / Hibernate        | OFF por default                     | ON por default → **hay que apagarlo** |
| Cierre de tapa (laptop)  | N/A                                 | Suspende por default → **hay que cambiarlo** |
| Reinicios programados    | Windows Update opcional             | Windows Update obligatorio          |
| 24/7 confiable           | Sí, por diseño                      | Depende de luz/internet del hogar   |
| Costo                    | Pagado por la empresa               | $0                                  |

### Si vas a usar tu PC personal como server

Hay un **paso previo** importante: correr `prep-pc-as-server.ps1` antes del install. Eso desactiva sleep, hibernate y (si es laptop) la suspensión por cierre de tapa.

```powershell
# PowerShell como Administrator
cd C:\temp\yoko_ai\bot-service\deploy
.\prep-pc-as-server.ps1     # solo PC personal, NO Windows Server
.\install-windows.ps1
```

Si la PC es **laptop**: dejala enchufada permanentemente. Cierre de tapa con el script ya configurado a "no hacer nada".

### Si vas a usar un Windows Server (corporativo o VPS)

Saltate el `prep-pc-as-server.ps1` (no hace falta — los servers ya vienen sin sleep) y andá directo al install.

### Migración futura a Hetzner cuando tengas tu primer cliente

Cuando llegue tracción y un VPS dedicado tenga sentido (US$5/mes), seguir la guía `LINUX_VPS.md`. Para no perder la sesión Baileys (no re-escanear QR), copiar la carpeta `auth/cmejia/` desde la PC al VPS antes del primer arranque del servicio. Tiempo total de migración: ~30-45 min.

---

## Pre-requisitos (instalación manual, una sola vez)

Conectate por RDP al server y, como **Administrator**, instalá estas tres cosas:

1. **Node.js LTS 20+**: descarga el .msi de [nodejs.org](https://nodejs.org/) y ejecutalo. Acepta los defaults.
2. **Git for Windows**: descarga el .exe de [git-scm.com](https://git-scm.com/) y ejecutalo. Acepta los defaults.
3. **NSSM 2.24**: descargá el zip de [nssm.cc/download](https://nssm.cc/download), abrilo, y copiá `win64\nssm.exe` a `C:\yoko-bot\nssm.exe` (creá la carpeta si no existe).

Verificá:

```powershell
node --version    # v20.x.x o v22.x.x
git --version     # 2.x
Test-Path C:\yoko-bot\nssm.exe   # True
```

---

## Quickstart

Abrí **PowerShell como Administrator** en el server.

```powershell
# 1. Cloná solo este folder o el repo entero (más simple)
git clone https://github.com/Zetrix1111/yoko_ai.git C:\temp\yoko_ai

# 2. Corré el script de instalación
cd C:\temp\yoko_ai\bot-service\deploy
.\install-windows.ps1
```

El script va a:

1. Verificar Node, Git y NSSM.
2. Clonar el repo a `C:\yoko-bot\yoko_ai\` (si no está ya).
3. `npm install` en `bot-service/`.
4. **Pausarse** y abrirte `notepad` con el `.env` para que llenés los secretos:
   ```
   AIRTABLE_TOKEN=patXXXXXXXXXX
   AIRTABLE_BASE_ID=app9s5KuEvlAlZJgl
   YOKO_BASE_URL=https://yokochat.vercel.app
   LOG_LEVEL=info
   ```
   Guardá y cerrá notepad. Volvé a correr el script.
5. Registrar el servicio Windows `YokoBot` con NSSM (auto-start, restart on crash, logs rotados a 10MB).
6. Arrancar el servicio.

Al final vas a ver:

```
==> Status: SERVICE_RUNNING
Deploy listo.
```

---

## Verificar que ande

```powershell
# Logs del bot en vivo (Ctrl+C para salir):
Get-Content C:\yoko-bot\logs\bot.out.log -Tail 50 -Wait

# Estado del servicio:
& C:\yoko-bot\nssm.exe status YokoBot
# Esperás: SERVICE_RUNNING

# Lista de servicios Windows:
Get-Service YokoBot
```

Esperás ver en el log:

```
[bot] iniciando manager
[manager] Iniciando session manager...
```

Y cuando alguien interactúa con el bot:

```
[cmejia] DEBUG msg from=...@s.whatsapp.net fromMe=false types=[conversation] text="hola"
[cmejia] ← Nombre: "hola"
[cmejia] LLM respondió en 1234ms
[cmejia] → +51XXX: respuesta enviada
```

---

## Migración inicial desde tu PC personal

Si ya tenés el bot corriendo en tu PC y querés migrarlo:

### Opción A — Empezar limpio (recomendado)

1. En la UI de Yoko: Configuración Ventas Inteligentes → "Desconectar".
2. En Airtable, en `wa_sessions/cmejia`, dejá `status=qr`, `qr_string=""`, `phone=""`.
3. Cerrá el bot en tu PC (`Ctrl+C`).
4. Corré `install-windows.ps1` en el server (si todavía no lo hiciste).
5. Recargá la UI de Yoko y escaneá el QR nuevo con el celular que vas a usar como WA del bot.

### Opción B — Heredar la sesión actual

Si no querés re-escanear:

1. **Detené el bot en tu PC** (`Ctrl+C`). NO lo vuelvas a arrancar.
2. **Copiá la carpeta auth completa** desde tu PC al server. Por RDP: arrastrá `C:\yoko_chat\bot-service\auth\cmejia\` y soltala en `C:\yoko-bot\yoko_ai\bot-service\auth\` del server.
3. Corré `install-windows.ps1` en el server.

⚠ A veces Baileys detecta el cambio de máquina y termina pidiendo nuevo QR igual. Si pasa, fallback a Opción A.

---

## Operación día a día

### Actualizar al último commit del repo

Cuando hayas pusheado cambios al repo que querés deployar:

```powershell
cd C:\temp\yoko_ai\bot-service\deploy   # o donde haya quedado el script
.\update-windows.ps1
```

Eso hace `git pull` + `npm install` (si cambió package-lock) + restart del servicio. Total: ~30 segundos.

### Reiniciar manualmente

```powershell
& C:\yoko-bot\nssm.exe restart YokoBot
```

### Detener (sin desinstalar)

```powershell
& C:\yoko-bot\nssm.exe stop YokoBot
```

### Ver logs

```powershell
# Últimas 50 líneas:
Get-Content C:\yoko-bot\logs\bot.out.log -Tail 50

# Tail en vivo:
Get-Content C:\yoko-bot\logs\bot.out.log -Tail 50 -Wait

# Errores únicamente:
Get-Content C:\yoko-bot\logs\bot.err.log -Tail 50
```

### Desinstalar todo

```powershell
& C:\yoko-bot\nssm.exe stop YokoBot
& C:\yoko-bot\nssm.exe remove YokoBot confirm
Remove-Item -Recurse -Force C:\yoko-bot
```

---

## Troubleshooting

### "Este script requiere PowerShell elevado"

Cerrá PowerShell, click derecho sobre el icono → "Run as Administrator".

### El servicio queda en `SERVICE_PAUSED` o no arranca

Mirá `C:\yoko-bot\logs\bot.err.log`. Causas comunes:

- **`Falta AIRTABLE_TOKEN o AIRTABLE_BASE_ID en env`**: el `.env` está mal o no existe.
- **`ECONNREFUSED` al hacer fetch a WhatsApp**: firewall corporativo bloqueando outbound. Pedile a TI que permita HTTPS saliente a `*.whatsapp.com`, `api.airtable.com`, `yokochat.vercel.app`.
- **`Cannot find module 'tsx'`**: `npm install` falló. Corré:
  ```powershell
  cd C:\yoko-bot\yoko_ai\bot-service
  npm install
  ```

### El antivirus marca node.exe o nssm.exe

Whitelisteá la carpeta `C:\yoko-bot\` en el antivirus corporativo. Es común con NSSM porque algunos malware se hacen pasar por servicios Windows.

### El QR aparece pero no se conecta después de escanear

Mirá el log. Si ves `code=440` repetidamente: hay otro "Desktop" linkeado en tu WhatsApp. En el celular que tiene la cuenta WA del bot: Settings → Linked devices → borrá los devices viejos.

### El servicio se corta solo cada cierto tiempo

NSSM tiene rotación de logs activa (10MB cada uno, 1 backup). Si el log crece más rápido que eso podés ajustar `AppRotateBytes` con:

```powershell
& C:\yoko-bot\nssm.exe set YokoBot AppRotateBytes 52428800   # 50MB
```

Para diagnosticar crashes: `Get-EventLog Application -Newest 20 | Where-Object {$_.Source -like "*YokoBot*"}`.

### Quiero correr 2 servicios separados (ej. cmejia y demo)

NSSM acepta varios servicios apuntando al mismo binario con configs distintas. Pero el bot actual es multi-tenant en un solo proceso (lee todas las filas de `wa_sessions` y arranca una `WaSession` por tenant). Para escalar: 1 servicio único, multi-tenant, escala vertical (más RAM/CPU). Si en el futuro hay >50 tenants, ahí sí dividir en servicios separados con `TENANT_FILTER` env var (no implementado todavía).

---

## Plan de salida

Si en algún momento perdés acceso al server del trabajo:

1. **Backup manual**: copiá `C:\yoko-bot\yoko_ai\bot-service\auth\` a un drive externo o a tu PC.
2. **Migrar a un VPS** (Hetzner CX22 € 4.51/mes recomendado): instalá Node 20 + Git, cloná el repo, copiá la carpeta `auth/` adentro, llenás el `.env`, registrás como servicio systemd. Sin perder sesiones de WhatsApp.

El plan completo de migración a VPS está fuera del alcance de este README, pero el patrón es idéntico al de Windows: la carpeta `auth/` es el único estado persistente que no podés regenerar.
