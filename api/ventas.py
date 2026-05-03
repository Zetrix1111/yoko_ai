"""
api/ventas.py — endpoint dispatcher consolidado del módulo Ventas Inteligentes.

Vercel Hobby plan tiene un cap de 12 serverless functions. Para no superarlo,
todos los endpoints relacionados a ventas viven aquí y se diferencian por el
query param `?resource=`:

  resource=wa
    GET                              → estado de la sesión WA del tenant
    POST   ?action=connect           → upsert wa_sessions con status='qr'
    POST   ?action=disconnect        → marca status='disconnected'

  resource=conversaciones
    GET                              → lista del tenant (TENANT_ID env)
    GET    ?id=recXXX                → una conversación por ID
    DELETE ?id=recXXX                → borra conversación + sus mensajes

  resource=mensajes
    GET    ?conversacion_id=recXXX   → historial ordenado ASC
    POST   body: {conversacion_id, role, content}
                                     → INSERT en mensajes (+ outbox si role=human)

  resource=conversaciones_modo
    POST   body: {conversacion_id, modo}   → toggle AI/HUMAN

  resource=sales_chat
    POST   body: {empresa_id, phone, nombre, history}
                                     → llama OpenAI con tools de venta + catálogo
                                     → devuelve {reply}

Cada bloque está marcado con un comentario de sección. El cuerpo de cada
"sub-handler" es una función _<resource>_<method>(self) que escribe la
response usando self._json (heredado del HTTP handler).
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                         # noqa: E402
from _lib import config_loader                           # noqa: E402
from _lib import openai_client                           # noqa: E402
from _lib import prompt_builder                          # noqa: E402
from _lib.airtable_client import AirtableError           # noqa: E402
from _lib.tools import ventas as ventas_tools            # noqa: E402

try:
    from openai import APIError as OpenAIAPIError        # noqa: E402
except ImportError:
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_FALLBACK_TENANT = "cmejia"


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            r = self._resource()
            if r == "wa":             return _wa_get(self)
            if r == "conversaciones": return _conversaciones_get(self)
            if r == "mensajes":       return _mensajes_get(self)
            return self._json(400, {"error": f"resource '{r}' no soporta GET."})
        except Exception as e:
            return self._handle_unhandled(e)

    def do_POST(self):
        try:
            r = self._resource()
            if r == "wa":                  return _wa_post(self)
            if r == "mensajes":            return _mensajes_post(self)
            if r == "conversaciones_modo": return _modo_post(self)
            if r == "sales_chat":          return _sales_chat_post(self)
            return self._json(400, {"error": f"resource '{r}' no soporta POST."})
        except Exception as e:
            return self._handle_unhandled(e)

    def do_DELETE(self):
        try:
            r = self._resource()
            if r == "conversaciones": return _conversaciones_delete(self)
            return self._json(400, {"error": f"resource '{r}' no soporta DELETE."})
        except Exception as e:
            return self._handle_unhandled(e)

    # ── Helpers de instancia ────────────────────────────────────────────

    def _resource(self) -> str:
        qs = parse_qs(urlparse(self.path).query)
        return (qs.get("resource") or [""])[0]

    def _qs(self) -> dict:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_unhandled(self, e: Exception):
        print(f"[ventas] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
        return self._json(500, {"error": "Error interno del servidor."})

    def log_message(self, *args):
        pass


# ─────────────────────────────────────────────────────────────────────────
# resource=wa  (sesión WhatsApp)
# ─────────────────────────────────────────────────────────────────────────

_TABLA_WA = "wa_sessions"


def _wa_find_session(empresa_id: str) -> dict | None:
    formula = f"{{empresa_id}}='{empresa_id}'"
    records = airtable_client.list_records(
        _TABLA_WA, filter_formula=formula, max_records=1,
    )
    return records[0] if records else None


def _wa_normalize(rec: dict | None) -> dict | None:
    if not rec:
        return None
    f = rec.get("fields", {})
    return {
        "id":            rec.get("id"),
        "empresa_id":    f.get("empresa_id"),
        "status":        f.get("status", "disconnected"),
        "qr_string":     f.get("qr_string"),
        "phone":         f.get("phone"),
        "connected_at":  f.get("connected_at"),
        "last_seen_at":  f.get("last_seen_at"),
    }


def _wa_get(self):
    try:
        qs = self._qs()
        empresa_id = qs.get("empresa_id") or _tenant_id()
        rec = _wa_find_session(empresa_id)
        if rec is None:
            return self._json(200, {"session": {
                "empresa_id": empresa_id,
                "status":     "disconnected",
                "qr_string":  None,
                "phone":      None,
            }})
        return self._json(200, {"session": _wa_normalize(rec)})
    except AirtableError as e:
        print(f"[ventas/wa] AirtableError GET: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo consultar Airtable."})


def _wa_post(self):
    try:
        qs = self._qs()
        action = qs.get("action")
        body = self._read_body()
        empresa_id = (body.get("empresa_id") or "").strip() or _tenant_id()

        if action == "connect":
            existing = _wa_find_session(empresa_id)
            fields = {
                "empresa_id": empresa_id,
                "status":     "qr",
                "qr_string":  "",
                "phone":      "",
            }
            if existing:
                rec = airtable_client.update_record(_TABLA_WA, existing["id"], fields)
            else:
                rec = airtable_client.create_record(_TABLA_WA, fields)
            return self._json(200, {"session": _wa_normalize(rec)})

        if action == "disconnect":
            existing = _wa_find_session(empresa_id)
            if not existing:
                return self._json(200, {"ok": True, "note": "Tenant sin sesión."})
            rec = airtable_client.update_record(
                _TABLA_WA, existing["id"],
                {"status": "disconnected", "qr_string": "", "phone": ""},
            )
            return self._json(200, {"session": _wa_normalize(rec)})

        return self._json(400, {"error": "action debe ser 'connect' o 'disconnect'."})
    except AirtableError as e:
        print(f"[ventas/wa] AirtableError POST: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo escribir en Airtable."})
    except json.JSONDecodeError:
        return self._json(400, {"error": "JSON inválido."})


# ─────────────────────────────────────────────────────────────────────────
# resource=conversaciones
# ─────────────────────────────────────────────────────────────────────────

_TABLA_CONV = "conversaciones"
_TABLA_MSGS = "mensajes"
_TABLA_OUTBOX = "outbox"


def _conv_normalize(rec: dict) -> dict:
    f = rec.get("fields", {})
    return {
        "id":              rec.get("id"),
        "empresa_id":      f.get("empresa_id"),
        "phone":           f.get("phone"),
        "nombre":          f.get("nombre"),
        "modo":            f.get("modo", "AI"),
        "last_message_at": f.get("last_message_at"),
        "created_at":      f.get("created_at"),
    }


def _conversaciones_get(self):
    try:
        qs = self._qs()
        rec_id = qs.get("id")
        if rec_id:
            rec = airtable_client.get_record(_TABLA_CONV, rec_id)
            return self._json(200, {"conversacion": _conv_normalize(rec)})

        tenant = _tenant_id()
        formula = f"{{empresa_id}}='{tenant}'"
        records = airtable_client.list_records(_TABLA_CONV, filter_formula=formula, max_records=100)
        convs = [_conv_normalize(r) for r in records]
        convs.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
        return self._json(200, {"conversaciones": convs})
    except AirtableError as e:
        print(f"[ventas/conversaciones] GET: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo consultar Airtable."})


def _conversaciones_delete(self):
    try:
        qs = self._qs()
        rec_id = qs.get("id")
        if not rec_id:
            return self._json(400, {"error": "Falta query param 'id'."})
        # Borrar mensajes asociados primero (best-effort)
        try:
            msgs = airtable_client.list_records(
                _TABLA_MSGS,
                filter_formula=f"{{conversacion_id}}='{rec_id}'",
                max_records=100,
            )
            for m in msgs:
                airtable_client.delete_record(_TABLA_MSGS, m["id"])
        except AirtableError as e:
            print(f"[ventas/conversaciones] No se pudo borrar mensajes: {e}", file=sys.stderr)

        airtable_client.delete_record(_TABLA_CONV, rec_id)
        return self._json(200, {"ok": True, "id": rec_id})
    except AirtableError as e:
        print(f"[ventas/conversaciones] DELETE: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo eliminar."})


# ─────────────────────────────────────────────────────────────────────────
# resource=mensajes
# ─────────────────────────────────────────────────────────────────────────

def _msg_normalize(rec: dict) -> dict:
    f = rec.get("fields", {})
    # conversacion_id es Single line text. Si por algún motivo viene como
    # array (ej. el campo se cambió a Linked Record después), tomamos el primero.
    conv = f.get("conversacion_id")
    if isinstance(conv, list) and conv:
        conv = conv[0]
    return {
        "id":              rec.get("id"),
        "conversacion_id": conv,
        "empresa_id":      f.get("empresa_id"),
        "role":            f.get("role"),
        "content":         f.get("content", ""),
        "created_at":      f.get("created_at"),
    }


def _mensajes_get(self):
    try:
        qs = self._qs()
        conv_id = qs.get("conversacion_id")
        if not conv_id:
            return self._json(400, {"error": "Falta conversacion_id."})
        # Text field → match directo
        formula = f"{{conversacion_id}}='{conv_id}'"
        records = airtable_client.list_records(_TABLA_MSGS, filter_formula=formula, max_records=100)
        mensajes = [_msg_normalize(r) for r in records]
        mensajes.sort(key=lambda m: m.get("created_at") or "")
        return self._json(200, {"mensajes": mensajes})
    except AirtableError as e:
        print(f"[ventas/mensajes] GET: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo consultar Airtable."})


def _mensajes_post(self):
    try:
        body = self._read_body()
        conv_id = (body.get("conversacion_id") or "").strip()
        role = (body.get("role") or "human").strip()
        content = (body.get("content") or "").strip()

        if not conv_id:
            return self._json(400, {"error": "Falta conversacion_id."})
        if not content:
            return self._json(400, {"error": "Falta content."})
        if role not in ("user", "assistant", "human"):
            return self._json(400, {"error": "role debe ser user|assistant|human."})

        # Cargar conversación para obtener empresa_id + phone (para outbox)
        conv_rec = airtable_client.get_record(_TABLA_CONV, conv_id)
        conv_f = conv_rec.get("fields", {})
        empresa_id = conv_f.get("empresa_id")
        phone = conv_f.get("phone")
        if not empresa_id or not phone:
            return self._json(400, {"error": "Conversación sin empresa_id o phone."})

        now = _now_iso()

        # conversacion_id es Single line text → string, no array
        msg_rec = airtable_client.create_record(_TABLA_MSGS, {
            "conversacion_id": conv_id,
            "empresa_id":      empresa_id,
            "role":            role,
            "content":         content,
            "created_at":      now,
        })

        if role == "human":
            airtable_client.create_record(_TABLA_OUTBOX, {
                "conversacion_id": conv_id,
                "empresa_id":      empresa_id,
                "phone":           phone,
                "content":         content,
                "sent":            False,
                "created_at":      now,
            })

        try:
            airtable_client.update_record(_TABLA_CONV, conv_id, {"last_message_at": now})
        except AirtableError as e:
            print(f"[ventas/mensajes] No se actualizó last_message_at: {e}", file=sys.stderr)

        return self._json(200, {"mensaje": _msg_normalize(msg_rec)})
    except AirtableError as e:
        print(f"[ventas/mensajes] POST: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo guardar el mensaje."})
    except json.JSONDecodeError:
        return self._json(400, {"error": "JSON inválido."})


# ─────────────────────────────────────────────────────────────────────────
# resource=conversaciones_modo
# ─────────────────────────────────────────────────────────────────────────

def _modo_post(self):
    try:
        body = self._read_body()
        conv_id = (body.get("conversacion_id") or "").strip()
        modo = (body.get("modo") or "").strip().upper()

        if not conv_id:
            return self._json(400, {"error": "Falta conversacion_id."})
        if modo not in ("AI", "HUMAN"):
            return self._json(400, {"error": "modo debe ser 'AI' o 'HUMAN'."})

        rec = airtable_client.update_record(_TABLA_CONV, conv_id, {"modo": modo})
        return self._json(200, {
            "ok":   True,
            "id":   rec.get("id"),
            "modo": rec.get("fields", {}).get("modo"),
        })
    except AirtableError as e:
        print(f"[ventas/modo] POST: {e}", file=sys.stderr)
        return self._json(502, {"error": "No se pudo actualizar el modo."})
    except json.JSONDecodeError:
        return self._json(400, {"error": "JSON inválido."})


# ─────────────────────────────────────────────────────────────────────────
# resource=sales_chat — llamado por bot-baileys, NO por la UI
# ─────────────────────────────────────────────────────────────────────────

_REQUIRED_ENV_SALES = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")


def _sales_chat_post(self):
    try:
        body = self._read_body()

        missing = [k for k in _REQUIRED_ENV_SALES if not os.environ.get(k)]
        if missing:
            print(f"[ventas/sales_chat] Faltan env vars: {missing}", file=sys.stderr)
            return self._json(500, {"error": "Configuración del servidor incompleta."})

        empresa_id = (body.get("empresa_id") or "").strip()
        history = body.get("history") or []
        if not empresa_id:
            return self._json(400, {"error": "Falta 'empresa_id'."})
        if not isinstance(history, list) or not history:
            return self._json(400, {"error": "Falta 'history' o está vacío."})

        sender = {
            "phone":  (body.get("phone") or "").strip(),
            "nombre": (body.get("nombre") or "").strip(),
        }

        # Cargar productos del tenant (catálogo para el prompt)
        try:
            productos_result = ventas_tools.consultar_productos(
                {"solo_disponibles": False},
                {"empresa_id": empresa_id},
            )
        except AirtableError as e:
            print(f"[ventas/sales_chat] AirtableError productos: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo cargar el catálogo."})

        productos = productos_result.get("productos", [])

        # Cargar config completa (empresa.info_extendida + ventas.*).
        # Si Airtable falla, seguimos con un dict mínimo: el agente responde igual,
        # solo sin los bloques opcionales. NO devolvemos 502.
        try:
            full_config = config_loader.load_full_config()
        except AirtableError as e:
            print(f"[ventas/sales_chat] Config dinámica no disponible: {e}", file=sys.stderr)
            full_config = {"empresa": {}, "ventas": {}}
        except Exception as e:
            print(f"[ventas/sales_chat] Error cargando config: {type(e).__name__}: {e}", file=sys.stderr)
            full_config = {"empresa": {}, "ventas": {}}

        empresa_full = full_config.get("empresa") or {}

        # Desde el paso 6: Airtable (Config_Empresa) es la fuente de verdad.
        # El body solo se usa como fallback por si el bot llama antes de que
        # la fila exista en Airtable.
        config = {
            "empresa": {
                "id":               empresa_id,
                "name":             empresa_full.get("name") or (body.get("name") or "").strip(),
                "razon_social":     empresa_full.get("razon_social") or (body.get("razon_social") or "").strip(),
                "ruc":              empresa_full.get("ruc") or (body.get("ruc") or "").strip(),
                "sistema_contable": empresa_full.get("sistema_contable") or (body.get("sistema_contable") or "").strip(),
                "info_extendida":   empresa_full.get("info_extendida", {}),
            },
            "ventas": full_config.get("ventas", {}),
        }

        try:
            system = prompt_builder.build_system_prompt(
                config, user=None,
                extra_context={"modo": "ventas", "productos": productos, "sender": sender},
            )
        except Exception as e:
            print(f"[ventas/sales_chat] Error armando prompt: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno armando prompt."})

        try:
            result = openai_client.run_chat(
                system_prompt=system,
                messages=history,
                tools=ventas_tools.VENTAS_TOOLS_OPENAI,
                context={"empresa_id": empresa_id, "sender": sender},
                executor=ventas_tools.execute_ventas_tool,
                max_iterations=4,
            )
        except OpenAIAPIError as e:
            print(f"[ventas/sales_chat] OpenAI API error: {e}", file=sys.stderr)
            return self._json(502, {"error": "Error del servicio IA."})
        except AirtableError as e:
            print(f"[ventas/sales_chat] AirtableError run_chat: {e}", file=sys.stderr)
            return self._json(502, {"error": "Error consultando catálogo."})

        reply = (result.get("text") or "").strip()
        if not reply:
            reply = "Disculpa, no entendí bien tu mensaje. ¿Podrías repetirlo?"

        return self._json(200, {"reply": reply})
    except json.JSONDecodeError:
        return self._json(400, {"error": "JSON inválido."})
