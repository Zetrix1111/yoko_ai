"""
api/chat.py — dispatcher de Yoko (asistente caja chica).

Único archivo que Vercel ve como serverless function. Toda la lógica
vive en api/yoko/handler.py. Este archivo solo hace el bootstrap del
sys.path y delega al handler interno.

Body esperado:
    {
      "user":     {"dni": "...", "nombre": "...", "cargo": "..."},
      "messages": [{"role": "user"|"assistant", "content": "..."}, ...]
    }

Respuesta: {"text": "...", "action": {...} | null}
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# api/ al sys.path para que `from _lib import ...` y `from _yoko import ...`
# resuelvan correctamente, igual que el resto de los handlers serverless.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _yoko import handler as yoko_handler  # noqa: E402


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            yoko_handler.handle_post(self)
        except Exception as e:
            print(f"[chat] Error inesperado en dispatcher: {type(e).__name__}: {e}", file=sys.stderr)
            self._json(500, {"error": "Error interno del servidor."})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
