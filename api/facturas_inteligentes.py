"""
api/facturas_inteligentes.py
Endpoint del módulo "Facturas Inteligentes".
Stub inicial: recibe JSON, valida DNI, responde OK.
TODO: reemplazar el eco por lógica real.
"""

from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            dni = str(body.get("dni", "")).strip()
            if not dni.isdigit() or len(dni) != 8:
                return self._json(400, {"error": "DNI inválido."})

            # TODO: conectar con Make / Airtable
            return self._json(200, {
                "ok": True,
                "modulo": "facturas_inteligentes",
                "received": body,
            })

        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido."})
        except Exception as e:
            print(f"[facturas_inteligentes] Error: {e}")
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
