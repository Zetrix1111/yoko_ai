"""
ventas/conversaciones.py — handlers de tres recursos relacionados:

  • resource=conversaciones (GET / DELETE)
       GET                     → lista conversaciones del tenant
       GET    ?id=recXXX       → una sola por ID
       DELETE ?id=recXXX       → borra conversación + sus mensajes

  • resource=mensajes (GET / POST)
       GET    ?conversacion_id=recXXX        → historial ordenado ASC
       POST   body {conversacion_id, role, content}
                                              → INSERT en mensajes (+ outbox si role=human)

  • resource=conversaciones_modo (POST)
       POST   body {conversacion_id, modo}   → toggle AI/HUMAN
"""

import json
import sys

from _lib import airtable_client
from _lib.airtable_client import AirtableError
from _ventas import tenant_id, now_iso


_TABLA_CONV = "conversaciones"
_TABLA_MSGS = "mensajes"
_TABLA_OUTBOX = "outbox"


# ─────────────────────────────────────────────────────────────────────────
# Normalizers
# ─────────────────────────────────────────────────────────────────────────

def _conv_normalize(rec: dict) -> dict:
    f = rec.get("fields", {})
    return {
        "id":              rec.get("id"),
        "empresa_id":      f.get("empresa_id"),
        "phone":           f.get("phone"),
        "nombre":          f.get("nombre"),
        "modo":            f.get("modo", "AI"),
        "last_message_at": f.get("last_message_at"),
        "created_at":      f.get("created_at"),
    }


def _msg_normalize(rec: dict) -> dict:
    f = rec.get("fields", {})
    # conversacion_id es Single line text. Si por algún motivo viene como
    # array (campo cambiado a Linked Record), tomamos el primero.
    conv = f.get("conversacion_id")
    if isinstance(conv, list) and conv:
        conv = conv[0]
    return {
        "id":              rec.get("id"),
        "conversacion_id": conv,
        "empresa_id":      f.get("empresa_id"),
        "role":            f.get("role"),
        "content":         f.get("content", ""),
        "created_at":      f.get("created_at"),
    }


# ─────────────────────────────────────────────────────────────────────────
# resource=conversaciones
# ─────────────────────────────────────────────────────────────────────────

def conversaciones_get(req) -> None:
    try:
        qs = req._qs()
        rec_id = qs.get("id")
        if rec_id:
            rec = airtable_client.get_record(_TABLA_CONV, rec_id)
            return req._json(200, {"conversacion": _conv_normalize(rec)})

        tenant = tenant_id()
        formula = f"{{empresa_id}}='{tenant}'"
        records = airtable_client.list_records(_TABLA_CONV, filter_formula=formula, max_records=100)
        convs = [_conv_normalize(r) for r in records]
        convs.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
        return req._json(200, {"conversaciones": convs})
    except AirtableError as e:
        print(f"[ventas/conversaciones] GET: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo consultar Airtable."})


def conversaciones_delete(req) -> None:
    try:
        qs = req._qs()
        rec_id = qs.get("id")
        if not rec_id:
            return req._json(400, {"error": "Falta query param 'id'."})
        # Borrar mensajes asociados primero (best-effort)
        try:
            msgs = airtable_client.list_records(
                _TABLA_MSGS,
                filter_formula=f"{{conversacion_id}}='{rec_id}'",
                max_records=100,
            )
            for m in msgs:
                airtable_client.delete_record(_TABLA_MSGS, m["id"])
        except AirtableError as e:
            print(f"[ventas/conversaciones] No se pudo borrar mensajes: {e}", file=sys.stderr)

        airtable_client.delete_record(_TABLA_CONV, rec_id)
        return req._json(200, {"ok": True, "id": rec_id})
    except AirtableError as e:
        print(f"[ventas/conversaciones] DELETE: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo eliminar."})


# ─────────────────────────────────────────────────────────────────────────
# resource=mensajes
# ─────────────────────────────────────────────────────────────────────────

def mensajes_get(req) -> None:
    try:
        qs = req._qs()
        conv_id = qs.get("conversacion_id")
        if not conv_id:
            return req._json(400, {"error": "Falta conversacion_id."})
        formula = f"{{conversacion_id}}='{conv_id}'"
        records = airtable_client.list_records(_TABLA_MSGS, filter_formula=formula, max_records=100)
        mensajes = [_msg_normalize(r) for r in records]
        mensajes.sort(key=lambda m: m.get("created_at") or "")
        return req._json(200, {"mensajes": mensajes})
    except AirtableError as e:
        print(f"[ventas/mensajes] GET: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo consultar Airtable."})


def mensajes_post(req) -> None:
    try:
        body = req._read_body()
        conv_id = (body.get("conversacion_id") or "").strip()
        role = (body.get("role") or "human").strip()
        content = (body.get("content") or "").strip()

        if not conv_id:
            return req._json(400, {"error": "Falta conversacion_id."})
        if not content:
            return req._json(400, {"error": "Falta content."})
        if role not in ("user", "assistant", "human"):
            return req._json(400, {"error": "role debe ser user|assistant|human."})

        # Cargar conversación para obtener empresa_id + phone (para outbox)
        conv_rec = airtable_client.get_record(_TABLA_CONV, conv_id)
        conv_f = conv_rec.get("fields", {})
        empresa_id = conv_f.get("empresa_id")
        phone = conv_f.get("phone")
        if not empresa_id or not phone:
            return req._json(400, {"error": "Conversación sin empresa_id o phone."})

        now = now_iso()

        # conversacion_id es Single line text → string, no array
        msg_rec = airtable_client.create_record(_TABLA_MSGS, {
            "conversacion_id": conv_id,
            "empresa_id":      empresa_id,
            "role":            role,
            "content":         content,
            "created_at":      now,
        })

        if role == "human":
            airtable_client.create_record(_TABLA_OUTBOX, {
                "conversacion_id": conv_id,
                "empresa_id":      empresa_id,
                "phone":           phone,
                "content":         content,
                "sent":            False,
                "created_at":      now,
            })

        try:
            airtable_client.update_record(_TABLA_CONV, conv_id, {"last_message_at": now})
        except AirtableError as e:
            print(f"[ventas/mensajes] No se actualizó last_message_at: {e}", file=sys.stderr)

        return req._json(200, {"mensaje": _msg_normalize(msg_rec)})
    except AirtableError as e:
        print(f"[ventas/mensajes] POST: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo guardar el mensaje."})
    except json.JSONDecodeError:
        return req._json(400, {"error": "JSON inválido."})


# ─────────────────────────────────────────────────────────────────────────
# resource=conversaciones_modo
# ─────────────────────────────────────────────────────────────────────────

def modo_post(req) -> None:
    try:
        body = req._read_body()
        conv_id = (body.get("conversacion_id") or "").strip()
        modo = (body.get("modo") or "").strip().upper()

        if not conv_id:
            return req._json(400, {"error": "Falta conversacion_id."})
        if modo not in ("AI", "HUMAN"):
            return req._json(400, {"error": "modo debe ser 'AI' o 'HUMAN'."})

        rec = airtable_client.update_record(_TABLA_CONV, conv_id, {"modo": modo})
        return req._json(200, {
            "ok":   True,
            "id":   rec.get("id"),
            "modo": rec.get("fields", {}).get("modo"),
        })
    except AirtableError as e:
        print(f"[ventas/modo] POST: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo actualizar el modo."})
    except json.JSONDecodeError:
        return req._json(400, {"error": "JSON inválido."})
