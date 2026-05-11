"""
api/_ventas/_lib/history_loader.py

Reconstruye el history conversacional del cliente desde la tabla
`mensajes` de Airtable, evitando depender del history truncado que
manda bot-baileys (servicio externo con cap fijo a 20 mensajes, fuera
de nuestro control). El backend pasa a ser la fuente de verdad del
contexto que ve el LLM.

Separación entre clientes:
  - Cada cliente WhatsApp tiene una sola fila en `conversaciones`
    (clave única: empresa_id + phone).
  - Cada mensaje apunta a su conversación vía `conversacion_id` (FK).
  - El loader busca la conv por (empresa_id, phone) → obtiene su
    rec_id → solo carga mensajes con ese conv_id. Cero mezcla entre
    clientes distintos.

API pública:
  - `load_history(empresa_id, phone) -> list[dict] | None`
  - `merge_with_latest_user_message(airtable, body) -> list[dict]`
"""

import sys

from _lib import airtable_client
from _lib.airtable_client import AirtableError


_TABLA_CONV = "conversaciones"
_TABLA_MSGS = "mensajes"

# Últimos N mensajes (user + assistant combinados) que cargamos del
# historial. Compromiso entre memoria útil y costo de OpenAI:
# conversaciones de venta WhatsApp típicas son <20 turnos; >50 ya es
# raro y casi siempre indica que toca derivar a humano.
_HISTORY_CAP = 50


def load_history(empresa_id: str, phone: str) -> list[dict] | None:
    """
    Carga los últimos _HISTORY_CAP mensajes de la conversación
    (empresa_id, phone), ordenados ASC por created_at, en formato OpenAI
    [{role, content}].

    Devuelve None si:
      - falta phone o empresa_id
      - no existe la conversación en Airtable
      - error de red / 5xx (caller debe caer al history del body)

    NO levanta excepciones: cualquier falla → None + log a stderr. El
    caller usa eso como señal de fallback al history que mandó el bot.
    """
    if not empresa_id or not phone:
        return None

    try:
        # 1) Buscar conversacion_id por (empresa_id, phone).
        convs = airtable_client.list_records(
            _TABLA_CONV,
            filter_formula=f"AND({{empresa_id}}='{empresa_id}', {{phone}}='{phone}')",
            max_records=1,
        )
        if not convs:
            return None
        conv_id = convs[0].get("id")
        if not conv_id:
            return None

        # 2) Cargar mensajes de esa conversación. max_records=100 cubre
        #    cap=50 con holgura; si en el futuro hay conversaciones de
        #    >100 mensajes, tocaría paginar.
        rows = airtable_client.list_records(
            _TABLA_MSGS,
            filter_formula=f"{{conversacion_id}}='{conv_id}'",
            max_records=100,
        )

        # 3) Normalizar + filtrar + ordenar por timestamp.
        msgs: list[dict] = []
        for rec in rows:
            f = rec.get("fields", {})
            role = f.get("role")
            content = f.get("content")
            if role not in ("user", "assistant") or not content:
                continue
            msgs.append({
                "role":    role,
                "content": content,
                "_ts":     f.get("created_at") or "",
            })
        msgs.sort(key=lambda m: m["_ts"])

        # 4) Tomar últimos _HISTORY_CAP y stripear _ts (no va a OpenAI).
        tail = msgs[-_HISTORY_CAP:]
        return [{"role": m["role"], "content": m["content"]} for m in tail]
    except AirtableError as e:
        print(
            f"[history_loader] Fallback al body history. Airtable error: {e}",
            file=sys.stderr,
        )
        return None


def merge_with_latest_user_message(
    airtable_history: list[dict],
    body_history: list[dict],
) -> list[dict]:
    """
    Defensivo contra el race condition donde bot-baileys hace POST al
    chat ANTES de guardar el último user message en Airtable.

    Si el último mensaje del body es role=user y NO está al final del
    airtable_history, lo agregamos al final. Si ya está (bot guardó
    antes), no duplicamos.
    """
    if not body_history:
        return airtable_history

    last_body = body_history[-1]
    if not isinstance(last_body, dict):
        return airtable_history
    if last_body.get("role") != "user":
        return airtable_history

    body_content = (last_body.get("content") or "").strip()
    if not body_content:
        return airtable_history

    # ¿El último mensaje del Airtable history ya es este mismo del user?
    if airtable_history:
        last_air = airtable_history[-1]
        if (
            last_air.get("role") == "user"
            and (last_air.get("content") or "").strip() == body_content
        ):
            return airtable_history

    return airtable_history + [{"role": "user", "content": body_content}]
