"""
api/_ventas/meta_status.py — endpoint para verificar el estado de la
conexión Meta Cloud API del tenant.

GET /api/ventas?resource=meta_status (JWT requerido)

Flujo:
  1. Lee la fila de `meta_connections` para el `empresa_id` del JWT.
  2. Hace ping a `https://graph.facebook.com/v23.0/me` con el access_token.
  3. Actualiza `estado_token` en Airtable según resultado.
  4. Devuelve resumen JSON al frontend.

Mapeo conservador del estado a las opciones del singleSelect existente:
  - Ping 200 OK → `"∞ no expira"` (asume token permanente)
  - Ping 401   → `"❌ VENCIDO"`
  - Otro error (red, 5xx) → NO actualiza el campo, solo devuelve detalle
    (preserva el estado previo, no hay info confiable para sobrescribir).

NO calcula días reales hasta expiración. Si el owner quiere granularidad
(`"✅ ok (Xd)"`, `"⚠ vence en 12d"`), es una iteración separada.
"""

import json
import sys
import urllib.error
import urllib.request

from _lib import meta_connections, airtable_client
from _lib.airtable_client import AirtableError


_TABLA = "meta_connections"
_GRAPH_BASE = "https://graph.facebook.com/v23.0"


def meta_status_get(req, empresa_id: str) -> None:
    """
    Devuelve el estado de la conexión Meta para la empresa del JWT.
    Forma de la response:
      {connected: bool, estado_token: str|None, phone_display: str|None,
       waba_id: str|None, detail: str, reason?: str}
    """
    conn = meta_connections.get_by_empresa_id(empresa_id)
    if not conn:
        return req._json(404, {
            "connected": False,
            "reason":    "no_record",
            "detail":    "Sin fila activa en meta_connections para esta empresa.",
        })

    token = conn.get("access_token")
    if not token:
        return req._json(200, {
            "connected":    False,
            "reason":       "no_token",
            "estado_token": conn.get("estado_token"),
            "detail":       "La fila existe pero no tiene access_token cargado.",
        })

    # Ping a /me — la forma más liviana de validar el token.
    url = f"{_GRAPH_BASE}/me?access_token={token}"
    new_estado = None
    ok = False
    detail = ""
    try:
        with urllib.request.urlopen(url, timeout=10) as res:
            body = json.loads(res.read())
        new_estado = "∞ no expira"  # opción del singleSelect en Airtable
        ok = True
        detail = body.get("id", "")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            new_estado = "❌ VENCIDO"
            detail = "HTTP 401 (token inválido o expirado)"
        else:
            # 4xx no-auth / 5xx: no confiable para sobrescribir estado.
            detail = f"HTTP {e.code}"
            print(f"[meta_status] ping fallo no-401: {detail}", file=sys.stderr)
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        print(f"[meta_status] {detail}", file=sys.stderr)

    # Actualizar estado_token solo si tenemos un valor confiable (OK o 401).
    # En otros casos preservamos el valor previo en Airtable.
    if new_estado is not None:
        try:
            airtable_client.update_record(
                _TABLA, conn["id"], {"estado_token": new_estado},
            )
            meta_connections.invalidate_cache(empresa_id)
        except AirtableError as e:
            print(
                f"[meta_status] no se pudo actualizar estado_token: {e}",
                file=sys.stderr,
            )

    return req._json(200, {
        "connected":     ok,
        "estado_token":  new_estado if new_estado is not None else conn.get("estado_token"),
        "phone_display": conn.get("phone_display"),
        "waba_id":       conn.get("waba_id"),
        "detail":        detail,
    })
