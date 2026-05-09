"""
api/parse_file.py
Handler HTTP delgado del endpoint /api/parse_file.

El motor de extracción real vive en `api/_lib/extraction/`:
  - `engine.py`           → funciones de bajo nivel (Vision, PDF, Excel, Word).
  - `registry.py`         → registro lazy de templates.
  - `templates/<x>.py`    → un archivo por tipo de documento (factura, caja_chica, ...).

Este archivo solo se encarga de:
  1. Validar JWT y leer la API key de OpenAI del env.
  2. Parsear el multipart con cgi y extraer el archivo.
  3. Resolver el template (query param `?template=` o `?tipo=` legacy).
  4. Delegar al motor: `extract_with_template(...)`.
  5. Devolver el resultado como JSON.

Endpoints:
  POST /api/parse_file?template=<nombre>   → extrae con ese template.
  POST /api/parse_file?tipo=<nombre>       → alias legacy (sigue funcionando).
  POST /api/parse_file                     → default `caja_chica`.
  GET  /api/parse_file?action=list-templates → discovery de templates.

Re-exports legacy: al final del archivo se re-exportan los símbolos
internos que `api/_lib/facturas_processor.py` importa por path directo.
A futuro, ese consumidor se va a migrar a `extract_with_template` y los
re-exports se podrán eliminar.
"""

import cgi
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import auth                                              # noqa: E402
from _lib.auth import AuthError                                    # noqa: E402
from _lib.extraction import (                                      # noqa: E402
    extract_with_template,
    list_templates,
)


# ─────────────────────────────────────────────────────────────────────────
# Handler HTTP
# ─────────────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        # 1) Auth
        try:
            auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        # 2) API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self._json(500, {"error": "OPENAI_API_KEY no configurada."})

        # 3) Resolver template (acepta `template=` nuevo o `tipo=` legacy)
        query_params = parse_qs(urlparse(self.path).query)
        template_name = (
            query_params.get("template")
            or query_params.get("tipo")     # legacy
            or ["caja_chica"]
        )[0]

        # 4) Parsear multipart
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(content_length),
            }
            fs = cgi.FieldStorage(
                fp=io.BytesIO(raw_body),
                environ=environ,
                keep_blank_values=True,
            )

            file_item = fs.getvalue("file") if "file" in fs else None
            filename = ""
            if hasattr(fs["file"], "filename") if "file" in fs else False:
                filename = fs["file"].filename or ""
                file_bytes = fs["file"].file.read()
            elif file_item:
                file_bytes = file_item if isinstance(file_item, bytes) else file_item.encode()
            else:
                return self._json(400, {"error": "No se encontró el campo 'file' en el body."})

            if not file_bytes:
                return self._json(400, {"error": "El archivo está vacío."})

            # 5) Delegar al motor
            result = extract_with_template(file_bytes, filename, template_name, api_key)

            # 6) Respuesta. Por compatibilidad legacy, response top-level
            # mantiene `campos` y `raw_text` como antes; agregamos `template`.
            return self._json(200, result)

        except ValueError as e:
            # Template inexistente o archivo ilegible.
            return self._json(400, {"error": str(e)})
        except json.JSONDecodeError as e:
            return self._json(422, {"error": f"No se pudo parsear la respuesta de IA: {e}"})
        except Exception as e:
            print(f"[parse_file] Error: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": f"Error al procesar el archivo: {type(e).__name__}"})

    def do_GET(self):
        """
        Endpoint de discovery: GET /api/parse_file?action=list-templates
        Devuelve la lista de templates disponibles para que un consumidor
        sepa qué pasar en `?template=`.
        """
        try:
            auth.require_auth(self.headers)
        except AuthError as e:
            return self._json(e.status, {"error": str(e)})

        query_params = parse_qs(urlparse(self.path).query)
        action = (query_params.get("action") or [""])[0]

        if action == "list-templates":
            try:
                return self._json(200, {"templates": list_templates()})
            except Exception as e:
                print(f"[parse_file] Error listando templates: {e}", file=sys.stderr)
                return self._json(500, {"error": "Error obteniendo templates."})

        return self._json(404, {
            "error": "GET no soporta esa action. Use ?action=list-templates.",
        })

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# ═════════════════════════════════════════════════════════════════════════
# COMPATIBILIDAD LEGACY
# ═════════════════════════════════════════════════════════════════════════
# Re-exporta exactamente los 7 símbolos que `api/_lib/facturas_processor.py`
# importa por path directo. CÓDIGO NUEVO debe usar `_lib.extraction.extract_with_template`
# en vez de pegarse a estos símbolos privados — los re-exports se eliminarán
# cuando facturas_processor.py migre a la nueva API.

from _lib.extraction.engine import (                                # noqa: E402, F401
    _extract_via_vision,
    _extract_pdf_pages,
    _extract_from_excel,
    _extract_from_docx,
    _text_to_campos,
)
from _lib.extraction.templates.factura import (                     # noqa: E402, F401
    PROMPT as _EXTRACTION_PROMPT_FACTURA,
    enrich as _enrich_factura_data,
)
