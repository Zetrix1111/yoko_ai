#!/usr/bin/env bash
#
# install-linux.sh — Instala bot-baileys como servicio systemd en Ubuntu/Debian.
#
# Idempotente: podés correrlo varias veces sin romper nada.
# Pensado para correrse como root en un VPS Hetzner / DO / etc. con
# Ubuntu 24.04 LTS recién provisionado.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/Zetrix1111/yoko_ai/main/bot-service/deploy/install-linux.sh | bash
# o, si ya tenés el repo:
#   /opt/yoko-bot/yoko_ai/bot-service/deploy/install-linux.sh
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/yoko-bot}"
REPO_URL="${REPO_URL:-https://github.com/Zetrix1111/yoko_ai.git}"
SERVICE_NAME="${SERVICE_NAME:-yoko-bot}"
NODE_MAJOR="${NODE_MAJOR:-20}"

REPO_DIR="${INSTALL_DIR}/yoko_ai"
BOT_DIR="${REPO_DIR}/bot-service"
ENV_FILE="${BOT_DIR}/.env"
ENV_EXAMPLE="${BOT_DIR}/.env.example"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

log()  { printf '\e[36m==> %s\e[0m\n' "$*"; }
ok()   { printf '    \e[32m%s\e[0m\n' "$*"; }
warn() { printf '    \e[33m%s\e[0m\n' "$*"; }
err()  { printf '    \e[31m%s\e[0m\n' "$*" >&2; }

# ── 0. Root check ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  err "Este script requiere root. Probá: sudo $0"
  exit 1
fi

# ── 1. Pre-requisitos del sistema ────────────────────────────────────────
log "Actualizando apt e instalando deps básicas"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y curl ca-certificates gnupg git build-essential
ok "git $(git --version | awk '{print $3}'), build-essential listos"

# ── 2. Node.js ────────────────────────────────────────────────────────────
if ! command -v node >/dev/null 2>&1 || \
   [[ "$(node --version | sed 's/v\([0-9]*\).*/\1/')" -lt "${NODE_MAJOR}" ]]; then
  log "Instalando Node.js ${NODE_MAJOR}.x via NodeSource"
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -qq -y nodejs
fi
ok "Node $(node --version) en $(command -v node)"
ok "npm  $(npm --version)"

# ── 3. Estructura de carpetas ────────────────────────────────────────────
log "Preparando ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

# ── 4. Clonar o actualizar repo ──────────────────────────────────────────
log "Sincronizando repo desde ${REPO_URL}"
if [[ -d "${REPO_DIR}/.git" ]]; then
  ok "Repo ya existe — git pull"
  git -C "${REPO_DIR}" pull --ff-only
else
  git clone "${REPO_URL}" "${REPO_DIR}"
  ok "Clonado en ${REPO_DIR}"
fi

# ── 5. npm install ───────────────────────────────────────────────────────
log "Instalando dependencias de bot-service"
cd "${BOT_DIR}"
npm install --no-fund --no-audit
ok "node_modules listo"

# ── 6. .env ──────────────────────────────────────────────────────────────
log "Verificando .env"
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE}" ]]; then
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    warn ".env no existía. Copié .env.example a .env."
  fi
  err ""
  err "DETENIENDO. Editá ${ENV_FILE} con tus credenciales reales:"
  err ""
  err "  nano ${ENV_FILE}"
  err ""
  err "Llenar:"
  err "  AIRTABLE_TOKEN=patXXXXXXXXXX"
  err "  AIRTABLE_BASE_ID=app9s5KuEvlAlZJgl"
  err "  YOKO_BASE_URL=https://yokochat.vercel.app"
  err "  LOG_LEVEL=info"
  err ""
  err "Después volvé a correr este script."
  exit 1
fi
chmod 600 "${ENV_FILE}"
ok ".env presente, permisos 600 (solo root puede leer)"

# ── 7. systemd unit ──────────────────────────────────────────────────────
log "Configurando servicio systemd '${SERVICE_NAME}'"
NODE_BIN="$(command -v node)"
TSX_CLI="${BOT_DIR}/node_modules/tsx/dist/cli.mjs"

if [[ ! -f "${TSX_CLI}" ]]; then
  err "No encontré ${TSX_CLI} — npm install puede haber fallado."
  exit 1
fi

cat > "${UNIT_FILE}" <<UNIT
[Unit]
Description=Yoko WhatsApp Bot (Baileys)
Documentation=https://github.com/Zetrix1111/yoko_ai
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${BOT_DIR}
ExecStart=${NODE_BIN} ${TSX_CLI} src/index.ts
Restart=on-failure
RestartSec=5s
# Captura stdout/stderr en journalctl (rotación automática a cargo de systemd)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
# Endurecimiento ligero
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT

ok "Unit file: ${UNIT_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
ok "Servicio habilitado para auto-start al boot"

# ── 8. Arrancar (o reiniciar si ya estaba) ───────────────────────────────
log "Arrancando ${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}.service"
sleep 3
status="$(systemctl is-active "${SERVICE_NAME}.service" || true)"
ok "Status: ${status}"

# ── 9. Final ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Deploy listo."
echo ""
echo "  Logs en vivo (Ctrl+C para salir):"
echo "    journalctl -u ${SERVICE_NAME} -f -o cat"
echo ""
echo "  Comandos útiles:"
echo "    systemctl status   ${SERVICE_NAME}"
echo "    systemctl restart  ${SERVICE_NAME}"
echo "    systemctl stop     ${SERVICE_NAME}"
echo "    journalctl -u ${SERVICE_NAME} --since '10 min ago'"
echo ""
echo "  Para actualizar a la última versión del repo:"
echo "    ${BOT_DIR}/deploy/update-linux.sh"
echo "════════════════════════════════════════════════════════════════"

if [[ "${status}" != "active" ]]; then
  warn "El servicio NO quedó activo. Revisá:"
  warn "  journalctl -u ${SERVICE_NAME} --since '5 min ago'"
  exit 1
fi
