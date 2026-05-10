"""
api/_yoko/handler_status.py — endpoint GET de polling del task async.

Invocado por el frontend desde `useChat.js` mientras espera la respuesta
del agent: hace polling cada 1.5s a `GET /api/chat?action=status&task_id=X`
hasta que el task termina (`done` / `error`).

Auth: JWT del usuario (mismo que el resto del chat). NO usar el token
interno acá — esto es público para el frontend.

Response shape:
  {
    "status": "pending" | "running" | "done" | "error",
    "text":   "<texto acumulado del bot, parcial mientras corre>",
    "error":  null | "<mensaje>",
  }
"""

import sys
from urllib.parse import parse_qs, urlparse

from _lib import auth, yoko_task_store
from _lib.auth import AuthError


def handle_get(req) -> None:
    # Auth: JWT del usuario.
    try:
        auth.require_auth(req.headers)
    except AuthError as e:
        return req._json(e.status, {"error": str(e)})

    parsed = urlparse(req.path)
    qs = parse_qs(parsed.query or "")
    task_id = (qs.get("task_id") or [""])[0].strip()
    if not task_id:
        return req._json(400, {"error": "task_id requerido"})

    task = yoko_task_store.get(task_id)
    if task is None:
        # Puede ser que expiró (TTL) o que nunca existió. Tratamos igual:
        # el frontend interpreta como "error transitorio, mostrá fallback".
        return req._json(404, {
            "status": "expired",
            "error":  "Task no encontrado o expirado.",
        })

    # NO devolvemos campos sensibles como auth_header.
    return req._json(200, {
        "status": task.get("status"),
        "text":   task.get("accumulated") or "",
        "error":  task.get("error"),
    })


def handle_post(req) -> None:
    """Compat por si llaman con POST por error."""
    return handle_get(req)
