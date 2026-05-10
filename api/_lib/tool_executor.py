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
    action en /api/facturas. Si se agrega un tool nuevo en
    `_yoko_agents/tools/__init__.py`, hay que agregar su entrada acá
    Y crear la action correspondiente en `api/facturas.py`.
  - `execute_local_tool(action, input_args, auth_header) -> dict` —
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


# Mapeo nombre del custom tool → action en /api/facturas. Si un tool
# nuevo aparece, agregar acá y crear la action en facturas.py. Tiene que
# coincidir con `ALL_TOOLS` de `_yoko_agents/tools/__init__.py`.
TOOL_TO_ACTION: dict[str, str] = {
    "yoko_procesar_archivos":         "procesar-chat",
    "yoko_generar_registro_contable": "registro-contable-chat",
    # "yoko_recuperar_proceso":       "recuperar-chat",  # uso futuro
}


def execute_local_tool(action: str, input_args: dict, auth_header: str) -> dict:
    """
    Ejecuta un custom tool del agent haciendo HTTP loopback a la propia API
    Yoko en `/api/facturas?action=<action>` con el JWT del usuario reenviado.

    Devuelve dict que se serializa como `user.custom_tool_result`. Si la
    respuesta del endpoint es binaria (xlsx en download-chat), la codifica
    en base64 y la incluye en el dict.
    """
    base = (os.environ.get("YOKO_API_BASE") or "https://yokochat.vercel.app").rstrip("/")
    url = f"{base}/api/facturas?action={urllib.parse.quote(action)}"

    body = json.dumps(input_args).encode("utf-8")
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
            if "spreadsheet" in content_type or action == "download-chat":
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
            f"[tool_executor] tool {action} HTTP {e.code}: {err_body[:300]}",
            file=sys.stderr,
        )
        return {"error": f"HTTP {e.code} en {action}", "detail": err_body[:300]}
    except urllib.error.URLError as e:
        print(f"[tool_executor] tool {action} URL error: {e}", file=sys.stderr)
        return {"error": f"Error de red al ejecutar {action}"}
    except Exception as e:
        print(
            f"[tool_executor] tool {action} excepción {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return {"error": f"Error inesperado en {action}: {type(e).__name__}"}


def _filename_from_disposition(header: str) -> str:
    if "filename=" not in header:
        return "archivo"
    return header.split("filename=", 1)[1].strip(' ;"\'')
