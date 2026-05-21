"""
api/_yoko/handler_reset.py — endpoint POST para forzar una nueva sesión
Claude Managed Agents para el usuario autenticado.

Casos de uso:
  - Tras cambiar la config de la empresa (ej. requiere_aprobacion), el agent
    ya tiene la sesión vieja con el contexto previo. Esto descarta la
    asociación (empresa_id, user_id) → session_id del KV; la próxima request
    crea una sesión nueva con el `<contexto_empresa>` actualizado.
  - Debugging: forzar arranque limpio sin esperar el TTL de 4hrs.

NO borra la sesión del lado Anthropic — queda colgada hasta su TTL
server-side. Solo invalida el cache local.

Auth: JWT del usuario.
"""

import sys

from _lib import auth, yoko_cart_store, yoko_session_store
from _lib.auth import AuthError


def handle_post(req) -> None:
    try:
        auth_payload = auth.require_auth(req.headers)
    except AuthError as e:
        return req._json(e.status, {"error": str(e)})

    empresa_id = auth_payload["empresa_id"]
    user_id = (auth_payload.get("dni") or auth_payload.get("sub") or "").strip()
    if not user_id:
        return req._json(400, {"error": "No se pudo identificar al usuario."})

    # Capturar el session_id antes de borrarlo para vaciar el carrito asociado.
    prev_session_id = yoko_session_store.get_session_id(empresa_id, user_id)

    try:
        yoko_session_store.force_new_session(empresa_id, user_id)
    except Exception as e:
        print(
            f"[chat/reset] force_new_session falló: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return req._json(502, {"error": "No se pudo resetear la sesión."})

    if prev_session_id:
        try:
            yoko_cart_store.clear_cart(prev_session_id)
        except Exception:
            pass

    print(
        f"[chat/reset] sesión reseteada para {empresa_id}/{user_id} "
        f"(prev={prev_session_id})",
        file=sys.stderr,
    )
    return req._json(200, {"ok": True, "prev_session_id": prev_session_id})
