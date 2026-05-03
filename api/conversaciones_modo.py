"""
api/conversaciones_modo.py — togglea el modo de una conversación entre AI y HUMAN.

POST con body:
  { "conversacion_id": "recXXX", "modo": "AI" | "HUMAN" }

Cuando una conversación está en modo HUMAN, el bot-baileys NO la responde
con IA. Solo persiste los mensajes entrantes en la tabla `mensajes` y
queda esperando que un humano (desde el dashboard) responda.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                      # noqa: E402
from _lib.airtable_client import AirtableError        # noqa: E402


_TABLA = "conversaciones"


def _ventas_base() -> str:
    return airtable_client.get_ventas_base_id()


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            conv_id = (body.get("conversacion_id") or "").strip()
            modo = (body.get("modo") or "").strip().upper()

            if not conv_id:
                return self._json(400, {"error": "Falta conversacion_id."})
            if modo not in ("AI", "HUMAN"):
                return self._json(400, {"error": "modo debe ser 'AI' o 'HUMAN'."})

            rec = airtable_client.update_record(
                _TABLA, conv_id, {"modo": modo}, base_id=_ventas_base(),
            )
            return self._json(200, {
                "ok":   True,
                "id":   rec.get("id"),
                "modo": rec.get("fields", {}).get("modo"),
            })

        except AirtableError as e:
            print(f"[conversaciones_modo] AirtableError: {e}", file=sys.stderr)
            return self._json(502, {"error": "No se pudo actualizar el modo."})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido."})
        except Exception as e:
            print(f"[conversaciones_modo] Error: {type(e).__name__}: {e}", file=sys.stderr)
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
