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
from _lib import yoko_context_builder, yoko_session_store
from _lib.airtable_client import AirtableError
from _lib.auth import AuthError


_REQUIRED_ENV = (
    "ANTHROPIC_API_KEY",
    "YOKO_AGENT_ID",
    "KV_REST_API_URL",
    "KV_REST_API_TOKEN",
)

# Mapeo nombre del custom tool → action en /api/facturas. Si un tool nuevo
# aparece, agregar acá y crear la action en facturas.py.
_TOOL_TO_ACTION: dict[str, str] = {
    "yoko_procesar_archivos": "procesar-chat",
    "yoko_generar_excel":     "download-chat",
    "yoko_recuperar_proceso": "recuperar-chat",
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

        if attachments:
            msg_adjuntos = f"[El usuario adjuntó {len(attachments)} archivo(s) para procesar]"
            last_user_content = (
                f"{last_user_content}\n\n{msg_adjuntos}" if last_user_content else msg_adjuntos
            )

        if not last_user_content:
            return req._json(400, {"error": "No hay mensaje del usuario."})

        # 7) Get-or-create session (cacheada en KV)
        agent_id = os.environ["YOKO_AGENT_ID"]
        user_id = (user.get("dni") or "anonymous").strip()
        try:
            session_id = yoko_session_store.get_session_id(empresa_id, user_id)
        except Exception as e:
            print(f"[chat/managed] KV get_session_id: {e}", file=sys.stderr)
            session_id = None

        is_new_session = session_id is None
        if is_new_session:
            try:
                contexto = yoko_context_builder.construir_contexto_empresa(
                    empresa_id, user, modulos=modulos,
                )
            except AirtableError as e:
                print(f"[chat/managed] Airtable: {e}", file=sys.stderr)
                return req._json(502, {"error": "Error al consultar la base de datos."})

            try:
                title = f"yoko/{empresa_id}/{user_id}"
                session_id = mac.create_session(
                    agent_id=agent_id,
                    vault_id=vault_id,
                    title=title,
                )
            except mac.ManagedAgentsError as e:
                print(f"[chat/managed] No pude crear session: {e}", file=sys.stderr)
                return req._json(502, {"error": "Error iniciando la conversación."})

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
            last_user_content = f"{contexto}\n\n{last_user_content}"

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

        # 8) Conversación: stream + posibles tool_uses.
        auth_header = req.headers.get("Authorization") or ""
        try:
            text = _run_turn(
                session_id=session_id,
                user_content=last_user_content,
                auth_header=auth_header,
                attachments=attachments,
            )
        except mac.ManagedAgentsError as e:
            print(f"[chat/managed] Error en agent loop: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error del servicio IA."})

        return req._json(200, {"text": text, "action": None})

    except Exception as e:
        print(
            f"[chat/managed] Error inesperado: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return req._json(500, {"error": "Error interno del servidor."})


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

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


def _run_turn(
    session_id: str,
    user_content: str,
    auth_header: str,
    attachments: list[dict] | None = None,
) -> str:
    """
    Ejecuta un turno completo del agent:
      1. Abre stream SSE de eventos.
      2. POST user.message.
      3. Lee eventos hasta `session.status_idle` con stop_reason `end_turn`,
         resolviendo cualquier `requires_action` con custom tools en el medio.

    Devuelve el texto final acumulado del assistant.
    """
    text_parts: list[str] = []
    pending_tools: dict[str, dict] = {}  # event_id → {name, input}

    stream = mac.stream_session_events(session_id)
    print(f"[chat/managed] stream abierto session={session_id}", file=sys.stderr)

    # Posteamos el mensaje del usuario DESPUÉS de abrir el stream para no
    # perder eventos. urlopen() ya devolvió el response (headers leídos);
    # los eventos del POST llegarán por el socket abierto.
    mac.send_user_message(session_id, user_content)
    print(
        f"[chat/managed] user.message posteado ({len(user_content)} chars)",
        file=sys.stderr,
    )

    events_seen = 0
    turns = 0
    for evt in stream:
        events_seen += 1
        etype = evt.get("type") or ""
        if events_seen <= 3 or etype.startswith("session.") or etype == "session.error":
            print(f"[chat/managed] evt#{events_seen} type={etype}", file=sys.stderr)

        if etype == "agent.message":
            for block in evt.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text") or ""
                    if t:
                        text_parts.append(t)

        elif etype == "agent.custom_tool_use":
            evt_id = evt.get("id") or ""
            name = evt.get("name") or ""
            tool_input = evt.get("input") or {}
            if evt_id and name:
                pending_tools[evt_id] = {"name": name, "input": tool_input}

        elif etype == "session.error":
            err = evt.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            print(f"[chat/managed] session.error: {msg}", file=sys.stderr)
            break

        elif etype == "session.status_idle":
            stop = evt.get("stop_reason") or {}
            stop_type = stop.get("type") if isinstance(stop, dict) else None

            if stop_type == "end_turn":
                break

            if stop_type == "requires_action":
                blocking_ids: list[str] = []
                if isinstance(stop, dict):
                    blocking_ids = list(stop.get("event_ids") or [])

                if not blocking_ids:
                    # Idle sin acciones bloqueantes: corte por seguridad.
                    break

                turns += 1
                if turns > _MAX_TURNS:
                    print(
                        f"[chat/managed] cap de turnos alcanzado ({_MAX_TURNS}); "
                        "interrumpiendo loop de tools",
                        file=sys.stderr,
                    )
                    break

                for eid in blocking_ids:
                    pending = pending_tools.get(eid)
                    if not pending:
                        # No tenemos el tool_use cacheado: respondemos un error
                        # para destrabar la session.
                        mac.submit_custom_tool_result(
                            session_id, eid,
                            {"error": "tool_use no encontrado en el stream"},
                        )
                        continue

                    tool_name = pending["name"]
                    tool_input = dict(pending["input"] or {})

                    if tool_name == "yoko_procesar_archivos" and attachments:
                        tool_input["files"] = attachments

                    action = _TOOL_TO_ACTION.get(tool_name)
                    if not action:
                        result: dict = {"error": f"Tool '{tool_name}' no soportado."}
                        print(
                            f"[chat/managed] tool desconocido: {tool_name}",
                            file=sys.stderr,
                        )
                    else:
                        result = _exec_local_tool(action, tool_input, auth_header)

                    mac.submit_custom_tool_result(session_id, eid, result)
                # Seguir leyendo el stream: la session vuelve a `running`.
                continue

            # Otros stop_reasons (tool_confirmation, etc.): cortamos para
            # evitar quedar colgados. El agent devolverá lo que tenga hasta
            # el momento.
            print(
                f"[chat/managed] stop_reason inesperado: {stop_type}",
                file=sys.stderr,
            )
            break

        # Otros eventos (agent.thinking, span.*, agent.tool_use de toolset
        # built-in, etc.) los ignoramos para el texto al usuario.

    return "".join(text_parts).strip()


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
