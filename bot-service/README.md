# bot-baileys — Puente WhatsApp ↔ Yoko IA

Servicio Node.js que conecta WhatsApp Web (vía [Baileys](https://github.com/WhiskeySockets/Baileys)) con la IA de Yoko (Vercel). Multi-tenant: una sola instancia maneja N empresas, cada una con su propio número de WhatsApp.

**El bot es un puente tonto.** No tiene IA propia. Cuando llega un mensaje, llama a `POST /api/sales_chat` en Yoko, que es donde vive el cerebro (catálogo de productos + reglas de venta + OpenAI). El bot solo persiste en Airtable y reenvía la respuesta por WhatsApp.

---

## Arquitectura rápida

```
WhatsApp del cliente final
        │
        ▼  (Baileys WebSocket)
┌─────────────────────────────────┐         ┌──────────────────────┐
│  bot-baileys (este servicio)    │  HTTP   │  Yoko Vercel         │
│                                 │  ◄────► │  /api/sales_chat     │
│  • N sockets Baileys            │         │  (catálogo + IA)     │
│  • auth/<empresa_id>/           │         └──────────────────────┘
│  • Polls wa_sessions  cada 5s   │                 ▲
│  • Polls outbox       cada 2s   │                 │
│                                 │  ◄──── escribe mensajes
│                                 │                 │
└─────────────────────────────────┘                 │
        │                                           │
        ▼                                           │
        Airtable (base "Tablas CMEJIA SAC")  ◄──────┘
        Tablas: wa_sessions, conversaciones, mensajes, outbox
```

---

## Setup local (PC del dev)

### Requisitos

- **Node.js 20+** (Baileys lo requiere)
- Cuenta de Airtable con la base `app9s5KuEvlAlZJgl` accesible
- Yoko desplegado en Vercel (`https://yokochat.vercel.app`) — el bot lo consume

### Instalación

```bash
cd bot-service
npm install
```

`npm install` toma 1-2 minutos por compilación nativa de algunas deps de Baileys.

### Configuración

```bash
cp .env.example .env
# editar .env con los valores reales:
#   AIRTABLE_TOKEN=pat...   (tu Personal Access Token de Airtable)
#   AIRTABLE_BASE_ID=app9s5KuEvlAlZJgl
#   YOKO_BASE_URL=https://yokochat.vercel.app
#   LOG_LEVEL=silent  (cambialo a 'info' para ver logs internos de Baileys)
```

### Ejecutar

```bash
npm run start
```

Verás:
```
════════════════════════════════════════════════
  Yoko bot-baileys — WhatsApp ↔ IA bridge
════════════════════════════════════════════════
[bot] AIRTABLE_BASE_ID = app9s5KuEvlAlZJgl
[bot] YOKO_BASE_URL    = https://yokochat.vercel.app
[manager] Iniciando session manager...
[bot] LISTO. Polling wa_sessions cada 5s, outbox cada 2s.
```

El bot queda esperando. **Ahora desde Yoko**, andás a Ventas Inteligentes → Configuración → click "Vincular WhatsApp". Eso escribe `wa_sessions[empresa_id=cmejia].status = 'qr'`. En el próximo tick (≤5s), el bot detecta el cambio, abre el socket Baileys, genera el QR y lo escribe en `wa_sessions.qr_string`. La UI lo renderiza. Escaneás con tu WhatsApp y queda conectado.

---

## Cómo funciona (flujo completo)

### Vincular WhatsApp (primer setup)

1. Usuario en Yoko clickea "Vincular WhatsApp" → `wa.py` upserta `wa_sessions` con `status='qr', qr_string=''`.
2. Bot poll detecta status='qr' sin sesión en memoria → instancia un `WaSession` para ese tenant.
3. `WaSession.start()` abre Baileys con `Browsers.macOS('Desktop')` y `fetchLatestBaileysVersion()`.
4. Baileys emite el evento `qr` con un string raw → el bot lo escribe en `wa_sessions.qr_string`.
5. La UI hace polling de `/api/wa` cada 2s, detecta `qr_string`, lo renderiza con `react-qr-code`.
6. Usuario escanea con su WhatsApp.
7. Baileys emite `connection: 'open'`, el bot escribe `status='connected', phone='+5198...', connected_at=...`.
8. UI ve `status='connected'` y muestra "Conectado · +51 ...".
9. La sesión queda persistida en `auth/<empresa_id>/`. Próximos arranques del bot reanudan sin pedir QR.

### Mensaje entrante de un cliente

1. Cliente final escribe a +51 987 654 321 (el WA del tenant cmejia).
2. Baileys del bot recibe `messages.upsert`.
3. Bot filtra: no `fromMe`, no grupo (`@g.us`), termina en `@s.whatsapp.net`.
4. Bot upsertea `conversaciones[empresa_id=cmejia, phone=+51...]` (crea si no existe, default `modo='AI'`).
5. Bot inserta el mensaje en `mensajes` con `role='user'`.
6. Bot re-lee la conversación para ver `modo` actual (puede haber cambiado a HUMAN entre tanto).
7. Si `modo='AI'`:
   - Bot lee últimos 20 mensajes ordenados ASC.
   - Bot mapea `role='human'` a `'assistant'` (los mensajes humanos del dashboard "salieron del lado del bot" desde el punto de vista del LLM).
   - Bot llama `POST /api/sales_chat` con `{empresa_id, phone, nombre, history}`.
   - Yoko ejecuta: arma system prompt con catálogo + reglas → llama OpenAI con tools de venta → devuelve `{reply}`.
   - Bot inserta `mensajes` con `role='assistant'`, contenido = reply.
   - Bot envía la reply vía Baileys → `sock.sendMessage(jid, {text: reply})`.
8. Si `modo='HUMAN'`: bot solo persiste el inbound. Nadie responde IA. Un humano debe responder desde el dashboard "Respuestas IA".

### Mensaje saliente humano (desde dashboard)

1. Usuario en Yoko, dashboard de Respuestas IA, modo HUMAN, escribe un mensaje.
2. UI llama `POST /api/mensajes` con `{conversacion_id, role='human', content}`.
3. `mensajes.py` inserta en `mensajes` Y en `outbox` con `sent=false`.
4. Bot polls outbox cada 2s, ve la fila, llama `WaSession.sendText(phone, content)` para ese tenant, marca `sent=true`.
5. WhatsApp del cliente recibe el mensaje "del" tenant.

---

## Troubleshooting

### Code 405 al conectar (`Stream Errored`)

Versión de Baileys vs WhatsApp protocol desactualizada. Solución: ya está manejada con `fetchLatestBaileysVersion()`. Si igualmente falla, actualizá `@whiskeysockets/baileys` a la última.

### Code 440 en loop (`connectionReplaced`)

Browser fingerprint custom. Verificá en `baileys-session.ts` que esté `Browsers.macOS('Desktop')`. Si persiste:
- En tu teléfono: Configuración → Dispositivos vinculados → borrá cualquier "Desktop" viejo de pruebas anteriores.
- Esperá 15s entre reintentos (ya está aplicado en el backoff).

### El QR no aparece en la UI

Posibles:
- Bot no está corriendo localmente. Levantalo con `npm run start`.
- Bot tiene error al escribir Airtable: revisá la consola, mirá el log de connection.update.
- El polling de la UI no está corriendo: hacer reload del navegador.

### "FATAL: Falta AIRTABLE_TOKEN..."

No se cargó el `.env`. Asegurate de:
- El archivo se llama exactamente `.env` (no `.env.local`, no `.env.txt`).
- Está en la raíz de `bot-service/`, no en `bot-service/src/`.
- No hay espacios alrededor del `=`.

### El bot se queda corriendo después de Ctrl+C

En Windows los procesos hijos a veces quedan. Cerralo con:
```powershell
tasklist | findstr tsx
taskkill /F /PID <pid>
```

### Modelo de OpenAI saturado (429)

Sucede si configuraste un modelo `:free` o tu cuota mensual se acabó. Recomendado: `gpt-4.1-mini-2025-04-14` (lo que ya usa Yoko).

---

## Deploy futuro a producción (cuando salga del modo PC-local)

Opciones recomendadas:
- **Hetzner CX11** (~US$4/mes) + EasyPanel
- **Railway** (~US$5/mes)
- **Cualquier VPS** con Node 20+

Volúmenes persistentes obligatorios:
- `/app/auth` → si lo perdés, todos los clientes deben re-escanear QR.
- `/app/.env` → el archivo de env vars (o usar el sistema de secrets del provider).

Procfile sugerido:
```
worker: npm run start
```

---

## Mejoras pendientes (v2)

- Soporte de imágenes salientes (enviar la foto del producto cuando el LLM lo recomienda).
- Ingesta de imágenes/audio entrantes con transcripción (visión multimodal).
- WebSocket en lugar de polling (UI más responsiva).
- Notificación push al vendedor cuando el LLM detecta intención fuerte de compra.
- Auto-toggle a HUMAN cuando el bot dice "te derivo con un asesor humano" (regex en handler).
- Encriptación at-rest de la sesión Baileys (`auth/`) — sensible si el VPS se compromete.
- Migración de Baileys a Meta Cloud API cuando el cliente pase a producción seria.
