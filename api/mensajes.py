"""
api/mensajes.py — historial + envío de mensajes humanos.

Tabla: `mensajes` (en la base default AIRTABLE_BASE_ID).

Métodos:
  GET ?conversacion_id=recXXX   → historial completo (orden ASC)
  POST                          → INSERT mensaje + (si role=human) INSERT en outbox
                                  Body: {conversacion_id, role: 'human', content}

NOTA: El bot-baileys NO usa este endpoint. Escribe directamente en Airtable
mensajes (role=user para inbound, role=assistant para reply de IA).
Este endpoint es para el dashboard "Respuestas IA": cuando el usuario
desde Yoko UI escribe un mensaje en modo HUMAN, lo persistimos en mensajes
Y lo encolamos en outbox para que el bot lo envíe vía Baileys.
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

from _lib import airtable_client                      # noqa: E402
from _lib.airtable_client import AirtableError        # noqa: E402


_TABLA_MSGS = "mensajes"
_TABLA_CONV = "conversaciones"
_TABLA_OUTBOX = "outbox"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_msg(rec: dict) -> dict:
    f = rec.get("fields", {})
    # Airtable Linked field viene como [recId]; aplanamos
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


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            conv_id = (qs.get("conversacion_id") or [None])[0]
            if not conv_id:
                return self._json(400, {"error": "Falta conversacion_id."})

            # Linked records en Airtable se filtran con FIND sobre el ID
            formula = f"FIND('{conv_id}', ARRAYJOIN({{conversacion_id}}))"
            records = airtable_client.list_records(
                _TABLA_MSGS, filter_formula=formula, max_records=100,
            )
            mensajes = [_normalize_msg(r) for r in records]
            mensajes.sort(key=lambda m: m.get("created_at") or "")
            return self._json(200, {"mensajes": mensajes})

        except AirtableError as e:
            print(f"[mensajes] AirtableError GET: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo consultar Airtable."})
        except Exception as e:
            print(f"[mensajes] Error GET: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

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

            # 1) Insert mensaje
            msg_rec = airtable_client.create_record(
                _TABLA_MSGS,
                {
                    "conversacion_id": [conv_id],
                    "empresa_id":      empresa_id,
                    "role":            role,
                    "content":         content,
                    "created_at":      now,
                },
            )

            # 2) Si es human, encolar en outbox para que el bot lo envíe
            if role == "human":
                airtable_client.create_record(
                    _TABLA_OUTBOX,
                    {
                        "conversacion_id": [conv_id],
                        "empresa_id":      empresa_id,
                        "phone":           phone,
                        "content":         content,
                        "sent":            False,
                        "created_at":      now,
                    },
                )

            # 3) Actualizar last_message_at en la conversación
            try:
                airtable_client.update_record(
                    _TABLA_CONV, conv_id,
                    {"last_message_at": now},
                )
            except AirtableError as e:
                print(f"[mensajes] No se actualizó last_message_at: {e}", file=sys.stderr)

            return self._json(200, {"mensaje": _normalize_msg(msg_rec)})

        except AirtableError as e:
            print(f"[mensajes] AirtableError POST: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo guardar el mensaje."})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido."})
        except Exception as e:
            print(f"[mensajes] Error POST: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
