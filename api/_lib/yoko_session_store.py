"""
api/_lib/yoko_session_store.py

Persistencia liviana en Vercel KV de las sessions de Anthropic Managed Agents.
Una `session_id` se asocia a `(empresa_id, user_id)` con TTL deslizante de 4 hrs:
cada lectura renueva el TTL, así un usuario activo no pierde su contexto.

Este módulo NO crea la session en Anthropic (eso lo hace `handler_managed.py`
en la Etapa F). Solo administra el cache de la asociación.

Layout en KV:
  yoko:session:{empresa_id}:{user_id}     -> session_id  (string)
  yoko:session_meta:{session_id}          -> {empresa_id, user_id, created_at, ...}
                                             (JSON, util para auditoria/debug)
"""

import json
import sys
from datetime import datetime, timezone

from . import kv_client
from ._config import SESSION_TTL_SECONDS  # centralizado
from .kv_schema import session_key as _session_key
from .kv_schema import session_metadata_key as _metadata_key


def get_session_id(empresa_id: str, user_id: str) -> str | None:
    """
    Devuelve el `session_id` cacheado para (empresa_id, user_id), o None si
    no existe o expiró. Si lo encuentra, RENUEVA el TTL en ambas claves
    (sliding expiration).
    """
    key = _session_key(empresa_id, user_id)
    sid = kv_client.kv_get(key)
    if sid:
        kv_client.kv_expire(key, SESSION_TTL_SECONDS)
        kv_client.kv_expire(_metadata_key(sid), SESSION_TTL_SECONDS)
    return sid


def store_session(
    empresa_id: str,
    user_id: str,
    session_id: str,
    extra_metadata: dict | None = None,
) -> None:
    """
    Cachea `(empresa_id, user_id) -> session_id` con TTL fresco. También
    guarda metadata indexada por `session_id` para lookup inverso.

    `extra_metadata` permite agregar campos libres (agent_id, etc.) sin
    romper el contrato de los campos base.
    """
    key = _session_key(empresa_id, user_id)
    if not kv_client.kv_set(key, session_id, ttl_seconds=SESSION_TTL_SECONDS):
        print(
            f"[yoko_session_store] kv_set falló para {key}",
            file=sys.stderr,
        )
        return

    metadata = {
        "empresa_id": empresa_id,
        "user_id": user_id,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    kv_client.kv_set(
        _metadata_key(session_id),
        json.dumps(metadata, ensure_ascii=False),
        ttl_seconds=SESSION_TTL_SECONDS,
    )


def force_new_session(empresa_id: str, user_id: str) -> None:
    """
    Borra el `session_id` cacheado para que la próxima request del usuario
    cree una nueva session en Anthropic. NO toca la session del lado
    Anthropic — eso queda colgado hasta su propio TTL server-side.
    """
    key = _session_key(empresa_id, user_id)
    sid = kv_client.kv_get(key)
    kv_client.kv_delete(key)
    if sid:
        kv_client.kv_delete(_metadata_key(sid))


def get_session_metadata(session_id: str) -> dict | None:
    """
    Devuelve la metadata asociada al `session_id` (empresa_id, user_id,
    created_at, extras). Útil para auditoría y debugging.
    """
    raw = kv_client.kv_get(_metadata_key(session_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(
            f"[yoko_session_store] metadata corrupta para {session_id}",
            file=sys.stderr,
        )
        return None
