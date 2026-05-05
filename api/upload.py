"""
api/upload.py
Serverless function (Python): proxy seguro para subida de archivos.
Lee el body multipart/form-data del browser y lo reenvía tal cual
al webhook de Make — la URL nunca se expone al cliente.
"""

from http.server import BaseHTTPRequestHandler
import os
import sys
import urllib.request
import urllib.error
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                 # noqa: E402
from _lib.auth import AuthError       # noqa: E402


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            try:
                auth.require_auth(self.headers)
            except AuthError as e:
                return self._json(e.status, {"error": str(e)})

            webhook_url  = os.environ.get("MAKE_WEBHOOK_UPLOAD")
            if not webhook_url:
                return self._json(500, {"error": "Configuración del servidor incompleta."})

            content_length = int(self.headers.get("Content-Length", 0))
            content_type   = self.headers.get("Content-Type", "multipart/form-data")

            # Leer el cuerpo multipart tal como viene del browser
            raw_body = self.rfile.read(content_length)

            # Hacer proxy directo: reenviar el multipart a Make sin modificarlo
            req = urllib.request.Request(
                webhook_url,
                data=raw_body,
                headers={"Content-Type": content_type},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=28) as res:
                status_ok = (200 <= res.status < 300)

            return self._json(200 if status_ok else 502, {"ok": status_ok})

        except urllib.error.HTTPError as e:
            print(f"[upload] Error Make HTTP {e.code}")
            return self._json(502, {"error": f"Error al subir archivo: HTTP {e.code}."})

        except Exception as e:
            print(f"[upload] Error inesperado: {e}")
            return self._json(500, {"error": "Error interno al subir el archivo."})

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
