"""
api/_lib/tool_executor.py

Ejecutor de custom tools del agent (Managed Agents). Antes vivía dentro
de `_yoko/handler_managed.py` como helpers privados, pero el worker
async (`_yoko/handler_worker.py`) los importaba — eso creaba un
acoplamiento circular incómodo: el worker dependía del handler "padre"
solo para reusar dos helpers genéricos.

Lo extrajimos acá. Tanto handler_managed como handler_worker (y
cualquier futuro consumidor) deberían importar desde acá.

API pública:
  - `TOOL_TO_ACTION: dict[str, str]` — mapeo nombre del custom tool →
    ruta `endpoint:action`. Si se omite el endpoint, cae a `facturas`
    por compatibilidad.
  - `execute_local_tool(action, input_args, auth_header, tool_context=None) -> dict` —
    hace HTTP loopback a /api/facturas?action=<action> con el JWT del
    usuario reenviado. Devuelve dict listo para serializar como
    `user.custom_tool_result`. Si la respuesta es binaria (xlsx),
    la codifica en base64.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from ._config import TOOL_HTTP_TIMEOUT_SECONDS
from ._http_utils import read_http_error_body


# Mapeo nombre del custom tool → endpoint:action. Si un tool
# nuevo aparece, agregar acá y crear la action en su dispatcher. Tiene que
# coincidir con `ALL_TOOLS` de `_yoko_agents/tools/__init__.py`.
TOOL_TO_ACTION: dict[str, str] = {
    "yoko_procesar_archivos":         "facturas:procesar-chat",
    "yoko_generar_registro_contable": "facturas:registro-contable-chat",
    "yoko_recuperar_proceso":         "facturas:recuperar-chat",
    "yoko_procesar_solicitud_caja":   "solicitudes:procesar-solicitud-caja-chat",
    "yoko_crear_solicitud":           "solicitudes:crear-chat",
    "consultar_solicitud_por_id":     "solicitudes:consultar-por-id-chat",
    "consultar_solicitudes_por_dni":  "solicitudes:consultar-por-dni-chat",
    "consultar_aprobador":            "solicitudes:consultar-aprobador-chat",
    "consultar_centros_costo":        "solicitudes:consultar-centros-costo-chat",
}


def execute_local_tool(
    action: str,
    input_args: dict,
    auth_header: str,
    tool_context: dict | None = None,
) -> dict:
    """
    Ejecuta un custom tool del agent haciendo HTTP loopback a la propia API
    Yoko en `/api/facturas?action=<action>` con el JWT del usuario reenviado.

    Devuelve dict que se serializa como `user.custom_tool_result`. Si la
    respuesta del endpoint es binaria (xlsx en download-chat), la codifica
    en base64 y la incluye en el dict.
    """
    endpoint, resolved_action = _resolve_route(action)
    base = (os.environ.get("YOKO_API_BASE") or "https://yokochat.vercel.app").rstrip("/")
    url = f"{base}/api/{endpoint}?action={urllib.parse.quote(resolved_action)}"

    body_payload = dict(input_args or {})
    if tool_context:
        body_payload["_yoko_context"] = tool_context
    body = json.dumps(body_payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if auth_header:
        request.add_header("Authorization", auth_header)

    try:
        with urllib.request.urlopen(request, timeout=TOOL_HTTP_TIMEOUT_SECONDS) as res:
            content_type = res.headers.get("Content-Type", "") or ""
            data = res.read()
            if "application/json" in content_type:
                return json.loads(data) if data else {}
            if "spreadsheet" in content_type or resolved_action == "download-chat":
                disposition = res.headers.get("Content-Disposition", "") or ""
                return {
                    "ok":           True,
                    "filename":     _filename_from_disposition(disposition),
                    "content_b64":  base64.b64encode(data).decode("ascii"),
                    "content_type": content_type,
                }
            return {"ok": True, "raw_size": len(data), "content_type": content_type}
    except urllib.error.HTTPError as e:
        err_body = read_http_error_body(e)
        print(
            f"[tool_executor] tool {endpoint}:{resolved_action} HTTP {e.code}: {err_body[:300]}",
            file=sys.stderr,
        )
        return {"error": f"HTTP {e.code} en {endpoint}:{resolved_action}", "detail": err_body[:300]}
    except urllib.error.URLError as e:
        print(f"[tool_executor] tool {action} URL error: {e}", file=sys.stderr)
        return {"error": f"Error de red al ejecutar {endpoint}:{resolved_action}"}
    except Exception as e:
        print(
            f"[tool_executor] tool {endpoint}:{resolved_action} excepción {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return {"error": f"Error inesperado en {endpoint}:{resolved_action}: {type(e).__name__}"}


def _resolve_route(action: str) -> tuple[str, str]:
    if ":" in action:
        endpoint, resolved_action = action.split(":", 1)
        endpoint = endpoint.strip().strip("/")
        resolved_action = resolved_action.strip()
        if endpoint and resolved_action:
            return endpoint, resolved_action
    return "facturas", action


def _filename_from_disposition(header: str) -> str:
    if "filename=" not in header:
        return "archivo"
    return header.split("filename=", 1)[1].strip(' ;"\'')
