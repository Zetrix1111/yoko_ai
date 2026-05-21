"""
api/solicitudes.py — dispatcher del módulo de solicitudes de caja.

Acciones para tools conversacionales (POST):
  POST /api/solicitudes?action=procesar-solicitud-caja-chat
  POST /api/solicitudes?action=crear-chat
  POST /api/solicitudes?action=consultar-por-id-chat
  POST /api/solicitudes?action=consultar-por-dni-chat
  POST /api/solicitudes?action=consultar-aprobador-chat
  POST /api/solicitudes?action=consultar-centros-costo-chat

Acciones REST para la UI de gestión de caja chica:
  GET  /api/solicitudes?action=listar
  GET  /api/solicitudes?action=detalle&id=<recId>
  PUT  /api/solicitudes?action=actualizar-items
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client, auth, config_loader, solicitud_caja_processor  # noqa: E402
from _lib.airtable_client import AirtableError  # noqa: E402
from _lib.auth import AuthError  # noqa: E402
from _yoko._lib import tool_registry  # noqa: E402
from _yoko._lib.tools import consulta, crear_solicitud  # noqa: F401,E402


_TABLA_SOLICITUDES = "solicitudes_caja"
_CAMPO_EMAIL = "EMAIL (from SOLICITANTE)"
_CAMPO_ESTADO = "ESTADO"

# Solo se permite editar items mientras la solicitud no haya sido pagada/rendida.
_ESTADOS_EDITABLES_PREFIX = ("PENDIENTE_",)


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


# ─────────────────────────────────────────────────────────────────────────
# REST endpoints para la UI de gestión de caja chica
# ─────────────────────────────────────────────────────────────────────────

def _parse_detalle_gasto(raw) -> list[dict]:
    """
    DETALLE_GASTO en Airtable se guarda como JSON serializado (long text).
    Tolerante con el legacy: si llega como texto plano (registros viejos),
    devuelve [] sin romper — la UI muestra una tabla vacía editable.
    """
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_resumen(record: dict) -> dict:
    """Mapea un record de Airtable al shape que consume el listado."""
    fields = record.get("fields", {})
    items = _parse_detalle_gasto(fields.get("DETALLE_GASTO"))
    return {
        "id":            record.get("id"),
        "numero":        fields.get("NUMERO") or "",
        "tipo":          fields.get("TIPO_SOLICITUD") or "",
        "motivo":        fields.get("MOTIVO") or "",
        "moneda":        fields.get("MONEDA") or "",
        "total_general": fields.get("TOTAL_GENERAL") or 0,
        "estado":        fields.get(_CAMPO_ESTADO) or "",
        "fecha":         fields.get("fecha") or fields.get("FECHA") or "",
        "nombre":        fields.get("NOMBRE") or "",
        "items_count":   len(items),
    }


def _es_editable(estado: str) -> bool:
    if not estado:
        return False
    return any(str(estado).upper().startswith(p) for p in _ESTADOS_EDITABLES_PREFIX)


def _listar(req, auth_payload: dict) -> None:
    email = (auth_payload.get("email") or "").strip()
    if not email:
        return req._json(400, {"error": "No se pudo identificar al usuario (email ausente)."})

    # Escape defensivo del email para la formula de Airtable.
    esc_email = email.replace("'", "\\'")
    formula = f"{{{_CAMPO_EMAIL}}}='{esc_email}'"

    try:
        records = airtable_client.list_records(
            _TABLA_SOLICITUDES,
            filter_formula=formula,
        )
    except AirtableError as e:
        print(f"[solicitudes/listar] Airtable: {e}", file=sys.stderr)
        return req._json(502, {"error": "Error al consultar las solicitudes."})

    solicitudes = [_row_to_resumen(r) for r in records]
    # Más recientes primero — usamos NUMERO como proxy si fecha no está disponible.
    solicitudes.sort(key=lambda s: s.get("numero", ""), reverse=True)
    return req._json(200, {"solicitudes": solicitudes, "total": len(solicitudes)})


def _detalle(req, auth_payload: dict, record_id: str) -> None:
    if not record_id or not record_id.startswith("rec"):
        return req._json(400, {"error": "id inválido."})

    email = (auth_payload.get("email") or "").strip().lower()
    try:
        record = airtable_client.get_record(_TABLA_SOLICITUDES, record_id)
    except AirtableError as e:
        print(f"[solicitudes/detalle] Airtable: {e}", file=sys.stderr)
        return req._json(404, {"error": "Solicitud no encontrada."})

    fields = record.get("fields", {})
    # Defense-in-depth: comparar email del JWT con el lookup de la solicitud.
    # Si no matchea, devolver 404 (no 403) para no leakear existencia.
    solicitud_email = fields.get(_CAMPO_EMAIL)
    if isinstance(solicitud_email, list):
        emails_norm = [str(e).strip().lower() for e in solicitud_email]
    else:
        emails_norm = [str(solicitud_email or "").strip().lower()]
    if email not in emails_norm:
        print(
            f"[solicitudes/detalle] tenant mismatch: jwt={email!r} "
            f"vs record={emails_norm!r}",
            file=sys.stderr,
        )
        return req._json(404, {"error": "Solicitud no encontrada."})

    items = _parse_detalle_gasto(fields.get("DETALLE_GASTO"))
    return req._json(200, {
        "id":             record.get("id"),
        "numero":         fields.get("NUMERO") or "",
        "tipo":           fields.get("TIPO_SOLICITUD") or "",
        "motivo":         fields.get("MOTIVO") or "",
        "plazo":          fields.get("PLAZO") or "",
        "moneda":         fields.get("MONEDA") or "",
        "total_general":  fields.get("TOTAL_GENERAL") or 0,
        "centro_costo":   fields.get("CENTRO_COSTO") or "",
        "estado":         fields.get(_CAMPO_ESTADO) or "",
        "editable":       _es_editable(fields.get(_CAMPO_ESTADO)),
        "nombre":         fields.get("NOMBRE") or "",
        "items":          items,
    })


def _to_float(value, default: float = 0.0) -> float:
    """Convierte strings con comas/símbolos a float. Devuelve default si falla."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    # Quitar símbolos de moneda comunes
    for sym in ("S/", "S/.", "$", "USD", "PEN", "€", "EUR"):
        s = s.replace(sym, "")
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return default


def _normalizar_item(item: dict) -> dict:
    """Solo deja los keys permitidos en un item editable."""
    permitidos = ("descripcion", "unidad", "cantidad", "precio_unitario", "total", "proveedor")
    return {k: item.get(k) for k in permitidos}


def _actualizar_items(req, auth_payload: dict) -> None:
    body = _read_json_body(req)
    if body is None:
        return

    record_id = (body.get("id") or "").strip()
    items_raw = body.get("detalle_gasto")
    if not record_id or not record_id.startswith("rec"):
        return req._json(400, {"error": "id inválido."})
    if not isinstance(items_raw, list):
        return req._json(400, {"error": "detalle_gasto debe ser un array."})

    email = (auth_payload.get("email") or "").strip().lower()
    try:
        record = airtable_client.get_record(_TABLA_SOLICITUDES, record_id)
    except AirtableError as e:
        print(f"[solicitudes/actualizar-items] get_record: {e}", file=sys.stderr)
        return req._json(404, {"error": "Solicitud no encontrada."})

    fields = record.get("fields", {})
    solicitud_email = fields.get(_CAMPO_EMAIL)
    if isinstance(solicitud_email, list):
        emails_norm = [str(e).strip().lower() for e in solicitud_email]
    else:
        emails_norm = [str(solicitud_email or "").strip().lower()]
    if email not in emails_norm:
        return req._json(404, {"error": "Solicitud no encontrada."})

    estado = fields.get(_CAMPO_ESTADO) or ""
    if not _es_editable(estado):
        return req._json(
            409,
            {"error": f"La solicitud no se puede editar en estado {estado!r}."},
        )

    items = [_normalizar_item(i) for i in items_raw if isinstance(i, dict)]
    # Recalcular total_general sumando los `total` de cada item.
    total = sum(_to_float(i.get("total")) for i in items)

    try:
        updated = airtable_client.update_record(
            _TABLA_SOLICITUDES,
            record_id,
            {
                "DETALLE_GASTO": json.dumps(items, ensure_ascii=False),
                "TOTAL_GENERAL": round(total, 2),
            },
        )
    except AirtableError as e:
        print(f"[solicitudes/actualizar-items] update: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo actualizar la solicitud."})

    return req._json(200, {
        "ok":            True,
        "id":            updated.get("id"),
        "total_general": round(total, 2),
        "items_count":   len(items),
    })


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

    def do_GET(self):
        try:
            auth_payload = auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        action = _get_action(self)
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query or "")

        if action == "listar":
            return _listar(self, auth_payload)
        if action == "detalle":
            rid = (qs.get("id") or [""])[0].strip()
            return _detalle(self, auth_payload, rid)
        return self._json(404, {"error": f"GET action no soportada: {action}"})

    def do_PUT(self):
        try:
            auth_payload = auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        action = _get_action(self)
        if action == "actualizar-items":
            return _actualizar_items(self, auth_payload)
        return self._json(404, {"error": f"PUT action no soportada: {action}"})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
