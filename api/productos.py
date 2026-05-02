"""
api/productos.py — CRUD del catálogo de productos (módulo Ventas Inteligentes).

Tabla Airtable: `productos`
Campos esperados:
  • nombre (Single line text, requerido)
  • descripcion (Long text)
  • precio (Currency)
  • foto (Attachment | URL — ver nota abajo)
  • stock (Number, vacío = servicio)
  • stock_minimo (Number)
  • categoria (Single select, opcional)
  • activo (Checkbox)
  • empresa_id (Single line text — multi-tenant)
  • keywords (Long text — sinónimos para búsqueda)

Sobre fotos: este endpoint acepta un URL público en `foto` (string).
Subir archivos directamente a Airtable Attachment requiere o una URL
pública o upload vía base64 a su CDN. Por ahora MVP guarda URL externa
(o vacío). Cuando tengamos blob storage propio se conectará el upload.

Métodos:
  GET                       → listar productos del tenant activo
  GET    ?id=recXXX         → obtener un producto por ID
  POST                      → crear (body JSON)
  PATCH  ?id=recXXX         → actualizar (body JSON)
  DELETE ?id=recXXX         → eliminar
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

# Permitir importar desde api/_lib/ aunque la función serverless se ejecute
# con un cwd diferente al repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                                    # noqa: E402
from _lib.airtable_client import AirtableError                      # noqa: E402


_TABLA = "productos"
_FALLBACK_TENANT = "cmejia"


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


def _normalize_record(rec: dict) -> dict:
    """Aplana un record de Airtable al shape que consume el frontend."""
    f = rec.get("fields", {})
    foto_field = f.get("foto")
    foto_url = None
    if isinstance(foto_field, list) and foto_field:
        # Airtable Attachment: lista de {url, filename, ...}
        foto_url = foto_field[0].get("url")
    elif isinstance(foto_field, str):
        foto_url = foto_field
    return {
        "id":           rec.get("id"),
        "nombre":       f.get("nombre", ""),
        "descripcion":  f.get("descripcion", ""),
        "precio":       f.get("precio", 0),
        "foto":         foto_url,
        "stock":        f.get("stock"),
        "stockMinimo":  f.get("stock_minimo"),
        "categoria":    f.get("categoria"),
        "activo":       bool(f.get("activo", True)),
        "keywords":     f.get("keywords", ""),
    }


def _to_airtable_fields(payload: dict) -> dict:
    """Convierte el payload del frontend (camelCase) al schema Airtable (snake_case)."""
    fields = {}
    if "nombre" in payload:        fields["nombre"]       = payload["nombre"]
    if "descripcion" in payload:   fields["descripcion"]  = payload["descripcion"]
    if "precio" in payload:        fields["precio"]       = float(payload["precio"] or 0)
    if "stock" in payload:         fields["stock"]        = payload["stock"]  # puede ser None
    if "stockMinimo" in payload:   fields["stock_minimo"] = payload["stockMinimo"]
    if "categoria" in payload:     fields["categoria"]    = payload["categoria"]
    if "activo" in payload:        fields["activo"]       = bool(payload["activo"])
    if "keywords" in payload:      fields["keywords"]     = payload["keywords"]
    # Foto: aceptamos URL string. Para Airtable Attachment se envía como
    # lista [{"url": "..."}]. Si el cliente manda null/empty lo dejamos vacío.
    if "foto" in payload:
        foto = payload["foto"]
        if foto and isinstance(foto, str) and foto.startswith(("http://", "https://")):
            fields["foto"] = [{"url": foto}]
        elif not foto:
            fields["foto"] = []
        # Si es un blob:// (preview local del modal), lo ignoramos: no se puede
        # subir a Airtable directamente. Frontend deberá usar upload aparte.
    return fields


class handler(BaseHTTPRequestHandler):

    # ── GET: listar todos / obtener uno ──────────────────────────────────
    def do_GET(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            rec_id = (qs.get("id") or [None])[0]

            if rec_id:
                rec = airtable_client.get_record(_TABLA, rec_id)
                return self._json(200, {"producto": _normalize_record(rec)})

            tenant = _tenant_id()
            formula = f"{{empresa_id}}='{tenant}'"
            records = airtable_client.list_records(_TABLA, filter_formula=formula, max_records=100)
            productos = [_normalize_record(r) for r in records]
            return self._json(200, {"productos": productos})

        except AirtableError as e:
            print(f"[productos] AirtableError GET: {e}")
            return self._json(502, {"error": "No se pudo consultar Airtable."})
        except Exception as e:
            print(f"[productos] Error GET: {type(e).__name__}: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ── POST: crear ──────────────────────────────────────────────────────
    def do_POST(self):
        try:
            payload = self._read_body()
            if not payload.get("nombre"):
                return self._json(400, {"error": "El campo 'nombre' es requerido."})

            fields = _to_airtable_fields(payload)
            fields["empresa_id"] = _tenant_id()
            # Default activo si no se especifica
            fields.setdefault("activo", True)

            rec = airtable_client.create_record(_TABLA, fields)
            return self._json(200, {"producto": _normalize_record(rec)})

        except AirtableError as e:
            print(f"[productos] AirtableError POST: {e}")
            return self._json(502, {"error": "No se pudo crear el producto."})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido en el cuerpo."})
        except Exception as e:
            print(f"[productos] Error POST: {type(e).__name__}: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ── PATCH: actualizar ────────────────────────────────────────────────
    def do_PATCH(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            rec_id = (qs.get("id") or [None])[0]
            if not rec_id:
                return self._json(400, {"error": "Falta query param 'id'."})

            payload = self._read_body()
            fields = _to_airtable_fields(payload)
            if not fields:
                return self._json(400, {"error": "Body sin campos válidos para actualizar."})

            rec = airtable_client.update_record(_TABLA, rec_id, fields)
            return self._json(200, {"producto": _normalize_record(rec)})

        except AirtableError as e:
            print(f"[productos] AirtableError PATCH: {e}")
            return self._json(502, {"error": "No se pudo actualizar el producto."})
        except json.JSONDecodeError:
            return self._json(400, {"error": "JSON inválido en el cuerpo."})
        except Exception as e:
            print(f"[productos] Error PATCH: {type(e).__name__}: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ── DELETE: eliminar ─────────────────────────────────────────────────
    def do_DELETE(self):
        try:
            qs = parse_qs(urlparse(self.path).query)
            rec_id = (qs.get("id") or [None])[0]
            if not rec_id:
                return self._json(400, {"error": "Falta query param 'id'."})

            airtable_client.delete_record(_TABLA, rec_id)
            return self._json(200, {"ok": True, "id": rec_id})

        except AirtableError as e:
            print(f"[productos] AirtableError DELETE: {e}")
            return self._json(502, {"error": "No se pudo eliminar el producto."})
        except Exception as e:
            print(f"[productos] Error DELETE: {type(e).__name__}: {e}")
            return self._json(500, {"error": "Error interno del servidor."})

    # ── Helpers ──────────────────────────────────────────────────────────
    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
