"""
api/facturas_concar.py
Proxy seguro al webhook de Make para GENERACIÓN del archivo CONCAR.
Recibe { proceso_id, empresa_id, dni } como JSON.

Si MAKE_WEBHOOK_FACTURAS_CONCAR no está configurado, devuelve un
download_url mock — útil en preview / desarrollo.
"""

from http.server import BaseHTTPRequestHandler
import os
import json
import urllib.request
import urllib.error


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            webhook_url = os.environ.get("MAKE_WEBHOOK_FACTURAS_CONCAR")
            length      = int(self.headers.get("Content-Length", 0))
            body        = json.loads(self.rfile.read(length)) if length else {}

            # ── Modo mock ──
            if not webhook_url:
                proceso_id = body.get("proceso_id", "mock")
                return self._json(200, {
                    "ok": True,
                    "mock": True,
                    "download_url": f"https://example.com/CONCAR_{proceso_id}.txt",
                })

            # ── Modo real: forward JSON al webhook ──
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as res:
                response_ct = res.headers.get("Content-Type", "")
                raw = res.read()

            if "application/json" in response_ct:
                return self._json(200, json.loads(raw))
            # Si Make responde una URL en texto plano, la envolvemos
            return self._json(200, {
                "ok": True,
                "download_url": raw.decode("utf-8", errors="replace").strip(),
            })

        except urllib.error.HTTPError as e:
            print(f"[facturas/concar] HTTP {e.code}")
            return self._json(502, {"error": f"Error en webhook (HTTP {e.code})."})

        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido."})

        except Exception as e:
            print(f"[facturas/concar] {e}")
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
