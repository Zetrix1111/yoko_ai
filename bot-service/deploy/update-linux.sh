#!/usr/bin/env bash
#
# update-linux.sh — Actualiza bot-baileys al último commit y reinicia el servicio.
#
# Uso:
#   sudo /opt/yoko-bot/yoko_chat/bot-service/deploy/update-linux.sh
#
# O si ya estás dentro de la carpeta:
#   sudo ./update-linux.sh
#
# Variables de entorno opcionales:
#   FORCE_NPM_INSTALL=1   → corre npm install aunque package-lock no haya cambiado
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/yoko-bot}"
SERVICE_NAME="${SERVICE_NAME:-yoko-bot}"

REPO_DIR="${INSTALL_DIR}/yoko_chat"
BOT_DIR="${REPO_DIR}/bot-service"
LOCK_FILE="${BOT_DIR}/package-lock.json"

log()  { printf '\e[36m==> %s\e[0m\n' "$*"; }
ok()   { printf '    \e[32m%s\e[0m\n' "$*"; }
warn() { printf '    \e[33m%s\e[0m\n' "$*"; }
err()  { printf '    \e[31m%s\e[0m\n' "$*" >&2; }

if [[ $EUID -ne 0 ]]; then
  err "Requiere root. Probá: sudo $0"
  exit 1
fi

if [[ ! -d "${BOT_DIR}" ]]; then
  err "No existe ${BOT_DIR}. ¿Corriste install-linux.sh primero?"
  exit 1
fi

# Hash del lockfile antes
hash_before=""
[[ -f "${LOCK_FILE}" ]] && hash_before="$(sha256sum "${LOCK_FILE}" | awk '{print $1}')"

log "Deteniendo ${SERVICE_NAME}"
systemctl stop "${SERVICE_NAME}.service"

log "git pull"
git -C "${REPO_DIR}" pull --ff-only

# Hash del lockfile después
hash_after=""
[[ -f "${LOCK_FILE}" ]] && hash_after="$(sha256sum "${LOCK_FILE}" | awk '{print $1}')"

if [[ "${FORCE_NPM_INSTALL:-0}" == "1" ]] || [[ "${hash_before}" != "${hash_after}" ]]; then
  log "Instalando dependencias (lockfile cambió o FORCE_NPM_INSTALL=1)"
  cd "${BOT_DIR}"
  npm install --no-fund --no-audit
else
  log "Dependencias sin cambios — skip npm install"
fi

# Si install-linux.sh fue actualizado en el repo, reinstalar la unit es seguro
# (sobreescribe con el mismo contenido si no hay cambios). Lo hacemos para que
# este script solo baste como "deploy" cuando hay cambios en la unit.
if [[ -x "${BOT_DIR}/deploy/install-linux.sh" ]]; then
  log "Re-aplicando configuración systemd (idempotente)"
  # Solo re-genera la unit, NO reinstala apt/node/npm si ya están al día.
  # install-linux.sh falla si .env falta — acá ya existe entonces sigue de largo.
  bash "${BOT_DIR}/deploy/install-linux.sh" >/dev/null
fi

log "Iniciando ${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}.service"
sleep 3
status="$(systemctl is-active "${SERVICE_NAME}.service" || true)"
ok "Status: ${status}"

log "Últimas 20 líneas del log"
journalctl -u "${SERVICE_NAME}.service" -n 20 -o cat --no-pager

if [[ "${status}" != "active" ]]; then
  err "Servicio NO está corriendo. Logs de error:"
  journalctl -u "${SERVICE_NAME}.service" --since '5 min ago' --no-pager
  exit 1
fi

echo ""
ok "Update completo. Servicio corriendo."
