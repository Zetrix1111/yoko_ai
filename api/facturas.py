"""
api/facturas.py — dispatcher de Facturas Inteligentes.

Único archivo serverless del módulo. Consolida múltiples acciones en un
solo dispatcher por `?action=` y método HTTP libre (cada action sabe
qué método espera y parsea el body acorde).

Acciones:
  POST   /api/facturas?action=procesar      → multipart, procesa N archivos
  PUT    /api/facturas?action=actualizar    → JSON, auto-save de ediciones
  GET    /api/facturas?action=recuperar     → ?proceso_id=…, recupera proceso
  DELETE /api/facturas?action=eliminar-fila → JSON, borra una factura
  POST   /api/facturas?action=concar        → 501 (TODO fase futura)

Todas validan JWT en el dispatcher; `empresa_id` se extrae del token.
"""

import cgi
import io
import json
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                                                # noqa: E402
from _lib.auth import AuthError                                      # noqa: E402
from _lib.facturas_processor import process_multiple_files           # noqa: E402
from _lib.db_manager import (                                        # noqa: E402
    init_db,
    save_proceso,
    get_proceso,
    update_factura,
    delete_factura,
)


# ─────────────────────────────────────────────────────────────────────────
# Acciones — invocadas tras validar JWT en el dispatcher
# ─────────────────────────────────────────────────────────────────────────

def _procesar(req, empresa_id: str) -> None:
    """
    POST multipart/form-data — procesa N archivos en paralelo.

    Campos del body:
      - tipo:       "compra" | "venta"
      - mes:        "YYYY-MM"
      - mes_label:  "Mayo 2026"
      - dni:        DNI del usuario
      - files:      uno o más archivos (campo repetible)

    Response: {ok, proceso_id, empresa_id, facturas, errores, timestamp}
    """
    try:
        init_db()

        content_type   = req.headers.get("Content-Type", "")
        content_length = int(req.headers.get("Content-Length", 0))
        raw_body       = req.rfile.read(content_length)

        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE":   content_type,
            "CONTENT_LENGTH": str(content_length),
        }
        fs = cgi.FieldStorage(
            fp=io.BytesIO(raw_body),
            environ=environ,
            keep_blank_values=True,
        )

        # Campos de texto del body multipart.
        def _str(name: str, default: str = "") -> str:
            if name not in fs:
                return default
            v = fs.getvalue(name)
            return v.decode("utf-8") if isinstance(v, bytes) else (v or default)

        tipo = _str("tipo", "compra")
        mes  = _str("mes", "")

        # Archivos: el campo "files" puede aparecer una o N veces.
        files = []
        if "files" in fs:
            file_items = fs["files"]
            if not isinstance(file_items, list):
                file_items = [file_items]
            for item in file_items:
                if hasattr(item, "filename") and hasattr(item, "file"):
                    filename = item.filename or "unknown"
                    file_bytes = item.file.read()
                    files.append((filename, file_bytes))

        if not files:
            return req._json(400, {"error": "No se recibieron archivos."})
        if len(files) > 50:
            return req._json(400, {"error": "Máximo 50 archivos por lote."})

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return req._json(500, {"error": "OPENAI_API_KEY no configurada."})

        proceso_id = f"proc-{uuid.uuid4().hex[:12]}"

        resultado = process_multiple_files(
            files=files,
            tipo=tipo,
            mes=mes,
            api_key=api_key,
        )

        save_proceso(proceso_id, empresa_id, resultado["facturas"])

        return req._json(200, {
            "ok":         True,
            "proceso_id": proceso_id,
            "empresa_id": empresa_id,
            "facturas":   resultado["facturas"],
            "errores":    resultado["errores"],
            "timestamp":  time.time(),
        })

    except ValueError as e:
        print(f"[facturas/procesar] ValueError: {e}", file=sys.stderr)
        return req._json(400, {"error": str(e)})
    except Exception as e:
        print(f"[facturas/procesar] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al procesar facturas."})


def _actualizar(req, empresa_id: str) -> None:
    """
    PUT JSON — auto-save de ediciones del usuario.

    Body: {proceso_id, facturas: [...]}
    Response: {ok, updated_count}
    """
    try:
        length = int(req.headers.get("Content-Length", 0))
        if length == 0:
            return req._json(400, {"error": "Body vacío."})

        try:
            body = json.loads(req.rfile.read(length))
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido."})

        proceso_id = body.get("proceso_id")
        facturas   = body.get("facturas", [])

        if not proceso_id:
            return req._json(400, {"error": "proceso_id requerido."})

        # Cross-tenant guard: el proceso debe existir y ser del tenant.
        if not get_proceso(proceso_id, empresa_id):
            return req._json(404, {"error": "Proceso no encontrado."})

        updated_count = sum(
            1 for f in facturas
            if update_factura(proceso_id, empresa_id, f)
        )

        return req._json(200, {"ok": True, "updated_count": updated_count})

    except Exception as e:
        print(f"[facturas/actualizar] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al actualizar."})


def _recuperar(req, empresa_id: str) -> None:
    """
    GET ?proceso_id=… — recupera un proceso guardado previamente.

    Response: {ok, proceso_id, facturas, timestamp} o 404 si no existe.
    """
    try:
        proceso_id = (parse_qs(urlparse(req.path).query).get("proceso_id") or [""])[0]
        if not proceso_id:
            return req._json(400, {"error": "proceso_id requerido en query."})

        proceso = get_proceso(proceso_id, empresa_id)
        if not proceso:
            return req._json(404, {"error": "Proceso no encontrado o expirado."})

        return req._json(200, {
            "ok":         True,
            "proceso_id": proceso_id,
            "facturas":   proceso["facturas"],
            "timestamp":  proceso["timestamp"],
        })

    except Exception as e:
        print(f"[facturas/recuperar] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al recuperar proceso."})


def _eliminar_fila(req, empresa_id: str) -> None:
    """
    DELETE JSON — elimina una factura del proceso.

    Body: {proceso_id, factura_id}
    Response: {ok}
    """
    try:
        length = int(req.headers.get("Content-Length", 0))
        if length == 0:
            return req._json(400, {"error": "Body vacío."})

        try:
            body = json.loads(req.rfile.read(length))
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido."})

        proceso_id = body.get("proceso_id")
        factura_id = body.get("factura_id")
        if not proceso_id or not factura_id:
            return req._json(400, {"error": "proceso_id y factura_id requeridos."})

        # Cross-tenant guard: el proceso debe existir y ser del tenant.
        if not get_proceso(proceso_id, empresa_id):
            return req._json(404, {"error": "Proceso no encontrado."})

        if not delete_factura(proceso_id, empresa_id, factura_id):
            return req._json(404, {"error": "Factura no encontrada."})

        return req._json(200, {"ok": True})

    except Exception as e:
        print(f"[facturas/eliminar-fila] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al eliminar."})


def _concar(req, empresa_id: str) -> None:
    """POST JSON — generación de archivo CONCAR. Pendiente de implementación."""
    del empresa_id  # se usará cuando se implemente
    return req._json(501, {"error": "Endpoint no implementado aún."})


_ACTIONS = {
    "procesar":      _procesar,
    "actualizar":    _actualizar,
    "recuperar":     _recuperar,
    "eliminar-fila": _eliminar_fila,
    "concar":        _concar,
}


# ─────────────────────────────────────────────────────────────────────────
# Dispatcher — método-agnóstico, rutea solo por ?action=
# ─────────────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_POST(self) -> None:    return self._dispatch()
    def do_PUT(self) -> None:     return self._dispatch()
    def do_GET(self) -> None:     return self._dispatch()
    def do_DELETE(self) -> None:  return self._dispatch()

    def _dispatch(self) -> None:
        action = (parse_qs(urlparse(self.path).query).get("action") or [""])[0]
        fn = _ACTIONS.get(action)
        if fn is None:
            return self._json(400, {
                "error": f"action inválida. Use: {sorted(_ACTIONS)}",
            })

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
