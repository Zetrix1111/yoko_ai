"""
api/wa.py — estado de sesión WhatsApp + comandos connect/disconnect.

Tabla: `wa_sessions` (1 row por tenant) en la base default AIRTABLE_BASE_ID.

Métodos:
  GET  ?empresa_id=cmejia              → estado de sesión + qr_string raw
  POST ?action=connect    body: {empresa_id}
                                       → upsert wa_sessions con status='disconnected'
                                         (señal al bot para que arranque la sesión)
  POST ?action=disconnect body: {empresa_id}
                                       → marca status='disconnected' + borra qr/phone
                                         (el bot detecta y mata la sesión)

El frontend hace polling de GET cada 2s mientras status != 'connected'.
El QR se renderiza en el cliente (React) a partir del qr_string raw.
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


_TABLA = "wa_sessions"
_FALLBACK_TENANT = "cmejia"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_session(empresa_id: str) -> dict | None:
    """Devuelve la row de wa_sessions del tenant o None si no existe."""
    formula = f"{{empresa_id}}='{empresa_id}'"
    records = airtable_client.list_records(
        _TABLA, filter_formula=formula, max_records=1,
    )
    return records[0] if records else None


def _normalize(rec: dict | None) -> dict | None:
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


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            empresa_id = (qs.get("empresa_id") or [os.environ.get("TENANT_ID") or _FALLBACK_TENANT])[0]

            rec = _find_session(empresa_id)
            if rec is None:
                # No hay row → tenant nunca intentó conectar
                return self._json(200, {
                    "session": {
                        "empresa_id": empresa_id,
                        "status":     "disconnected",
                        "qr_string":  None,
                        "phone":      None,
                    },
                })
            return self._json(200, {"session": _normalize(rec)})

        except AirtableError as e:
            print(f"[wa] AirtableError GET: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo consultar Airtable."})
        except Exception as e:
            print(f"[wa] Error GET: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def do_POST(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            action = (qs.get("action") or [None])[0]
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            empresa_id = (body.get("empresa_id") or "").strip()
            if not empresa_id:
                empresa_id = os.environ.get("TENANT_ID") or _FALLBACK_TENANT

            if action == "connect":
                return self._do_connect(empresa_id)
            if action == "disconnect":
                return self._do_disconnect(empresa_id)
            return self._json(400, {"error": "action debe ser 'connect' o 'disconnect'."})

        except AirtableError as e:
            print(f"[wa] AirtableError POST: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo escribir en Airtable."})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido."})
        except Exception as e:
            print(f"[wa] Error POST: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Helpers de acción ────────────────────────────────────────────────

    def _do_connect(self, empresa_id: str):
        """
        Señal al bot: 'el cliente quiere conectar este tenant'.
        Upsert wa_sessions con status='disconnected' (el bot polea esa tabla;
        cuando ve una row con status disconnected y no la tiene en memoria,
        arranca un nuevo socket Baileys para ese tenant).
        """
        existing = _find_session(empresa_id)
        fields = {
            "empresa_id": empresa_id,
            "status":     "disconnected",
            "qr_string":  "",
            "phone":      "",
        }
        if existing:
            rec = airtable_client.update_record(_TABLA, existing["id"], fields)
        else:
            rec = airtable_client.create_record(_TABLA, fields)
        return self._json(200, {"session": _normalize(rec)})

    def _do_disconnect(self, empresa_id: str):
        """Bota la sesión: setea status=disconnected y limpia qr/phone."""
        existing = _find_session(empresa_id)
        if not existing:
            return self._json(200, {"ok": True, "note": "Tenant sin sesión."})
        rec = airtable_client.update_record(
            _TABLA, existing["id"],
            {"status": "disconnected", "qr_string": "", "phone": ""},
        )
        return self._json(200, {"session": _normalize(rec)})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
