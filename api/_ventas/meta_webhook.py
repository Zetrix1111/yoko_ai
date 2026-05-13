"""
api/_ventas/meta_webhook.py — endpoint webhook para WhatsApp Cloud API (Meta).

Dos handlers expuestos via /api/ventas?resource=whatsapp_webhook:

  GET   → verificación inicial (handshake) que Meta hace al configurar el
          webhook. Compara hub.verify_token con env y devuelve hub.challenge.
  POST  → mensajes entrantes del cliente. Valida firma HMAC, persiste,
          invoca cerebro de ventas, manda respuesta (fotos + texto) via
          Meta Cloud API.

El feature flag "esta empresa usa Meta" es implícito: si llega un
mensaje a un `phone_number_id` que NO está en `meta_connections` con
`activo=TRUE`, respondemos 200 OK silencioso y nada más. Las empresas
en canal Baileys siguen funcionando como antes vía `sales_chat_post`.

Multi-tenant: cada fila en `meta_connections` mapea
`phone_number_id → empresa_id + access_token`. El token se lee de
Airtable, no de env vars — un solo lugar para gestionar credenciales.
"""

import json
import os
import sys
import time
from collections import deque

from _lib import airtable_client
from _lib import meta_connections
from _lib import whatsapp_meta_client as meta
from _lib.airtable_client import AirtableError
from _ventas import chat as ventas_chat

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_TABLA_CONV = "conversaciones"
_TABLA_MSGS = "mensajes"

# Dedup in-memory de wamid (Meta message id). Si Vercel responde tarde
# por cold-start, Meta reintenta el mismo POST y el cerebro procesaría
# el mensaje dos veces (respuesta duplicada al cliente). Esta cache
# sobrevive mientras la lambda esté caliente — cold-start la resetea,
# pero la ventana de retry de Meta es de segundos, suficiente.
_PROCESSED_WAMIDS: deque = deque(maxlen=500)
_PROCESSED_SET: set = set()

# Mensaje genérico cuando el cerebro falla (OpenAI down, Airtable down).
# Va al cliente final por WhatsApp. NO exponemos detalle técnico.
_FALLBACK_REPLY = (
    "Disculpa, estoy con un problema técnico en este momento. "
    "Por favor, escríbeme de nuevo en unos minutos."
)


# ─────────────────────────────────────────────────────────────────────────
# GET: handshake de verificación con Meta
# ─────────────────────────────────────────────────────────────────────────

def meta_webhook_get(req) -> None:
    """
    Meta llama una vez (al configurar el webhook):
      GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...

    Si hub.verify_token matchea el env META_WEBHOOK_VERIFY_TOKEN,
    respondemos con hub.challenge en plain text (Meta lo necesita
    EXACTO, sin JSON wrapping).
    """
    qs = req._qs()
    mode = qs.get("hub.mode") or ""
    token = qs.get("hub.verify_token") or ""
    challenge = qs.get("hub.challenge") or ""

    expected = os.environ.get("META_WEBHOOK_VERIFY_TOKEN") or ""
    if not expected:
        print(
            "[meta_webhook] META_WEBHOOK_VERIFY_TOKEN no configurado — "
            "rechazando handshake.",
            file=sys.stderr,
        )
        return req._json(500, {"error": "Server misconfigured"})

    if mode == "subscribe" and token and token == expected and challenge:
        # Plain text response — Meta espera EXACTAMENTE el challenge.
        body = challenge.encode("utf-8")
        req.send_response(200)
        req.send_header("Content-Type", "text/plain; charset=utf-8")
        req.send_header("Content-Length", str(len(body)))
        req.end_headers()
        req.wfile.write(body)
        print("[meta_webhook] handshake OK", file=sys.stderr)
        return None

    print(
        f"[meta_webhook] handshake rechazado (mode={mode!r}, token_match="
        f"{token == expected})",
        file=sys.stderr,
    )
    return req._json(403, {"error": "Forbidden"})


# ─────────────────────────────────────────────────────────────────────────
# POST: mensajes entrantes
# ─────────────────────────────────────────────────────────────────────────

def meta_webhook_post(req) -> None:
    """
    Meta postea cada mensaje entrante. Estructura del payload:

      {
        "object": "whatsapp_business_account",
        "entry": [{
          "id": "<waba_id>",
          "changes": [{
            "value": {
              "messaging_product": "whatsapp",
              "metadata": {
                "display_phone_number": "...",
                "phone_number_id": "<el WABA al que escribieron>"
              },
              "contacts": [{"profile": {"name": "..."}, "wa_id": "<phone>"}],
              "messages": [{
                "from": "<phone del cliente>",
                "id": "<wamid>",
                "timestamp": "<unix>",
                "type": "text",
                "text": {"body": "Hola"}
              }]
            },
            "field": "messages"
          }]
        }]
      }

    Flujo:
      1. Validar firma HMAC.
      2. Resolver empresa por phone_number_id.
      3. Por cada mensaje: persistir user msg → process_message →
         enviar fotos + texto via Meta → persistir assistant msg.
      4. Responder 200 OK SIEMPRE (incluso ante errores parciales)
         para evitar retries que dupliquen mensajes.
    """
    # 1) Leer body raw (para validar firma) y signature header
    length = int(req.headers.get("Content-Length", 0))
    if length == 0:
        return req._json(400, {"error": "Empty body"})
    raw = req.rfile.read(length)
    sig_header = req.headers.get("X-Hub-Signature-256")

    app_secret = os.environ.get("META_APP_SECRET") or ""
    if not app_secret:
        print(
            "[meta_webhook] META_APP_SECRET no configurado — "
            "rechazando POST por seguridad.",
            file=sys.stderr,
        )
        return req._json(500, {"error": "Server misconfigured"})

    if not meta.verify_webhook_signature(raw, sig_header, app_secret):
        print("[meta_webhook] firma inválida o ausente — 401", file=sys.stderr)
        return req._json(401, {"error": "Invalid signature"})

    # 2) Parsear payload
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[meta_webhook] payload no es JSON: {e}", file=sys.stderr)
        return req._json(400, {"error": "Invalid JSON"})

    # 3) Procesar cada change. Errores parciales se loguean pero NO
    # interrumpen el loop ni el 200 final.
    for entry in (payload.get("entry") or []):
        for change in (entry.get("changes") or []):
            if change.get("field") != "messages":
                continue
            try:
                _process_change(change.get("value") or {})
            except Exception as e:
                print(
                    f"[meta_webhook] error procesando change: "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                )

    # SIEMPRE 200 a Meta. Si devolvemos 5xx, Meta reintenta y duplica.
    return req._json(200, {"ok": True})


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _process_change(value: dict) -> None:
    """
    Procesa un `entry.changes[].value` del webhook. Cada change puede
    traer múltiples messages.
    """
    # Meta envía 'statuses' (delivery/read/error) por el mismo webhook.
    # No son input del usuario — skip silencioso para no contaminar logs.
    if value.get("statuses") and not value.get("messages"):
        return

    metadata = value.get("metadata") or {}
    phone_number_id = (metadata.get("phone_number_id") or "").strip()
    if not phone_number_id:
        return

    # Resolver empresa via meta_connections.
    conn = meta_connections.get_by_phone_number_id(phone_number_id)
    if not conn:
        # El WABA no está mapeado a una empresa nuestra (o `activo=FALSE`).
        # Ignoramos silenciosamente — quizás es otro tenant o config legacy.
        print(
            f"[meta_webhook] phone_number_id={phone_number_id!r} sin "
            "fila activa en meta_connections; ignorando.",
            file=sys.stderr,
        )
        return

    empresa_id = conn.get("empresa_id")
    access_token = conn.get("access_token")
    if not empresa_id or not access_token:
        return

    # Resolver nombre desde contacts[].
    contacts = value.get("contacts") or []
    nombre = ""
    if contacts and isinstance(contacts[0], dict):
        profile = contacts[0].get("profile") or {}
        nombre = (profile.get("name") or "").strip()

    # Loop mensajes (Meta puede mandar batch, aunque normalmente es 1).
    for msg in (value.get("messages") or []):
        try:
            _handle_message(
                msg=msg,
                empresa_id=empresa_id,
                phone_number_id=phone_number_id,
                access_token=access_token,
                nombre=nombre,
            )
        except Exception as e:
            print(
                f"[meta_webhook] error en mensaje individual: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )


def _handle_message(
    msg: dict,
    empresa_id: str,
    phone_number_id: str,
    access_token: str,
    nombre: str,
) -> None:
    """Procesa UN mensaje entrante: persiste, invoca cerebro, responde."""
    msg_type = msg.get("type")
    if msg_type != "text":
        # v1 solo procesa texto. Otros tipos (image, audio, document) se
        # podrían soportar en v2 con transcripción/parsing.
        print(
            f"[meta_webhook] tipo de mensaje no soportado en v1: {msg_type}",
            file=sys.stderr,
        )
        return

    from_phone = (msg.get("from") or "").strip()
    text_body = ((msg.get("text") or {}).get("body") or "").strip()
    if not from_phone or not text_body:
        return

    # Dedup por wamid: si ya procesamos este id, ignorar (reintento Meta).
    wamid = (msg.get("id") or "").strip()
    if wamid:
        if wamid in _PROCESSED_SET:
            print(f"[meta_webhook] wamid duplicado, skip: {wamid}", file=sys.stderr)
            return
        if len(_PROCESSED_WAMIDS) == _PROCESSED_WAMIDS.maxlen:
            _PROCESSED_SET.discard(_PROCESSED_WAMIDS[0])
        _PROCESSED_WAMIDS.append(wamid)
        _PROCESSED_SET.add(wamid)

    # 1) Resolver/crear conversación
    conv_id = _ensure_conversation(empresa_id, from_phone, nombre)

    # 2) Persistir mensaje del user en `mensajes`
    _insert_mensaje(conv_id, empresa_id, "user", text_body)

    # 3) Invocar cerebro de ventas. El history viene puro de Airtable
    # (history_loader rearma todo) — el `history` param se usa para
    # merge defensivo si Airtable aún no tiene el último mensaje.
    last_user = [{"role": "user", "content": text_body}]
    try:
        result = ventas_chat.process_message(
            empresa_id, from_phone, nombre, last_user,
            channel="meta",
        )
        reply = result["reply"]
        media_urls = result.get("media_urls") or []
    except (OpenAIAPIError, AirtableError, Exception) as e:
        print(
            f"[meta_webhook] cerebro falló: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        reply = _FALLBACK_REPLY
        media_urls = []

    # 4) Mandar a Meta: primero imágenes (si hay), después texto.
    for url in media_urls:
        try:
            meta.send_image(phone_number_id, from_phone, url, None, access_token)
        except meta.MetaError as e:
            print(
                f"[meta_webhook] send_image falló para {url}: {e}",
                file=sys.stderr,
            )
            # Seguimos con las demás; el texto va igual.

    try:
        meta.send_text(phone_number_id, from_phone, reply, access_token)
    except meta.MetaError as e:
        # Si el texto falla, no podemos hacer mucho — el cliente no
        # recibe respuesta. Loguear y persistir el reply igual para
        # que quede registrado en el historial (importante para que el
        # próximo turno reconstruya bien el contexto).
        print(
            f"[meta_webhook] send_text falló: {e}",
            file=sys.stderr,
        )

    # 5) Persistir respuesta del bot en `mensajes` (aunque envío haya
    # fallado — sirve para que el próximo turno tenga continuidad).
    _insert_mensaje(conv_id, empresa_id, "assistant", reply)


def _ensure_conversation(empresa_id: str, phone: str, nombre: str) -> str:
    """
    Resuelve `conversacion_id` para (empresa_id, phone). Si no existe,
    la crea. Devuelve el recId.
    """
    formula = f"AND({{empresa_id}}='{empresa_id}', {{phone}}='{phone}')"
    try:
        rows = airtable_client.list_records(
            _TABLA_CONV, filter_formula=formula, max_records=1,
        )
    except AirtableError as e:
        print(
            f"[meta_webhook] no pude buscar conversación: {e}",
            file=sys.stderr,
        )
        raise

    if rows:
        return rows[0]["id"]

    # No existe → crear
    now = _now_iso()
    fields = {
        "empresa_id":      empresa_id,
        "phone":           phone,
        "nombre":          nombre or phone,
        "modo":            "AI",
        "last_message_at": now,
        "created_at":      now,
    }
    rec = airtable_client.create_record(_TABLA_CONV, fields)
    return rec["id"]


def _insert_mensaje(conv_id: str, empresa_id: str, role: str, content: str) -> None:
    """Inserta una fila en `mensajes`. Sin levantar si Airtable falla."""
    if not content:
        return
    fields = {
        "conversacion_id": conv_id,
        "empresa_id":      empresa_id,
        "role":            role,
        "content":         content,
        "created_at":      _now_iso(),
    }
    try:
        airtable_client.create_record(_TABLA_MSGS, fields)
    except AirtableError as e:
        print(
            f"[meta_webhook] no se pudo guardar mensaje ({role}): {e}",
            file=sys.stderr,
        )


def _now_iso() -> str:
    """ISO UTC timestamp, sin microsegundos."""
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
