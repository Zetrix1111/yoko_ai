"""
api/chat.py — dispatcher de Yoko (asistente).

Único archivo que Vercel ve como serverless function. Rutea por `?action=`
y método HTTP. Toda la lógica vive en `api/_yoko/handler*.py`.

Acciones (managed_agents backend, async pattern):
  POST /api/chat                          → encolar task, devolver task_id
                                            (handler_managed.handle_post)
  POST /api/chat?action=worker            → ejecutar el task (auth interna)
                                            (handler_worker.handle_post)
  GET  /api/chat?action=status&task_id=X  → polling (auth user)
                                            (handler_status.handle_get)

Acción legacy (openai backend):
  Si `YOKO_BACKEND=openai`, el POST sin action sigue corriendo el flujo
  síncrono viejo (handler.handle_post). El feature flag se chequea
  dentro de handler_managed.handle_post — esta capa es solo dispatch.

Body esperado para POST sin action:
    {
      "user":     {"dni": "...", "nombre": "...", "cargo": "..."},
      "messages": [{"role": "user"|"assistant", "content": "..."}, ...]
      "attachments": [{"filename": "...", "content_b64": "..."}, ...] (opcional)
    }

Response:
  POST sin action  → {"task_id": "...", "status": "pending"}  (managed)
                     {"text": "...", "action": null}          (openai legacy)
  POST ?worker     → {"ok": true, "task_id": "..."}
  GET  ?status     → {"status": "...", "text": "...", "error": null}
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _yoko import handler as yoko_handler          # noqa: E402
from _yoko import handler_status, handler_worker   # noqa: E402


def _get_action(req) -> str:
    parsed = urlparse(req.path)
    qs = parse_qs(parsed.query or "")
    return (qs.get("action") or [""])[0].strip().lower()


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            action = _get_action(self)
            if action == "worker":
                handler_worker.handle_post(self)
            elif action == "status":
                # GET-equivalent vía POST (algunos clients no soportan GET con body).
                handler_status.handle_post(self)
            else:
                # Acción default: chat normal (managed_agents async o openai sync).
                # `yoko_handler.handle_post` mira YOKO_BACKEND y delega a
                # handler_managed.handle_post (que ahora encola task) o al
                # flujo legacy.
                yoko_handler.handle_post(self)
        except Exception as e:
            print(
                f"[chat] Error inesperado en dispatcher (POST {self.path}): "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            self._json(500, {"error": "Error interno del servidor."})

    def do_GET(self):
        try:
            action = _get_action(self)
            if action == "status":
                handler_status.handle_get(self)
            else:
                self._json(404, {"error": "GET solo soporta ?action=status"})
        except Exception as e:
            print(
                f"[chat] Error inesperado en dispatcher (GET {self.path}): "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
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
