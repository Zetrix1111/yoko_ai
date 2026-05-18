"""
api/solicitudes.py — dispatcher del módulo de solicitudes de caja.

Acciones para tools conversacionales:
  POST /api/solicitudes?action=procesar-solicitud-caja-chat
  POST /api/solicitudes?action=crear-chat
  POST /api/solicitudes?action=consultar-por-id-chat
  POST /api/solicitudes?action=consultar-por-dni-chat
  POST /api/solicitudes?action=consultar-aprobador-chat
  POST /api/solicitudes?action=consultar-centros-costo-chat
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth, config_loader, solicitud_caja_processor  # noqa: E402
from _lib.airtable_client import AirtableError  # noqa: E402
from _lib.auth import AuthError  # noqa: E402
from _yoko._lib import tool_registry  # noqa: E402
from _yoko._lib.tools import consulta, crear_solicitud  # noqa: F401,E402


def _get_action(req) -> str:
    parsed = urlparse(req.path)
    qs = parse_qs(parsed.query or "")
    return (qs.get("action") or [""])[0].strip().lower()


def _procesar_solicitud_caja_chat(req, empresa_id: str) -> None:
    _ = empresa_id
    try:
        length = int(req.headers.get("Content-Length", 0))
        if length == 0:
            return req._json(400, {"error": "Body vacío."})
        try:
            body = json.loads(req.rfile.read(length))
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido."})

        result = solicitud_caja_processor.procesar_solicitud_caja(body)
        status = 200 if result.get("ok") else 400
        return req._json(status, result)

    except ValueError as e:
        return req._json(400, {"ok": False, "error": str(e)})
    except Exception as e:
        print(
            f"[solicitudes/procesar-solicitud-caja-chat] Error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return req._json(500, {"ok": False, "error": "Error al procesar solicitud de caja."})


def _read_json_body(req) -> dict | None:
    length = int(req.headers.get("Content-Length", 0))
    if length == 0:
        req._json(400, {"error": "Body vacío."})
        return None
    try:
        body = json.loads(req.rfile.read(length))
    except json.JSONDecodeError:
        req._json(400, {"error": "JSON inválido."})
        return None
    if not isinstance(body, dict):
        req._json(400, {"error": "JSON debe ser un objeto."})
        return None
    return body


def _execute_registry_tool(req, auth_payload: dict, tool_name: str) -> None:
    body = _read_json_body(req)
    if body is None:
        return

    tool_context = body.pop("_yoko_context", {}) or {}
    if not isinstance(tool_context, dict):
        tool_context = {}

    empresa_id = auth_payload["empresa_id"]
    try:
        config = config_loader.load_full_config(empresa_id)
    except AirtableError as e:
        print(f"[solicitudes/{tool_name}] Airtable config error: {e}", file=sys.stderr)
        return req._json(502, {"error": "Error al consultar la configuración."})

    modulos = tool_context.get("modulos") or auth_payload.get("modulos") or []
    if isinstance(modulos, list):
        config.setdefault("empresa", {})["modules"] = modulos

    context = {
        "user": tool_context.get("user") or {},
        "config": config,
        "empresa_id": empresa_id,
        "session_id_for_cart": tool_context.get("session_id_for_cart"),
        "auth_header": req.headers.get("Authorization") or "",
    }
    result = tool_registry.execute_tool(tool_name, body, context)
    status = 200 if not result.get("error") else 400
    return req._json(status, result)


def _crear_chat(req, auth_payload: dict) -> None:
    return _execute_registry_tool(req, auth_payload, "yoko_crear_solicitud")


def _consultar_por_id_chat(req, auth_payload: dict) -> None:
    return _execute_registry_tool(req, auth_payload, "consultar_solicitud_por_id")


def _consultar_por_dni_chat(req, auth_payload: dict) -> None:
    return _execute_registry_tool(req, auth_payload, "consultar_solicitudes_por_dni")


def _consultar_aprobador_chat(req, auth_payload: dict) -> None:
    return _execute_registry_tool(req, auth_payload, "consultar_aprobador")


def _consultar_centros_costo_chat(req, auth_payload: dict) -> None:
    return _execute_registry_tool(req, auth_payload, "consultar_centros_costo")


_POST_ACTIONS = {
    "procesar-solicitud-caja-chat": _procesar_solicitud_caja_chat,
    "crear-chat": _crear_chat,
    "consultar-por-id-chat": _consultar_por_id_chat,
    "consultar-por-dni-chat": _consultar_por_dni_chat,
    "consultar-aprobador-chat": _consultar_aprobador_chat,
    "consultar-centros-costo-chat": _consultar_centros_costo_chat,
}


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            auth_payload = auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        action = _get_action(self)
        fn = _POST_ACTIONS.get(action)
        if not fn:
            return self._json(404, {"error": f"action no soportada: {action}"})
        if action == "procesar-solicitud-caja-chat":
            return fn(self, auth_payload["empresa_id"])
        return fn(self, auth_payload)

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
