"""
api/_lib/yoko_task_store.py

Persistencia en KV de tasks asíncronos del chat con Managed Agents. El
patrón "kick a worker, return immediately, frontend polls" requiere un
estado compartido entre 3 funciones de Vercel:

  POST /api/chat                    → encola un task con status=pending
  POST /api/chat?action=worker      → corre _run_turn, actualiza estado
  GET  /api/chat?action=status      → lee estado, devuelve al frontend

Layout en KV (una key por task):
  yoko:task:{task_id} → JSON {
    status:        "pending" | "running" | "done" | "error",
    session_id:    "sesn_...",
    user_id:       "...",
    empresa_id:    "...",
    user_content:  "<texto + hints inyectados por handle_post>",
    auth_header:   "<JWT del usuario, para que el worker llame loops>",
    accumulated:   "<texto del bot, se va llenando durante running>",
    error:         null | "<msg>",
    started_at:    1715308800.5,
    finished_at:   null | 1715308860.0,
  }

TTL:
  - 5 min mientras pending/running → si el worker muere abruptamente, el
    task expira solo y no queda basura en KV.
  - 60 s después de done/error → tiempo suficiente para que el último
    poll del frontend lo lea y descarte.

NO usar para datos sensibles a largo plazo. Es estado efímero de un
turno del chat.
"""

import json
import sys
import time
import uuid
from typing import Any

from . import kv_client
from ._config import (  # centralizado
    TASK_TTL_ACTIVE_SECONDS as _TTL_ACTIVE,
    TASK_TTL_FINAL_SECONDS as _TTL_FINAL,
)


_KEY_TPL = "yoko:task:{task_id}"


def _key(task_id: str) -> str:
    return _KEY_TPL.format(task_id=task_id)


def new_task_id() -> str:
    """Genera un task_id corto pero suficientemente único."""
    return uuid.uuid4().hex[:16]


def create(
    task_id: str,
    *,
    session_id: str,
    user_id: str,
    empresa_id: str,
    user_content: str,
    auth_header: str,
) -> bool:
    """
    Persiste un task nuevo con status=pending. Devuelve True si se grabó OK.
    """
    payload = {
        "status":       "pending",
        "session_id":   session_id,
        "user_id":      user_id,
        "empresa_id":   empresa_id,
        "user_content": user_content,
        "auth_header":  auth_header,
        "accumulated":  "",
        "error":        None,
        "started_at":   time.time(),
        "finished_at":  None,
    }
    return kv_client.kv_set(
        _key(task_id),
        json.dumps(payload, ensure_ascii=False),
        ttl_seconds=_TTL_ACTIVE,
    )


def get(task_id: str) -> dict | None:
    """Lee el estado del task. Devuelve None si no existe / expiró."""
    if not task_id:
        return None
    raw = kv_client.kv_get(_key(task_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        print(f"[yoko_task_store] task {task_id} corrupto", file=sys.stderr)
        return None


def update(task_id: str, **fields: Any) -> bool:
    """
    Merge de campos sobre el task existente. Conserva los demás. Si el
    task fue marcado como `done` o `error`, aplica el TTL final corto;
    si sigue activo (pending/running), refresca el TTL activo.
    """
    current = get(task_id)
    if current is None:
        return False
    current.update(fields)

    status = current.get("status")
    ttl = _TTL_FINAL if status in ("done", "error") else _TTL_ACTIVE

    return kv_client.kv_set(
        _key(task_id),
        json.dumps(current, ensure_ascii=False),
        ttl_seconds=ttl,
    )


def delete(task_id: str) -> bool:
    """Borra el task explícitamente (raramente necesario; el TTL lo hace)."""
    return kv_client.kv_delete(_key(task_id))


def mark_running(task_id: str) -> bool:
    return update(task_id, status="running")


def append_accumulated(task_id: str, extra_text: str) -> bool:
    """
    Suma `extra_text` al campo `accumulated`. Útil para que el worker vaya
    publicando el texto del bot a medida que llegan eventos `agent.message`,
    permitiendo streaming UX en el frontend (cada poll ve más texto).
    """
    if not extra_text:
        return True
    current = get(task_id)
    if current is None:
        return False
    current["accumulated"] = (current.get("accumulated") or "") + extra_text
    return kv_client.kv_set(
        _key(task_id),
        json.dumps(current, ensure_ascii=False),
        ttl_seconds=_TTL_ACTIVE,
    )


def mark_done(task_id: str, final_text: str) -> bool:
    return update(
        task_id,
        status="done",
        accumulated=final_text,
        finished_at=time.time(),
    )


def mark_error(task_id: str, error_msg: str) -> bool:
    return update(
        task_id,
        status="error",
        error=error_msg,
        finished_at=time.time(),
    )
