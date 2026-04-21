"""
api/chat.py
Serverless function (Python): proxy seguro hacia el webhook de Make (IA).
El CHANNEL y la URL de Make nunca se exponen al browser.

A futuro (Fase 4): reemplazar la llamada a Make por:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(...)
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))

            webhook_url = os.environ.get("MAKE_WEBHOOK_AI")
            channel     = os.environ.get("CHANNEL", "app")

            if not webhook_url:
                return self._json(500, {"error": "Configuración del servidor incompleta."})

            # El canal se inyecta aquí en el servidor, nunca viene del cliente
            payload = {
                "canal":          channel,
                "message":        body.get("message", ""),
                "has_attachment": bool(body.get("has_attachment", False)),
                "session_id":     body.get("session_id", ""),
            }
            if body.get("batchId"):
                payload["batchId"] = body["batchId"]

            data   = json.dumps(payload).encode("utf-8")
            req    = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=28) as res:
                content_type = res.headers.get("Content-Type", "")
                raw = res.read()

            if "application/json" in content_type:
                return self._json(200, json.loads(raw))
            else:
                # Make a veces responde texto plano
                return self._json(200, {"response": raw.decode("utf-8")})

        except urllib.error.HTTPError as e:
            print(f"[chat] Error Make HTTP {e.code}")
            return self._json(502, {"error": f"Error del servicio IA: HTTP {e.code}."})

        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

        except Exception as e:
            print(f"[chat] Error inesperado: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
