"""
api/ventas.py — dispatcher de Ventas Inteligentes.

Único archivo que Vercel ve como serverless function. Toda la lógica
vive en api/_ventas/<resource>.py. Este archivo SOLO hace routing por
?resource= y método HTTP, valida JWT y pasa `empresa_id` a las funciones.

Recursos soportados (todos requieren JWT salvo `sales_chat`):
  GET    ?resource=wa                   → estado WhatsApp
  POST   ?resource=wa&action=connect    → init pairing
  POST   ?resource=wa&action=disconnect → cerrar sesión
  GET    ?resource=conversaciones       → lista
  GET    ?resource=conversaciones&id=…  → una
  DELETE ?resource=conversaciones&id=…  → borra (con sus mensajes)
  GET    ?resource=mensajes             → historial por conv
  POST   ?resource=mensajes             → insert (+ outbox si role=human)
  POST   ?resource=conversaciones_modo  → toggle AI/HUMAN
  GET    ?resource=prompt_preview       → system prompt del agente IA
  POST   ?resource=sales_chat           → cerebro del bot-baileys (S2S)

`sales_chat` es la única excepción que NO valida JWT: lo invoca el bot
de WhatsApp server-to-server, sin token. Toma `empresa_id` del body
porque el bot lo conoce desde su propio .env por sesión Baileys.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# api/ al sys.path para que `from _lib import ...` y `from _ventas import ...`
# resuelvan correctamente, igual que el resto de los handlers serverless.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                                                # noqa: E402
from _lib.auth import AuthError                                      # noqa: E402
from _ventas import wa, conversaciones, chat as ventas_chat, prompt_preview  # noqa: E402


# Mapa: (resource, método) → función que recibe (req, empresa_id).
# Estas funciones requieren JWT — el dispatcher valida y les pasa empresa_id.
_DISPATCH_AUTH = {
    ("wa",                  "GET"):    wa.wa_get,
    ("wa",                  "POST"):   wa.wa_post,

    ("conversaciones",      "GET"):    conversaciones.conversaciones_get,
    ("conversaciones",      "DELETE"): conversaciones.conversaciones_delete,

    ("mensajes",            "GET"):    conversaciones.mensajes_get,
    ("mensajes",            "POST"):   conversaciones.mensajes_post,

    ("conversaciones_modo", "POST"):   conversaciones.modo_post,

    ("prompt_preview",      "GET"):    prompt_preview.prompt_preview_get,
}

# Recursos S2S (NO validan JWT). Reciben (req,) — empresa_id viene del body.
_DISPATCH_PUBLIC = {
    ("sales_chat", "POST"): ventas_chat.sales_chat_post,
}


class handler(BaseHTTPRequestHandler):

    def do_GET(self):    return self._dispatch("GET")
    def do_POST(self):   return self._dispatch("POST")
    def do_DELETE(self): return self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        qs = parse_qs(urlparse(self.path).query)
        resource = (qs.get("resource") or [""])[0]
        key = (resource, method)

        # Recursos S2S: sin JWT.
        public_fn = _DISPATCH_PUBLIC.get(key)
        if public_fn is not None:
            try:
                return public_fn(self)
            except Exception as e:
                print(f"[ventas/{resource}] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
                return self._json(500, {"error": "Error interno del servidor."})

        # Resto: validar JWT antes de despachar.
        auth_fn = _DISPATCH_AUTH.get(key)
        if auth_fn is None:
            return self._json(400, {"error": f"resource '{resource}' no soporta {method}."})

        try:
            auth_payload = auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})
        empresa_id = auth_payload["empresa_id"]

        try:
            return auth_fn(self, empresa_id)
        except Exception as e:
            print(f"[ventas/{resource}] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Helpers expuestos a los sub-handlers ──────────────────────────────

    def _qs(self) -> dict:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
