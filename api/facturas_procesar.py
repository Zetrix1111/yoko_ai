"""
api/facturas_procesar.py
Proxy seguro al webhook de Make para PROCESAMIENTO de facturas.
Recibe multipart/form-data del browser y lo reenvía al webhook tal cual.

Si MAKE_WEBHOOK_FACTURAS_PROCESAR no está configurado, devuelve datos
mock (proceso_id + sheet_url) — útil en preview / desarrollo.
"""

from http.server import BaseHTTPRequestHandler
import os
import json
import time
import urllib.request
import urllib.error


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            webhook_url    = os.environ.get("MAKE_WEBHOOK_FACTURAS_PROCESAR")
            content_length = int(self.headers.get("Content-Length", 0))
            content_type   = self.headers.get("Content-Type", "multipart/form-data")
            raw_body       = self.rfile.read(content_length)

            # ── Modo mock: el env var no está seteado todavía ──
            if not webhook_url:
                proceso_id = f"proc-mock-{int(time.time())}"
                return self._json(200, {
                    "ok": True,
                    "mock": True,
                    "proceso_id": proceso_id,
                    "sheet_url": "https://docs.google.com/spreadsheets/d/MOCK_FACTURAS_VALIDACION/edit",
                    "empresa_id": "cmejia",
                })

            # ── Modo real: forward multipart al webhook ──
            req = urllib.request.Request(
                webhook_url,
                data=raw_body,
                headers={"Content-Type": content_type},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as res:
                response_ct = res.headers.get("Content-Type", "")
                raw = res.read()

            if "application/json" in response_ct:
                return self._json(200, json.loads(raw))
            # Si Make responde texto plano, lo envolvemos
            return self._json(200, {
                "ok": True,
                "raw": raw.decode("utf-8", errors="replace"),
            })

        except urllib.error.HTTPError as e:
            print(f"[facturas/procesar] HTTP {e.code}")
            return self._json(502, {"error": f"Error en webhook (HTTP {e.code})."})

        except Exception as e:
            print(f"[facturas/procesar] {e}")
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
