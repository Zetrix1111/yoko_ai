"""
api/facturas.py — dispatcher de Facturas Inteligentes.

Único archivo serverless del módulo. Consolida múltiples acciones en un
solo dispatcher por `?action=` y método HTTP libre (cada action sabe
qué método espera y parsea el body acorde).

Acciones del flujo web (UI clásica):
  POST   /api/facturas?action=procesar       → multipart, procesa N archivos
  PUT    /api/facturas?action=actualizar     → JSON, auto-save de ediciones
  GET    /api/facturas?action=recuperar      → ?proceso_id=…, recupera proceso
  DELETE /api/facturas?action=eliminar-fila  → JSON, borra una factura
  POST   /api/facturas?action=concar         → genera y descarga el Excel del registro
                                                contable (CONCAR/SISCONT/etc. según
                                                Config_Empresa.basicos.sistema_contable)

Acciones consumidas por el agent (Anthropic Managed Agents → custom tools):
  POST   /api/facturas?action=procesar-chat          → JSON+base64, equivalente a procesar
  POST   /api/facturas?action=recuperar-chat         → JSON {proceso_id}, equivalente a recuperar
  POST   /api/facturas?action=registro-contable-chat → JSON {proceso_id}, validación liviana
                                                        para que el agent confirme que el
                                                        archivo está listo (no devuelve bytes).

Todas validan JWT en el dispatcher; `empresa_id` se extrae del token.
"""

import base64
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
from _lib.registro_contable import engine as registro_contable_engine  # noqa: E402


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
    """
    POST JSON — genera el Excel del registro contable para descarga.

    Body: {proceso_id}

    Wrapper delgado sobre `registro_contable.engine.generate()`. El motor
    resuelve qué template usar según `Config_Empresa.basicos.sistema_contable`
    (CONCAR hoy; SISCONT/etc. cuando se sumen templates) y devuelve los bytes.

    Response: binary stream `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
    con `Content-Disposition: attachment; filename="REGISTRO_<proceso>.xlsx"`.
    El frontend lo guarda como blob y dispara la descarga.

    El nombre de la action se mantiene como `concar` por compat con el
    botón "Descargar Excel CONCAR" del frontend; el archivo en sí ya no es
    necesariamente CONCAR.
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
        if not proceso_id:
            return req._json(400, {"error": "proceso_id requerido."})

        try:
            out = registro_contable_engine.generate(proceso_id, empresa_id)
        except ValueError as e:
            # Proceso inexistente, sin facturas, o sistema_contable no soportado.
            status = 404 if "no encontrado" in str(e).lower() else 400
            return req._json(status, {"error": str(e)})
        except Exception as e:
            print(f"[facturas/concar] Error generando xlsx: {type(e).__name__}: {e}", file=sys.stderr)
            return req._json(500, {"error": "Error al generar el Excel."})

        print(
            f"[facturas/concar] {proceso_id} sistema={out['sistema']}: "
            f"{out['num_facturas']} facturas → {out['num_filas']} filas",
            file=sys.stderr,
        )

        xlsx_bytes = out["content"]
        req.send_response(200)
        req.send_header("Content-Type", out["content_type"])
        req.send_header("Content-Disposition", f'attachment; filename="{out["filename"]}"')
        req.send_header("Content-Length", str(len(xlsx_bytes)))
        req.end_headers()
        req.wfile.write(xlsx_bytes)

    except Exception as e:
        print(f"[facturas/concar] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al generar el archivo."})


def _procesar_chat(req, empresa_id: str) -> None:
    """
    POST JSON — variante "chat-friendly" de procesar.

    En vez de multipart, recibe los archivos en base64 dentro del JSON, que
    es como Anthropic Managed Agents le pasa el lote al custom tool
    `yoko_procesar_archivos`. Reusa exactamente la misma lógica de extracción
    que `_procesar`.

    Body:
      {
        "tipo":  "compra" | "venta",
        "mes":   "YYYY-MM",
        "files": [{"filename": "...", "content_b64": "..."}]   # ≤ 50
      }

    Response: {ok, proceso_id, empresa_id, facturas, errores, alertas, timestamp}
    """
    try:
        init_db()

        length = int(req.headers.get("Content-Length", 0))
        if length == 0:
            return req._json(400, {"error": "Body vacío."})
        try:
            body = json.loads(req.rfile.read(length))
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido."})

        tipo     = (body.get("tipo") or "compra").strip().lower()
        mes      = (body.get("mes") or "").strip()
        files_in = body.get("files") or []

        if tipo not in ("compra", "venta"):
            return req._json(400, {"error": "tipo debe ser 'compra' o 'venta'."})
        if not isinstance(files_in, list) or not files_in:
            return req._json(400, {"error": "files debe ser una lista no vacía."})
        if len(files_in) > 50:
            return req._json(400, {"error": "Máximo 50 archivos por lote."})

        # Decodificar base64 → list[(filename, bytes)]
        files: list[tuple[str, bytes]] = []
        for i, item in enumerate(files_in):
            if not isinstance(item, dict):
                return req._json(400, {
                    "error": f"files[{i}] debe ser objeto con filename+content_b64.",
                })
            fname = (item.get("filename") or "").strip()
            content_b64 = item.get("content_b64") or ""
            if not fname or not content_b64:
                return req._json(400, {
                    "error": f"files[{i}] requiere filename y content_b64 no vacíos.",
                })
            try:
                fbytes = base64.b64decode(content_b64, validate=True)
            except (ValueError, base64.binascii.Error):
                return req._json(400, {"error": f"files[{i}] content_b64 no es base64 válido."})
            if not fbytes:
                return req._json(400, {"error": f"files[{i}] vacío tras decodificar."})
            files.append((fname, fbytes))

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

        revision_marker = f"[ABRIR_REVISION:{proceso_id}]"

        return req._json(200, {
            "ok":              True,
            "proceso_id":      proceso_id,
            "empresa_id":      empresa_id,
            "facturas":        resultado["facturas"],
            "errores":         resultado["errores"],
            "alertas":         [],
            "timestamp":       time.time(),
            "revision_marker": revision_marker,
            "mensaje_revision": (
                f"El usuario puede revisar y editar los "
                f"{len(resultado['facturas'])} comprobantes extraídos en la "
                f"pantalla web. Para que aparezca el botón clickeable en el "
                f"chat, INCLUÍ al final de tu respuesta esta línea EXACTA, "
                f"sin modificarla, sin envolverla en código, sin emojis "
                f"pegados ni paréntesis: {revision_marker}"
            ),
        })

    except ValueError as e:
        print(f"[facturas/procesar-chat] ValueError: {e}", file=sys.stderr)
        return req._json(400, {"error": str(e)})
    except Exception as e:
        print(f"[facturas/procesar-chat] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al procesar facturas."})


def _recuperar_chat(req, empresa_id: str) -> None:
    """
    POST JSON — variante de recuperar pensada para el agent.

    Diferencia con `_recuperar` (que es GET con ?proceso_id=…): el agent
    llama esto en POST con body JSON, que es la forma natural en la que
    Anthropic invoca un custom tool.

    Body: {"proceso_id": "..."}
    Response: {ok, proceso_id, facturas, timestamp}
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
        if not proceso_id:
            return req._json(400, {"error": "proceso_id requerido."})

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
        print(f"[facturas/recuperar-chat] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al recuperar proceso."})


def _registro_contable_chat(req, empresa_id: str) -> None:
    """
    POST JSON — validación liviana del registro contable. Invocado por el
    custom tool `yoko_generar_registro_contable` del agent.

    NO genera bytes. Solo verifica que el proceso esté listo para ser
    descargado desde la UI web (existe, tiene facturas, su sistema_contable
    resuelve a un template registrado) y devuelve metadata para que el
    agent confirme al usuario que el archivo está disponible.

    Body:     {"proceso_id": "..."}
    Response: {ok, sistema, num_facturas, num_filas_estimado, mensaje}
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
        if not proceso_id:
            return req._json(400, {"error": "proceso_id requerido."})

        try:
            out = registro_contable_engine.validate(proceso_id, empresa_id)
        except ValueError as e:
            status = 404 if "no encontrado" in str(e).lower() else 400
            return req._json(status, {"error": str(e)})

        download_marker = f"[DESCARGAR_REGISTRO:{proceso_id}]"

        return req._json(200, {
            "ok":                 out["ok"],
            "proceso_id":         proceso_id,
            "sistema":            out["sistema"],
            "num_facturas":       out["num_facturas"],
            "num_filas_estimado": out["num_filas_estimado"],
            "download_marker":    download_marker,
            "mensaje": (
                f"El registro contable está listo ({out['num_facturas']} "
                f"comprobantes, {out['num_filas_estimado']} filas, formato "
                f"{out['sistema'].upper()}). Para que el usuario pueda "
                f"descargarlo desde el chat, INCLUÍ al final de tu respuesta "
                f"la línea EXACTA, sin modificarla: {download_marker}"
            ),
        })

    except Exception as e:
        print(f"[facturas/registro-contable-chat] Error: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error al validar el registro contable."})


_ACTIONS = {
    # Flujo web (UI clásica)
    "procesar":      _procesar,
    "actualizar":    _actualizar,
    "recuperar":     _recuperar,
    "eliminar-fila": _eliminar_fila,
    "concar":        _concar,
    # Flujo chat (Anthropic Managed Agents → custom tools)
    "procesar-chat":          _procesar_chat,
    "recuperar-chat":         _recuperar_chat,
    "registro-contable-chat": _registro_contable_chat,
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
