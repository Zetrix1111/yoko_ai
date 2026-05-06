"""
ventas/productos.py — CRUD del catálogo de productos del tenant.

Tabla Airtable: `productos` (multi-tenant por `empresa_id`).
Campos: nombre, descripcion, precio, foto (URL), stock, stock_minimo,
categoria, activo, empresa_id, keywords.

Resources del dispatcher:
  GET    /api/ventas?resource=productos              → lista del tenant
  GET    /api/ventas?resource=productos&id=recXXX    → uno
  POST   /api/ventas?resource=productos              → crear (body JSON)
  PATCH  /api/ventas?resource=productos&id=recXXX    → actualizar (body JSON)
  DELETE /api/ventas?resource=productos&id=recXXX    → eliminar

`empresa_id` siempre se extrae del JWT por el dispatcher; cualquier valor
del body se ignora (cross-tenant guard).
"""

import json
import sys

from _lib import airtable_client
from _lib.airtable_client import AirtableError


_TABLA = "productos"


def _normalize_record(rec: dict) -> dict:
    """Aplana un record de Airtable al shape que consume el frontend."""
    f = rec.get("fields", {})
    foto_field = f.get("foto")
    foto_url = None
    if isinstance(foto_field, list) and foto_field:
        foto_url = foto_field[0].get("url")
    elif isinstance(foto_field, str):
        foto_url = foto_field
    return {
        "id":          rec.get("id"),
        "nombre":      f.get("nombre", ""),
        "descripcion": f.get("descripcion", ""),
        "precio":      f.get("precio", 0),
        "foto":        foto_url,
        "stock":       f.get("stock"),
        "stockMinimo": f.get("stock_minimo"),
        "categoria":   f.get("categoria"),
        "activo":      bool(f.get("activo", True)),
        "keywords":    f.get("keywords", ""),
    }


def _to_airtable_fields(payload: dict) -> dict:
    """Convierte el payload del frontend (camelCase) al schema Airtable (snake_case)."""
    fields: dict = {}
    if "nombre" in payload:      fields["nombre"]       = payload["nombre"]
    if "descripcion" in payload: fields["descripcion"]  = payload["descripcion"]
    if "precio" in payload:      fields["precio"]       = float(payload["precio"] or 0)
    if "stock" in payload:       fields["stock"]        = payload["stock"]
    if "stockMinimo" in payload: fields["stock_minimo"] = payload["stockMinimo"]
    if "categoria" in payload:   fields["categoria"]    = payload["categoria"]
    if "activo" in payload:      fields["activo"]       = bool(payload["activo"])
    if "keywords" in payload:    fields["keywords"]     = payload["keywords"]
    if "foto" in payload:
        foto = payload["foto"]
        if foto and isinstance(foto, str) and foto.startswith(("http://", "https://")):
            fields["foto"] = foto
        elif not foto:
            fields["foto"] = ""
    return fields


# ─────────────────────────────────────────────────────────────────────────
# Handlers — invocados por api/ventas.py vía _DISPATCH_AUTH
# ─────────────────────────────────────────────────────────────────────────

def productos_get(req, empresa_id: str) -> None:
    """GET: lista todos los productos del tenant, o uno por ?id=recXXX."""
    try:
        rec_id = req._qs().get("id")
        if rec_id:
            try:
                rec = airtable_client.get_record(_TABLA, rec_id)
            except AirtableError as e:
                if e.status == 404:
                    return req._json(404, {"error": "Producto no encontrado."})
                raise
            if (rec.get("fields", {}) or {}).get("empresa_id") != empresa_id:
                return req._json(404, {"error": "Producto no encontrado."})
            return req._json(200, {"producto": _normalize_record(rec)})

        formula = f"{{empresa_id}}='{empresa_id}'"
        records = airtable_client.list_records(_TABLA, filter_formula=formula, max_records=100)
        productos = [_normalize_record(r) for r in records]
        return req._json(200, {"productos": productos})

    except AirtableError as e:
        print(f"[ventas/productos] AirtableError GET: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo consultar Airtable."})


def productos_post(req, empresa_id: str) -> None:
    """POST: crear producto. `empresa_id` viene del JWT, ignora el del body."""
    try:
        try:
            payload = req._read_body()
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido en el cuerpo."})

        if not payload.get("nombre"):
            return req._json(400, {"error": "El campo 'nombre' es requerido."})

        fields = _to_airtable_fields(payload)
        fields["empresa_id"] = empresa_id
        fields.setdefault("activo", True)

        rec = airtable_client.create_record(_TABLA, fields)
        return req._json(200, {"producto": _normalize_record(rec)})

    except AirtableError as e:
        print(f"[ventas/productos] AirtableError POST: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo crear el producto."})


def productos_patch(req, empresa_id: str) -> None:
    """PATCH: actualizar producto. Cross-tenant guard por empresa_id."""
    try:
        rec_id = req._qs().get("id")
        if not rec_id:
            return req._json(400, {"error": "Falta query param 'id'."})

        try:
            existing = airtable_client.get_record(_TABLA, rec_id)
        except AirtableError as e:
            if e.status == 404:
                return req._json(404, {"error": "Producto no encontrado."})
            raise
        if (existing.get("fields", {}) or {}).get("empresa_id") != empresa_id:
            return req._json(404, {"error": "Producto no encontrado."})

        try:
            payload = req._read_body()
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido en el cuerpo."})

        fields = _to_airtable_fields(payload)
        if not fields:
            return req._json(400, {"error": "Body sin campos válidos para actualizar."})
        fields.pop("empresa_id", None)  # nunca cambiar empresa_id desde el body

        rec = airtable_client.update_record(_TABLA, rec_id, fields)
        return req._json(200, {"producto": _normalize_record(rec)})

    except AirtableError as e:
        print(f"[ventas/productos] AirtableError PATCH: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo actualizar el producto."})


def productos_delete(req, empresa_id: str) -> None:
    """DELETE: borrar producto. Cross-tenant guard por empresa_id."""
    try:
        rec_id = req._qs().get("id")
        if not rec_id:
            return req._json(400, {"error": "Falta query param 'id'."})

        try:
            existing = airtable_client.get_record(_TABLA, rec_id)
        except AirtableError as e:
            if e.status == 404:
                return req._json(404, {"error": "Producto no encontrado."})
            raise
        if (existing.get("fields", {}) or {}).get("empresa_id") != empresa_id:
            return req._json(404, {"error": "Producto no encontrado."})

        airtable_client.delete_record(_TABLA, rec_id)
        return req._json(200, {"ok": True, "id": rec_id})

    except AirtableError as e:
        print(f"[ventas/productos] AirtableError DELETE: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo eliminar el producto."})
