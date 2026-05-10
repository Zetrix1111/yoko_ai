"""
api/_lib/_config.py

Constantes operacionales del cerebro Claude Managed Agents (Yoko).
Centraliza TTLs, timeouts y caps que antes estaban duplicados en
varios módulos. Si querés ajustar comportamiento (ej: bajar TTL para
ahorrar costo en pausas largas, subir el cap de turnos para flujos
multi-tool), tocás acá un solo valor.

Estas constantes son SOLO para el flujo Managed Agents (handler_managed,
handler_worker, yoko_cart_store, yoko_session_store, yoko_task_store).
NO afectan al flujo legacy de OpenAI (`_yoko/handler.py`) ni al módulo
de ventas — esos cerebros tienen sus propias constantes.

El nombre con underscore inicial (`_config.py`) sigue la convención del
resto de archivos privados del paquete `_lib/`. No es un módulo público.
"""

# ─────────────────────────────────────────────────────────────────────────
# TTLs (segundos)
# ─────────────────────────────────────────────────────────────────────────

# TTL deslizante para session_id cacheado en KV y para el carrito de
# archivos. Mismo valor para que session y cart vivan en sincronía: si
# expira la sesión de Anthropic, el cart asociado tiene la misma vida.
# Mientras el usuario chatea, cada acceso renueva el TTL → conversación
# infinitamente larga sin perder contexto. Si el usuario pausa más que
# este valor, próximo turn crea sesión nueva (con su contexto inicial).
SESSION_TTL_SECONDS = 4 * 60 * 60   # 4 horas

# TTL del task async mientras está pending/running. Es un techo de
# seguridad: si el worker muere sin marcar done/error, el task expira
# y el frontend ve "tiempo agotado" en su polling. Debe ser > maxDuration
# de la function worker en Vercel (300s con fluid compute) + slack.
TASK_TTL_ACTIVE_SECONDS = 5 * 60    # 5 minutos

# TTL del task una vez en done/error. Ventana corta para que el último
# poll del frontend lea el resultado y descarte. Acortar reduce basura
# en KV; alargar permite recuperación si el polling tarda en llegar.
TASK_TTL_FINAL_SECONDS = 60         # 1 minuto


# ─────────────────────────────────────────────────────────────────────────
# Timeouts (segundos)
# ─────────────────────────────────────────────────────────────────────────

# Timeout HTTP del loopback orquestador → /api/facturas?action=...
# Procesar 50 PDFs con OCR/Vision puede tardar bastante; 120s es generoso.
TOOL_HTTP_TIMEOUT_SECONDS = 120     # 2 minutos


# ─────────────────────────────────────────────────────────────────────────
# Caps / safety limits
# ─────────────────────────────────────────────────────────────────────────

# Máximo de iteraciones del loop "agent emite tool_use → orchestrator
# ejecuta → submit result → agent emite otro tool_use" en un mismo turno.
# Si el agent se cuelga pidiendo herramientas en cascada (bug raro), este
# cap previene loops infinitos. 8 cubre los flujos legítimos (procesar +
# generar excel + recuperar + 1-2 retries) con margen.
MAX_TURNS_PER_RUN = 8
