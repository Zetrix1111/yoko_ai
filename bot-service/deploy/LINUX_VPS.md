# Deploy de bot-baileys en VPS Linux (Hetzner / Ubuntu 24.04)

Esta guía cubre el deploy en un VPS Linux genérico, con foco en **Hetzner Cloud CX22** (US$5/mes, lo más barato confiable). Sirve igual para DigitalOcean, Vultr, Linode si elegís Ubuntu 24.04 LTS.

> Para Windows Server mirá `WINDOWS_SERVER.md`. Para desarrollo local en tu PC mirá el `README.md` raíz de `bot-service/`.

---

## Quickstart total (~30 min la primera vez)

### 1. SSH key en tu PC con Windows (~2 min)

```powershell
# PowerShell normal (no Admin)
ssh-keygen -t ed25519 -C "yoko-bot-hetzner"
# Enter al primer prompt (path default)
# Enter dos veces al passphrase prompt (sin password)

# Mostrar la pública para copiar:
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Copiá la línea entera (`ssh-ed25519 AAAA... yoko-bot-hetzner`).

### 2. Crear server en Hetzner (~10 min)

1. Cuenta en [hetzner.com](https://www.hetzner.com/cloud) → verificación con DNI/pasaporte (puede tardar 5-15 min para nuevos usuarios).
2. Cloud Console → New Project → "yoko-bot".
3. Add Server:
   - **Location**: Ashburn, VA (US East) — mejor latencia con Perú
   - **Image**: Ubuntu 24.04
   - **Type**: Shared vCPU → **CX22** (€4.51/mo, 2 vCPU + 4GB RAM)
   - **Networking**: IPv4 + IPv6 (default)
   - **SSH Keys**: Add SSH Key → pegá tu llave pública (la del paso 1)
   - **Volumes / Firewalls / Backups**: dejar todo default por ahora
   - **Name**: `yoko-bot-1`
4. Create & Buy Now → en ~30 segundos tenés el server. Anotá la **IPv4 pública** que aparece en el panel.

### 3. SSH desde tu PC al server (~1 min)

```powershell
# Reemplazá <IP> con la IPv4 que te dio Hetzner:
ssh root@<IP>
# Primera vez te pregunta "Are you sure you want to continue connecting?" → yes
# No te pide password porque ya configuraste SSH key.
```

Si te conecta y ves un prompt `root@yoko-bot-1:~#`, estás adentro del server. Si pide password, algo salió mal con la SSH key — avisame.

### 4. Correr el script de instalación (~5 min)

Adentro del server:

```bash
curl -fsSL https://raw.githubusercontent.com/Zetrix1111/yoko_ai/main/bot-service/deploy/install-linux.sh -o /tmp/install-linux.sh
chmod +x /tmp/install-linux.sh
/tmp/install-linux.sh
```

El script:

1. Actualiza apt e instala `git`, `build-essential`, `curl`, etc.
2. Instala Node.js 20 desde NodeSource si no está.
3. Clona el repo a `/opt/yoko-bot/yoko_ai/`.
4. Corre `npm install` en `bot-service/`.
5. **Se detiene** porque falta el `.env` (esperado).

### 5. Llenar el `.env` con tus secretos (~2 min)

```bash
nano /opt/yoko-bot/yoko_ai/bot-service/.env
```

Reemplazá los placeholders:

```
AIRTABLE_TOKEN=patXXXXXXXXXX
AIRTABLE_BASE_ID=app9s5KuEvlAlZJgl
YOKO_BASE_URL=https://yokochat.vercel.app
LOG_LEVEL=info
```

`Ctrl+O` → Enter → `Ctrl+X` para guardar y salir.

### 6. Volver a correr el script (~1 min)

```bash
/tmp/install-linux.sh
```

Esta vez sigue de largo: arma el systemd unit, lo habilita para auto-start al boot, y arranca el servicio. Termina con:

```
==> Status: active
Deploy listo.
```

### 7. Verificar que ande (~1 min)

```bash
# Logs en vivo:
journalctl -u yoko-bot -f -o cat

# Esperás ver:
# [bot] iniciando manager
# [manager] Iniciando session manager...
# (Ctrl+C para salir del tail)

# Status del servicio:
systemctl status yoko-bot
```

### 8. Escanear QR y probar (~5 min)

1. **Apagá el bot en tu PC** (`Ctrl+C` y cerrá la terminal). NO debe quedar corriendo en dos lados.
2. En la UI de Yoko: Configuración Ventas Inteligentes → "Desconectar".
3. En Airtable, fila `wa_sessions/cmejia`: `status=qr`, `qr_string=""`, `phone=""`.
4. Recargá la UI de Yoko. El QR aparece en 2-5s.
5. Escaneá con tu celular WhatsApp Personal de prueba.
6. En el log del server (`journalctl -u yoko-bot -f -o cat`) deberías ver:
   ```
   [cmejia] CONECTADO: +51XXXXXXXXX
   ```
7. Mandate un mensaje de prueba desde otro celular. En el log:
   ```
   [cmejia] DEBUG msg from=...@s.whatsapp.net fromMe=false types=[conversation] text="hola"
   [cmejia] ← Nombre: "hola"
   [cmejia] LLM respondió en 1234ms
   [cmejia] → +51XXX: respuesta enviada
   ```

Si llegaste hasta acá: **listo, deploy completo**. Tu PC ya no es necesaria.

---

## Operación día a día

### Actualizar al último commit del repo

Cuando pusheés cambios al repo:

```bash
ssh root@<IP> '/opt/yoko-bot/yoko_ai/bot-service/deploy/update-linux.sh'
```

Hace `git pull` + `npm install` (si lockfile cambió) + restart. Total: ~30 segundos.

### Ver logs

```bash
# En vivo:
ssh root@<IP> 'journalctl -u yoko-bot -f -o cat'

# Últimas 100 líneas:
ssh root@<IP> 'journalctl -u yoko-bot -n 100 -o cat'

# Desde hace 1 hora:
ssh root@<IP> 'journalctl -u yoko-bot --since "1 hour ago"'

# Solo errores:
ssh root@<IP> 'journalctl -u yoko-bot -p err'
```

### Reiniciar / detener / ver status

```bash
ssh root@<IP> 'systemctl restart yoko-bot'
ssh root@<IP> 'systemctl stop yoko-bot'
ssh root@<IP> 'systemctl status yoko-bot'
```

### Backup de la sesión Baileys

La carpeta `auth/cmejia/` es lo único persistente que no podés regenerar (sin re-escanear QR). Backup ocasional:

```powershell
# Desde tu PC, copia todo el folder:
scp -r root@<IP>:/opt/yoko-bot/yoko_ai/bot-service/auth $env:USERPROFILE\Desktop\auth-backup-$(Get-Date -Format yyyyMMdd)
```

Si en el futuro migrás a otro VPS, podés copiar este backup adentro del nuevo y mantener la sesión activa sin re-escanear.

### Snapshots en Hetzner (gratis, manual)

Antes de cualquier cambio riesgoso:
- Cloud Console → tu server → Snapshots → "Take Snapshot" → nombre tipo `pre-update-2026-05-03`.
- Si rompés algo, "Rebuild from snapshot".
- Los snapshots son gratis hasta 10 por cuenta. Después €0.012/GB/mes.

### Backups automáticos (opcional, +20% del precio)

Cloud Console → tu server → Backups → Enable. Cuesta €0.90/mes extra. Te hace snapshot diario y guarda 7 días. Útil cuando haya tracción real con clientes.

---

## Troubleshooting

### `npm install` falla con error de "node-gyp" / "python"

`build-essential` ya lo instala el script. Si igualmente falla, instalá Python 3:

```bash
apt-get install -y python3 python3-pip
cd /opt/yoko-bot/yoko_ai/bot-service && npm install
```

### El servicio no arranca

```bash
# Ver el error exacto:
journalctl -u yoko-bot --since "10 min ago" --no-pager
```

Causas comunes:
- **"Falta AIRTABLE_TOKEN..."**: el `.env` no tiene los valores. Revisá con `cat /opt/yoko-bot/yoko_ai/bot-service/.env`.
- **"ECONNREFUSED 443"**: muy raro en Hetzner pero puede pasar con proxies; descartar primero con `curl https://api.airtable.com`.
- **"Cannot find module 'tsx'"**: `npm install` falló. Re-correrlo a mano.

### Quiero entrar al server con un cliente SSH gráfico

- **Windows**: Termius (gratis), MobaXterm, PuTTY.
- **VS Code Remote SSH**: instalá la extensión "Remote - SSH", `Ctrl+Shift+P` → "Connect to Host" → `root@<IP>`. Editás los archivos del server desde VS Code como si fueran locales. **Recomendado** si vas a tocar archivos seguido.

### Hetzner me cobra más de lo esperado

CX22 son €4.51 + 19% IVA si la facturación es a un país UE. Para Perú no hay IVA UE → te cobran exactamente €4.51. Verificalo en tu billing.

Si activaste Backups (€0.90/mes) o Volumes adicionales, suman aparte.

### Quiero apagar el server temporalmente sin perder datos

```
Cloud Console → tu server → "Power" → "Shutdown"
```

Mientras está apagado **NO te cobran CPU/RAM**, pero sí el storage (€0.50/mes aprox). Para arrancarlo: "Power" → "Power On". El servicio systemd vuelve solo.

Si querés cero costo: "Delete" el server y antes hacé Snapshot. Después podés recrearlo desde el snapshot.

---

## Plan de salida

Si querés migrar a otro provider:

1. Backup de `auth/`: ver sección "Backup de la sesión Baileys" arriba.
2. En el nuevo provider con Ubuntu 24.04: corré el mismo `install-linux.sh`.
3. Antes del primer start del servicio, copiá la carpeta `auth/` del backup al nuevo path.
4. Llená el `.env` igual que antes.
5. Start. La sesión Baileys se mantiene activa sin re-escanear QR.

Total tiempo de migración: ~10 min si tenés el backup hecho.
