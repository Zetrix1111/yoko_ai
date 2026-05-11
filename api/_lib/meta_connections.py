"""
api/_lib/meta_connections.py

Helper para resolver conexiones de Meta Cloud API por empresa o por
phone_number_id. Lee la tabla `meta_connections` de Airtable, que
contiene:

  empresa_id, canal (whatsapp|...), access_token, phone_number_id,
  waba_id, business_id, phone_display, activo, estado_token, ...

Feature flag implícito: una empresa "usa Meta" sii tiene fila con
`activo=TRUE`, `access_token` no vacío Y `phone_number_id` no vacío.
Si no, el flujo legacy de bot-baileys sigue funcionando como antes.

Cache 60s por empresa_id y por phone_number_id. Pattern mismo que
`config_loader._dynamic_cache`. Cold-start lo resetea (esperado en
serverless).

API pública:
  - `get_by_empresa_id(empresa_id) -> dict | None`
  - `get_by_phone_number_id(pid) -> dict | None`
  - `is_meta_active(empresa_id) -> bool`
"""

import sys
import time

from . import airtable_client
from .airtable_client import AirtableError


_TABLA = "meta_connections"
_CACHE_TTL_SECONDS = 60

# Cache: { empresa_id: (expires_at, conn_dict_or_None) }
_cache_by_empresa: dict[str, tuple[float, dict | None]] = {}
# Cache: { phone_number_id: (expires_at, conn_dict_or_None) }
_cache_by_pid: dict[str, tuple[float, dict | None]] = {}


def _normalize(rec: dict) -> dict:
    """Aplana un record al shape que consume el caller."""
    f = rec.get("fields", {}) or {}

    # Algunos campos vienen como objetos {id, name, color} (singleSelect).
    canal = f.get("canal")
    if isinstance(canal, dict):
        canal = canal.get("name")
    estado_token = f.get("estado_token")
    if isinstance(estado_token, dict):
        estado_token = estado_token.get("name")

    return {
        "id":               rec.get("id"),
        "empresa_id":       f.get("empresa_id"),
        "canal":            canal,
        "access_token":     f.get("access_token") or "",
        "phone_number_id":  f.get("phone_number_id") or "",
        "waba_id":          f.get("waba_id") or "",
        "business_id":      f.get("business_id") or "",
        "phone_display":    f.get("phone_display") or "",
        "token_expires_at": f.get("token_expires_at"),
        "estado_token":     estado_token,
        "activo":           bool(f.get("activo")),
    }


def _query(filter_formula: str) -> dict | None:
    """Devuelve el primer record que matchea, normalizado, o None."""
    try:
        rows = airtable_client.list_records(
            _TABLA,
            filter_formula=filter_formula,
            max_records=1,
        )
    except AirtableError as e:
        print(
            f"[meta_connections] Fallback a None. Airtable error: {e}",
            file=sys.stderr,
        )
        return None
    if not rows:
        return None
    return _normalize(rows[0])


def get_by_empresa_id(empresa_id: str) -> dict | None:
    """
    Devuelve la conexión Meta activa de una empresa (con `activo=TRUE`)
    o None si no existe / no está activa.
    """
    if not empresa_id:
        return None

    now = time.time()
    cached = _cache_by_empresa.get(empresa_id)
    if cached and cached[0] > now:
        return cached[1]

    formula = f"AND({{empresa_id}}='{empresa_id}', {{activo}}=TRUE())"
    conn = _query(formula)
    _cache_by_empresa[empresa_id] = (now + _CACHE_TTL_SECONDS, conn)
    # También cacheamos por phone_number_id para evitar lookup doble.
    if conn and conn.get("phone_number_id"):
        _cache_by_pid[conn["phone_number_id"]] = (
            now + _CACHE_TTL_SECONDS, conn,
        )
    return conn


def get_by_phone_number_id(pid: str) -> dict | None:
    """
    Devuelve la conexión Meta activa que matchea un `phone_number_id`.
    Es lo que usa el webhook receptor para resolver a qué empresa
    pertenece un mensaje entrante.
    """
    if not pid:
        return None

    now = time.time()
    cached = _cache_by_pid.get(pid)
    if cached and cached[0] > now:
        return cached[1]

    formula = f"AND({{phone_number_id}}='{pid}', {{activo}}=TRUE())"
    conn = _query(formula)
    _cache_by_pid[pid] = (now + _CACHE_TTL_SECONDS, conn)
    if conn and conn.get("empresa_id"):
        _cache_by_empresa[conn["empresa_id"]] = (
            now + _CACHE_TTL_SECONDS, conn,
        )
    return conn


def is_meta_active(empresa_id: str) -> bool:
    """
    True sii la empresa tiene fila activa con access_token Y
    phone_number_id no vacíos. Si falta cualquiera de los dos, la
    conexión no es usable — fallback a Baileys.
    """
    conn = get_by_empresa_id(empresa_id)
    if not conn:
        return False
    return bool(conn.get("access_token") and conn.get("phone_number_id"))


def invalidate_cache(empresa_id: str | None = None) -> None:
    """
    Limpia el cache. Sin args limpia todo; con empresa_id, solo esa
    entrada (y su phone_number_id asociado si lo tenemos cacheado).
    """
    if empresa_id is None:
        _cache_by_empresa.clear()
        _cache_by_pid.clear()
        return

    entry = _cache_by_empresa.pop(empresa_id, None)
    if entry and entry[1] and entry[1].get("phone_number_id"):
        _cache_by_pid.pop(entry[1]["phone_number_id"], None)
