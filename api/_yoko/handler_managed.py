"""
api/_yoko/handler_managed.py — backend Managed Agents del POST /api/chat.

Activado cuando `YOKO_BACKEND=managed_agents`. Tiene la misma firma que el
handler.py legacy (`handle_post(req)`), así api/chat.py no se entera del
cambio de backend.

Flujo (protocolo real de la beta `managed-agents-2026-04-01`):
  1. Auth JWT (mismo que legacy).
  2. session.extract_user(body) (mismo que legacy).
  3. Resolver Vault de la empresa (env vars por empresa).
  4. yoko_session_store.get_session_id(empresa_id, user_id):
       - Si existe → reusar.
       - Si no → mac.create_session(...) + cachear. El contexto de empresa se
         prepende al primer mensaje del usuario en vez de mandarse como evento
         aparte (más eficiente: evita una corrida del agent solo para "leer"
         el contexto).
  5. Abrir stream `GET /v1/sessions/{id}/events/stream` ANTES de mandar el
     user.message (si no, perdemos eventos del primer turno).
  6. POST user.message a `/v1/sessions/{id}/events`.
  7. Leer eventos del stream:
       - `agent.message`           → acumular text blocks.
       - `agent.custom_tool_use`   → guardar (id, name, input).
       - `session.status_idle`:
            stop_reason=`requires_action` → ejecutar tools, mandar
                                            `user.custom_tool_result`, seguir
                                            leyendo el stream.
            stop_reason=`end_turn`        → terminar turno y devolver texto.
       - `session.error`           → loguear y cortar.
  8. Devolver `{"text": "...", "action": null}` al frontend.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from _lib import auth, session
from _lib import managed_agents_client as mac
from _lib import (
    yoko_cart_store,
    yoko_context_builder,
    yoko_session_store,
    yoko_task_store,
)
from _lib.airtable_client import AirtableError
from _lib.auth import AuthError


_REQUIRED_ENV = (
    "ANTHROPIC_API_KEY",
    "YOKO_AGENT_ID",
    "KV_REST_API_URL",
    "KV_REST_API_TOKEN",
)

# Mapeo nombre del custom tool → action en /api/facturas. Si un tool nuevo
# aparece, agregar acá y crear la action en facturas.py. Tiene que coincidir
# con `ALL_TOOLS` de `_yoko_agents/tools/__init__.py`.
_TOOL_TO_ACTION: dict[str, str] = {
    "yoko_procesar_archivos":         "procesar-chat",
    "yoko_generar_registro_contable": "registro-contable-chat",
    # "yoko_recuperar_proceso":       "recuperar-chat",  # uso futuro
}

# Vault es por empresa. Hoy hardcodeamos cmejia; cuando se sumen más empresas,
# se mueve a Airtable o a un dict externo.
_VAULT_ENV_BY_EMPRESA: dict[str, str] = {
    "cmejia": "YOKO_VAULT_ID_CMEJIA",
}

_TOOL_HTTP_TIMEOUT = 120  # 2 min: procesar 50 PDFs puede tardar
_MAX_TURNS = 8            # safety: corta loops de requires_action ↔ tool_result


def handle_post(req) -> None:
    """Punto de entrada. Mismo contrato que `handler.handle_post`."""
    try:
        # 1) Body
        length = int(req.headers.get("Content-Length", 0))
        try:
            raw = req.rfile.read(length)
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

        # 2) Env vars críticas
        missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
        if missing:
            print(f"[chat/managed] Faltan env vars: {missing}", file=sys.stderr)
            return req._json(500, {"error": "Configuración del servidor incompleta."})

        # 3) Auth
        try:
            auth_payload = auth.require_auth(req.headers)
        except AuthError as e:
            return req._json(e.status, {"error": str(e)})
        empresa_id = auth_payload["empresa_id"]
        modulos = auth_payload.get("modulos") or []

        # 4) Usuario
        try:
            user = session.extract_user(body)
        except ValueError as e:
            print(f"[chat/managed] User inválido: {e}", file=sys.stderr)
            return req._json(400, {"error": "Datos del usuario inválidos."})

        # 5) Vault por empresa (opcional: si no hay, se crea session sin vault)
        vault_env_name = _VAULT_ENV_BY_EMPRESA.get(empresa_id)
        vault_id = os.environ.get(vault_env_name) if vault_env_name else None

        # 6) Último mensaje del usuario + adjuntos opcionales (base64).
        messages = body.get("messages") or []
        last_user_content = _last_user_content(messages)
        attachments = body.get("attachments") or None
        if attachments and not isinstance(attachments, list):
            return req._json(400, {"error": "attachments debe ser una lista."})

        if not last_user_content and not attachments:
            return req._json(400, {"error": "No hay mensaje del usuario."})

        # 7) Get-or-create session (cacheada en KV)
        agent_id = os.environ["YOKO_AGENT_ID"]
        user_id = (user.get("dni") or "anonymous").strip()
        try:
            session_id = yoko_session_store.get_session_id(empresa_id, user_id)
        except Exception as e:
            print(f"[chat/managed] KV get_session_id: {e}", file=sys.stderr)
            session_id = None

        # 7a) Si la session viene del cache, validar que siga viva en
        # Anthropic SOLO si podemos confirmar el estado. Casos a manejar:
        #   - GET 404 → session no existe → muerta, recrear.
        #   - status `terminated` o archived_at != null → muerta, recrear.
        #   - GET con 5xx / red caída → NO sabemos. Asumir viva: si está
        #     muerta de verdad, los POSTs de events fallarán abajo y el
        #     usuario tiene que reintentar; pero si el GET falló por un
        #     hipo transitorio, no perdemos el contexto de la conversación.
        if session_id is not None:
            session_dead = False
            try:
                info = mac.get_session(session_id)
                # mac.get_session devuelve None solo si HTTP 404
                # (session no existe).
                if not _is_session_alive(info):
                    session_dead = True
                    print(
                        f"[chat/managed] session cacheada {session_id} no "
                        f"usable (status={(info or {}).get('status')!r}, "
                        f"archived_at={(info or {}).get('archived_at')!r}); "
                        "descartando y creando una nueva.",
                        file=sys.stderr,
                    )
            except mac.ManagedAgentsError as e:
                # Error no-404: probablemente transitorio. Loggear y
                # seguir con la session cacheada.
                print(
                    f"[chat/managed] get_session HTTP {e.status} transitorio; "
                    f"asumiendo session {session_id} viva.",
                    file=sys.stderr,
                )

            if session_dead:
                try:
                    yoko_session_store.force_new_session(empresa_id, user_id)
                except Exception as e:
                    print(
                        f"[chat/managed] force_new_session falló: {e}",
                        file=sys.stderr,
                    )
                try:
                    yoko_cart_store.clear_cart(session_id)
                except Exception:
                    pass
                session_id = None

        is_new_session = session_id is None
        if is_new_session:
            try:
                contexto = yoko_context_builder.construir_contexto_empresa(
                    empresa_id, user, modulos=modulos,
                )
            except AirtableError as e:
                print(f"[chat/managed] Airtable: {e}", file=sys.stderr)
                return req._json(502, {
                    "error": "Error al consultar la base de datos.",
                    "where": "construir_contexto_empresa",
                })

            try:
                title = f"yoko/{empresa_id}/{user_id}"
                session_id = mac.create_session(
                    agent_id=agent_id,
                    vault_id=vault_id,
                    title=title,
                )
            except mac.ManagedAgentsError as e:
                print(f"[chat/managed] No pude crear session: {e}", file=sys.stderr)
                return req._json(502, {
                    "error": "Error iniciando la conversación.",
                    "where": "mac.create_session",
                    "anthropic_status": e.status,
                })

            try:
                yoko_session_store.store_session(
                    empresa_id, user_id, session_id,
                    extra_metadata={"agent_id": agent_id},
                )
            except Exception as e:
                # No bloqueante: si falla el cache, igual seguimos esta request.
                print(f"[chat/managed] KV store_session: {e}", file=sys.stderr)

            # En el primer turno, prependemos el contexto de empresa al
            # mensaje del usuario para que el agent lo lea sin gastar una
            # corrida solo para procesar el contexto.
            last_user_content = (
                f"{contexto}\n\n{last_user_content}" if last_user_content else contexto
            )

            print(
                f"[chat/managed] session NUEVA {session_id} para "
                f"{empresa_id}/{user_id}",
                file=sys.stderr,
            )
        else:
            print(
                f"[chat/managed] session reusada {session_id} para "
                f"{empresa_id}/{user_id}",
                file=sys.stderr,
            )

        # 7b) Persistir adjuntos al carrito KV (y armar hint para el agent
        # con el TOTAL acumulado del carrito, no solo los de esta request).
        if attachments:
            try:
                yoko_cart_store.add_files(session_id, attachments)
            except Exception as e:
                print(
                    f"[chat/managed] cart_store.add_files falló: {e}",
                    file=sys.stderr,
                )
                return req._json(502, {
                    "error": "Error guardando los adjuntos.",
                    "where": "yoko_cart_store.add_files",
                    "detail": f"{type(e).__name__}: {e}",
                })

        try:
            total_carrito = yoko_cart_store.cart_size(session_id)
        except Exception as e:
            print(f"[chat/managed] cart_size falló: {e}", file=sys.stderr)
            total_carrito = 0

        if attachments:
            nombres = ", ".join(
                (a.get("filename") or "archivo") for a in attachments[:5]
            )
            if len(attachments) > 5:
                nombres += f", ... y {len(attachments) - 5} más"
            msg_adjuntos = (
                f"[SISTEMA] El usuario adjuntó {len(attachments)} archivo(s) "
                f"en este turno: {nombres}. Total acumulado en el carrito: "
                f"{total_carrito}. IMPORTANTE: vos NO ves el contenido binario "
                f"de estos archivos directamente, NI están en ningún path del "
                f"filesystem. NO uses bash ni intentes leer rutas. Cuando el "
                f"usuario pida procesarlos, llamá la herramienta "
                f"`yoko_procesar_archivos` con `tipo` y `mes` — los archivos "
                f"se inyectan automáticamente en la llamada por el "
                f"orquestador. Mientras tanto, seguí el flujo del skill "
                f"yoko-facturas (confirmar recepción tipo \"Listo (N). ¿Más "
                f"comprobantes?\")."
            )
            last_user_content = (
                f"{last_user_content}\n\n{msg_adjuntos}"
                if last_user_content
                else msg_adjuntos
            )
        elif total_carrito > 0:
            # No hay attachments en esta request pero el carrito tiene archivos
            # de turnos previos. Recordarle al agent que están disponibles.
            msg_carrito = (
                f"[SISTEMA] Hay {total_carrito} archivo(s) acumulados en el "
                f"carrito desde turnos anteriores. Si el usuario pide procesar, "
                f"llamá `yoko_procesar_archivos` y los archivos se inyectan "
                f"automáticamente."
            )
            last_user_content = (
                f"{last_user_content}\n\n{msg_carrito}"
                if last_user_content
                else msg_carrito
            )

        # 8) Async pattern: encolar task y kickear worker. NO corremos
        # _run_turn acá — eso vive en /api/chat?action=worker, que tiene
        # su propio presupuesto de Vercel y puede tomar hasta 300s sin
        # bloquear esta function.
        auth_header = req.headers.get("Authorization") or ""
        task_id = yoko_task_store.new_task_id()
        try:
            ok = yoko_task_store.create(
                task_id,
                session_id=session_id,
                user_id=user_id,
                empresa_id=empresa_id,
                user_content=last_user_content,
                auth_header=auth_header,
            )
        except Exception as e:
            print(
                f"[chat/managed] task_store.create excepción: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return req._json(502, {
                "error": "No se pudo encolar la conversación.",
                "where": "yoko_task_store.create",
                "detail": f"{type(e).__name__}: {e}",
            })

        if not ok:
            return req._json(502, {
                "error": "No se pudo encolar la conversación.",
                "where": "yoko_task_store.create returned False",
            })

        try:
            _kick_worker(task_id)
        except Exception as e:
            # Si fire-and-forget falla, el task queda pending y el frontend
            # va a hacer polling — pero el worker nunca arrancó. Mejor
            # avisar y dejar que el usuario reintente.
            import traceback
            print(
                f"[chat/managed] _kick_worker falló: "
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                file=sys.stderr,
            )
            yoko_task_store.mark_error(
                task_id, f"No se pudo arrancar el worker: {e}"
            )
            return req._json(502, {
                "error": "Error iniciando el procesamiento.",
                "where": "_kick_worker",
                "detail": f"{type(e).__name__}: {e}",
            })

        print(
            f"[chat/managed] task {task_id} encolado y worker disparado",
            file=sys.stderr,
        )
        # Frontend va a hacer polling a GET /api/chat?action=status&task_id=...
        return req._json(202, {"task_id": task_id, "status": "pending"})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(
            f"[chat/managed] Error inesperado: {type(e).__name__}: {e}\n{tb}",
            file=sys.stderr,
        )
        return req._json(500, {
            "error": "Error interno del servidor.",
            "where": "handle_post outer except",
            "detail": f"{type(e).__name__}: {e}",
        })


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _kick_worker(task_id: str) -> None:
    """
    Dispara una request HTTP a `POST /api/chat?action=worker&task_id=<id>`
    sin esperar la respuesta (fire-and-forget). Vercel arranca esa segunda
    function en paralelo con su propio presupuesto de duration (~300s con
    fluid compute), separado del POST inicial del usuario.

    Auth interna: header `X-Internal-Token` (env var YOKO_INTERNAL_TOKEN).

    El timeout de 2s solo cubre el TCP handshake + envío del request.
    El worker mismo corre su lógica después de que esto retorne.

    NO propagar excepciones de la red al caller: ya que es fire-and-forget,
    cualquier error después de enviar el request es informativo, no fatal.
    Específicamente, urlopen con timeout puede levantar `socket.timeout`
    (subclase de OSError, NO de URLError), por eso atrapamos broad.
    El handle_post NO debe devolver 502 solo porque el kick "tardó" — la
    request al worker ya viajó y Vercel arrancó la function.
    """
    base = (os.environ.get("YOKO_API_BASE") or "https://yokochat.vercel.app").rstrip("/")
    token = os.environ.get("YOKO_INTERNAL_TOKEN")
    if not token:
        raise RuntimeError("YOKO_INTERNAL_TOKEN no configurado")

    url = f"{base}/api/chat?action=worker&task_id={urllib.parse.quote(task_id)}"
    request = urllib.request.Request(url, data=b"", method="POST")
    request.add_header("X-Internal-Token", token)
    request.add_header("Content-Type", "application/json")
    request.add_header("Content-Length", "0")

    try:
        urllib.request.urlopen(request, timeout=2)
    except Exception as e:
        # Atrapamos amplio: socket.timeout, OSError, URLError, HTTPError…
        # son todos "esperables" cuando Vercel cold-startea el worker y la
        # respuesta tarda más que el timeout de 2s. Lo que importa es que
        # la request salió: el worker function arranca igual.
        print(
            f"[chat/managed] _kick_worker fire-and-forget non-fatal: "
            f"{type(e).__name__}: {e}",
            file=sys.stderr,
        )


def _is_session_alive(info: dict | None) -> bool:
    """
    Decide si una session devuelta por mac.get_session sigue siendo usable.

    `info` es None si el GET devolvió 404 (session inexistente), o un dict
    con `status` y opcionalmente `archived_at`. Estados terminales:
      - status `terminated`: error irrecuperable.
      - `archived_at` no null: archivada (manualmente desde el Console o
        por API). Acepta lecturas pero rechaza POST de events.

    Estados vivos: `idle`, `running`, `rescheduling`.
    """
    if not info or not isinstance(info, dict):
        return False
    if info.get("archived_at"):
        return False
    status = (info.get("status") or "").lower()
    if status in ("terminated",):
        return False
    return True


def _last_user_content(messages: list) -> str:
    """Devuelve el content del último mensaje con role='user' o ''."""
    for m in reversed(messages or []):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    chunks.append(b.get("text", ""))
            return "".join(chunks)
    return ""


# NOTA: la antigua función `_run_turn` (versión síncrona) se movió al
# worker async como `_run_turn_streaming` en `handler_worker.py`. Acá
# solo dejamos los helpers que el worker importa: `_exec_local_tool` y
# `_TOOL_TO_ACTION`.


def _exec_local_tool(action: str, input_args: dict, auth_header: str) -> dict:
    """
    Ejecuta un custom tool del agent haciendo HTTP loopback a la propia API
    Yoko en `/api/facturas?action=<action>` con el JWT del usuario reenviado.

    Devuelve dict que se serializa como `user.custom_tool_result`. Si la
    respuesta del endpoint es binaria (xlsx en download-chat), la codifica en
    base64 y la incluye en el dict.
    """
    base = (os.environ.get("YOKO_API_BASE") or "https://yokochat.vercel.app").rstrip("/")
    url = f"{base}/api/facturas?action={urllib.parse.quote(action)}"

    body = json.dumps(input_args).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    if auth_header:
        request.add_header("Authorization", auth_header)

    try:
        with urllib.request.urlopen(request, timeout=_TOOL_HTTP_TIMEOUT) as res:
            content_type = res.headers.get("Content-Type", "") or ""
            data = res.read()
            if "application/json" in content_type:
                return json.loads(data) if data else {}
            if "spreadsheet" in content_type or action == "download-chat":
                disposition = res.headers.get("Content-Disposition", "") or ""
                return {
                    "ok":           True,
                    "filename":     _filename_from_disposition(disposition),
                    "content_b64":  base64.b64encode(data).decode("ascii"),
                    "content_type": content_type,
                }
            return {"ok": True, "raw_size": len(data), "content_type": content_type}
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        print(
            f"[chat/managed] tool {action} HTTP {e.code}: {err_body[:300]}",
            file=sys.stderr,
        )
        return {"error": f"HTTP {e.code} en {action}", "detail": err_body[:300]}
    except urllib.error.URLError as e:
        print(f"[chat/managed] tool {action} URL error: {e}", file=sys.stderr)
        return {"error": f"Error de red al ejecutar {action}"}
    except Exception as e:
        print(
            f"[chat/managed] tool {action} excepción {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return {"error": f"Error inesperado en {action}: {type(e).__name__}"}


def _filename_from_disposition(header: str) -> str:
    if "filename=" not in header:
        return "archivo"
    return header.split("filename=", 1)[1].strip(' ;"\'')
