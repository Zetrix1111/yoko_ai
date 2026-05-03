"""
api/conversaciones.py — CRUD de conversaciones del módulo Ventas Inteligentes.

Tabla Airtable: `conversaciones` (en la base default AIRTABLE_BASE_ID).
Multi-tenant via columna empresa_id.

Métodos:
  GET                 → listar conversaciones del tenant (ordenadas por last_message_at desc)
  GET ?id=recXXX      → obtener una conversación por ID
  DELETE ?id=recXXX   → eliminar conversación + sus mensajes asociados
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                      # noqa: E402
from _lib.airtable_client import AirtableError        # noqa: E402


_TABLA = "conversaciones"
_TABLA_MENSAJES = "mensajes"
_FALLBACK_TENANT = "cmejia"


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


def _normalize(rec: dict) -> dict:
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


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            rec_id = (qs.get("id") or [None])[0]

            if rec_id:
                rec = airtable_client.get_record(_TABLA, rec_id)
                return self._json(200, {"conversacion": _normalize(rec)})

            tenant = _tenant_id()
            formula = f"{{empresa_id}}='{tenant}'"
            records = airtable_client.list_records(
                _TABLA, filter_formula=formula, max_records=100,
            )
            convs = [_normalize(r) for r in records]
            # Ordenar por last_message_at desc (más reciente arriba). Airtable no
            # lo hace via API sin View; lo hacemos en Python.
            convs.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
            return self._json(200, {"conversaciones": convs})

        except AirtableError as e:
            print(f"[conversaciones] AirtableError GET: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo consultar Airtable."})
        except Exception as e:
            print(f"[conversaciones] Error GET: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def do_DELETE(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            rec_id = (qs.get("id") or [None])[0]
            if not rec_id:
                return self._json(400, {"error": "Falta query param 'id'."})

            # Borrar mensajes asociados primero
            try:
                msgs = airtable_client.list_records(
                    _TABLA_MENSAJES,
                    filter_formula=f"{{conversacion_id}}='{rec_id}'",
                    max_records=100,
                )
                for m in msgs:
                    airtable_client.delete_record(_TABLA_MENSAJES, m["id"])
            except AirtableError as e:
                print(f"[conversaciones] No se pudo borrar mensajes: {e}", file=sys.stderr)

            airtable_client.delete_record(_TABLA, rec_id)
            return self._json(200, {"ok": True, "id": rec_id})

        except AirtableError as e:
            print(f"[conversaciones] AirtableError DELETE: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo eliminar."})
        except Exception as e:
            print(f"[conversaciones] Error DELETE: {type(e).__name__}: {e}", file=sys.stderr)
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
