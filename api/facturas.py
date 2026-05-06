"""
api/facturas.py — dispatcher de Facturas Inteligentes.

Único archivo serverless que Vercel ve para el módulo Facturas Inteligentes.
Consolida los dos proxies a Make en un solo dispatcher por `?action=`.

Recursos:
  POST /api/facturas?action=procesar  → multipart/form-data → MAKE_WEBHOOK_FACTURAS_PROCESAR
  POST /api/facturas?action=concar    → JSON {proceso_id, dni} → MAKE_WEBHOOK_FACTURAS_CONCAR

Ambas acciones requieren JWT. `empresa_id` se extrae del token y, en
`concar`, sobreescribe cualquier valor del body antes de reenviar al
webhook (cross-tenant guard).

Si las env vars `MAKE_WEBHOOK_FACTURAS_*` no están seteadas, las acciones
devuelven datos mock — útil en preview / desarrollo.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                                              # noqa: E402
from _lib.auth import AuthError                                    # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# Acciones — invocadas tras validar JWT en el dispatcher
# ─────────────────────────────────────────────────────────────────────────

def _procesar(req, empresa_id: str) -> None:
    """Forward del multipart/form-data al webhook de procesamiento OCR."""
    try:
        webhook_url    = os.environ.get("MAKE_WEBHOOK_FACTURAS_PROCESAR")
        content_length = int(req.headers.get("Content-Length", 0))
        content_type   = req.headers.get("Content-Type", "multipart/form-data")
        raw_body       = req.rfile.read(content_length)

        # Modo mock (env var no seteada en dev/preview).
        if not webhook_url:
            return req._json(200, {
                "ok": True,
                "mock": True,
                "proceso_id": f"proc-mock-{int(time.time())}",
                "sheet_url": "https://docs.google.com/spreadsheets/d/MOCK_FACTURAS_VALIDACION/edit",
                "empresa_id": empresa_id,
            })

        http_req = urllib.request.Request(
            webhook_url,
            data=raw_body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=120) as res:
            response_ct = res.headers.get("Content-Type", "")
            raw = res.read()

        if "application/json" in response_ct:
            return req._json(200, json.loads(raw))
        return req._json(200, {"ok": True, "raw": raw.decode("utf-8", errors="replace")})

    except urllib.error.HTTPError as e:
        print(f"[facturas/procesar] HTTP {e.code}", file=sys.stderr)
        return req._json(502, {"error": f"Error en webhook (HTTP {e.code})."})


def _concar(req, empresa_id: str) -> None:
    """Forward del JSON {proceso_id, dni} al webhook de generación CONCAR."""
    try:
        webhook_url = os.environ.get("MAKE_WEBHOOK_FACTURAS_CONCAR")
        length      = int(req.headers.get("Content-Length", 0))
        try:
            body = json.loads(req.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido."})

        # `empresa_id` del JWT siempre gana — bloquea cross-tenant del body.
        body["empresa_id"] = empresa_id

        if not webhook_url:
            proceso_id = body.get("proceso_id", "mock")
            return req._json(200, {
                "ok": True,
                "mock": True,
                "download_url": f"https://example.com/CONCAR_{proceso_id}.txt",
            })

        payload  = json.dumps(body).encode("utf-8")
        http_req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=120) as res:
            response_ct = res.headers.get("Content-Type", "")
            raw = res.read()

        if "application/json" in response_ct:
            return req._json(200, json.loads(raw))
        return req._json(200, {
            "ok": True,
            "download_url": raw.decode("utf-8", errors="replace").strip(),
        })

    except urllib.error.HTTPError as e:
        print(f"[facturas/concar] HTTP {e.code}", file=sys.stderr)
        return req._json(502, {"error": f"Error en webhook (HTTP {e.code})."})


# Mapa: action → handler. Toda acción nueva se registra acá.
_ACTIONS = {
    "procesar": _procesar,
    "concar":   _concar,
}


# ─────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_POST(self) -> None:
        action = (parse_qs(urlparse(self.path).query).get("action") or [""])[0]
        fn = _ACTIONS.get(action)
        if fn is None:
            return self._json(400, {"error": f"action inválida. Use: {sorted(_ACTIONS)}."})

        try:
            try:
                auth_payload = auth.require_auth(self.headers)
            except AuthError as e:
                return self._json(e.status, {"error": str(e)})
            empresa_id = auth_payload["empresa_id"]
            return fn(self, empresa_id)
        except Exception as e:
            print(f"[facturas/{action}] Error: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
