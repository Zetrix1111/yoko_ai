"""
ventas/wa.py — handlers para resource=wa (sesión WhatsApp).

GET  /api/ventas?resource=wa[&empresa_id=...]
   → estado actual de la sesión Baileys del tenant.

POST /api/ventas?resource=wa&action=connect
   body: {"empresa_id"?: "..."}
   → upsert wa_sessions con status='qr' (señal al bot para iniciar pairing).

POST /api/ventas?resource=wa&action=disconnect
   body: {"empresa_id"?: "..."}
   → marca status='disconnected' (el bot detecta y cierra Baileys).
"""

import json
import sys

from _lib import airtable_client
from _lib.airtable_client import AirtableError
from _ventas import tenant_id


_TABLA_WA = "wa_sessions"


def _find_session(empresa_id: str) -> dict | None:
    formula = f"{{empresa_id}}='{empresa_id}'"
    records = airtable_client.list_records(
        _TABLA_WA, filter_formula=formula, max_records=1,
    )
    return records[0] if records else None


def _normalize(rec: dict | None) -> dict | None:
    if not rec:
        return None
    f = rec.get("fields", {})
    return {
        "id":            rec.get("id"),
        "empresa_id":    f.get("empresa_id"),
        "status":        f.get("status", "disconnected"),
        "qr_string":     f.get("qr_string"),
        "phone":         f.get("phone"),
        "connected_at":  f.get("connected_at"),
        "last_seen_at":  f.get("last_seen_at"),
    }


def wa_get(req) -> None:
    try:
        qs = req._qs()
        empresa_id = qs.get("empresa_id") or tenant_id()
        rec = _find_session(empresa_id)
        if rec is None:
            return req._json(200, {"session": {
                "empresa_id": empresa_id,
                "status":     "disconnected",
                "qr_string":  None,
                "phone":      None,
            }})
        return req._json(200, {"session": _normalize(rec)})
    except AirtableError as e:
        print(f"[ventas/wa] AirtableError GET: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo consultar Airtable."})


def wa_post(req) -> None:
    try:
        qs = req._qs()
        action = qs.get("action")
        body = req._read_body()
        empresa_id = (body.get("empresa_id") or "").strip() or tenant_id()

        if action == "connect":
            existing = _find_session(empresa_id)
            fields = {
                "empresa_id": empresa_id,
                "status":     "qr",
                "qr_string":  "",
                "phone":      "",
            }
            if existing:
                rec = airtable_client.update_record(_TABLA_WA, existing["id"], fields)
            else:
                rec = airtable_client.create_record(_TABLA_WA, fields)
            return req._json(200, {"session": _normalize(rec)})

        if action == "disconnect":
            existing = _find_session(empresa_id)
            if not existing:
                return req._json(200, {"ok": True, "note": "Tenant sin sesión."})
            rec = airtable_client.update_record(
                _TABLA_WA, existing["id"],
                {"status": "disconnected", "qr_string": "", "phone": ""},
            )
            return req._json(200, {"session": _normalize(rec)})

        return req._json(400, {"error": "action debe ser 'connect' o 'disconnect'."})
    except AirtableError as e:
        print(f"[ventas/wa] AirtableError POST: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo escribir en Airtable."})
    except json.JSONDecodeError:
        return req._json(400, {"error": "JSON inválido."})
