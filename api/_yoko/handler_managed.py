"""
api/_yoko/handler_managed.py — backend Managed Agents del POST /api/chat.

Activado cuando `YOKO_BACKEND=managed_agents`. Tiene la misma firma que el
handler.py legacy (`handle_post(req)`), así api/chat.py no se entera del
cambio de backend.

Flujo:
  1. Auth JWT (mismo que legacy).
  2. session.extract_user(body) (mismo que legacy).
  3. Resolver Vault y MemoryStore de la empresa (env vars por empresa).
  4. yoko_session_store.get_session_id(empresa_id, user_id):
       - Si existe → reusar.
       - Si no → mac.create_session(...) + mandar contexto + cachear.
  5. Mandar el ÚLTIMO mensaje del usuario (el frontend manda el array
     completo por compat; Managed Agents persiste su propio historial server-
     side, así que solo tomamos el último).
  6. Loop de tool calling: si la respuesta del agent incluye `tool_use`,
     ejecutar el tool localmente vía HTTP a /api/facturas?action=…-chat,
     y submit_tool_result. Repetir hasta `end_turn` o cap de iteraciones.
  7. Devolver `{"text": "...", "action": null}` al frontend (formato compat
     con el handler legacy).

NOTA: este handler es nuevo y no se ejecuta en producción hasta que el
owner ponga YOKO_BACKEND=managed_agents en Vercel. Mientras tanto, el flag
default es `openai` y el handler legacy maneja todo el tráfico.
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

# Mapeo tool name → action en /api/facturas. Si un tool nuevo aparece,
# agregar acá y crear la action correspondiente en facturas.py.
_TOOL_TO_ACTION: dict[str, str] = {
    "yoko_procesar_archivos": "procesar-chat",
    "yoko_generar_excel":     "download-chat",
    "yoko_recuperar_proceso": "recuperar-chat",
}

# Vault y MemoryStore son por empresa. Hoy hardcodeamos cmejia; cuando se
# sumen más empresas, se mueve a Airtable o a un dict externo.
_VAULT_ENV_BY_EMPRESA: dict[str, str] = {
    "cmejia": "YOKO_VAULT_ID_CMEJIA",
}
_MEMORY_ENV_BY_EMPRESA: dict[str, str] = {
    "cmejia": "YOKO_MEMORY_STORE_ID_CMEJIA",
}

_TOOL_HTTP_TIMEOUT = 120  # 2 min: procesar 50 PDFs puede tardar
_MAX_TOOL_ITERATIONS = 6  # safety: corta loops infinitos de tool_use


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

        # 5) Vault + MemoryStore por empresa
        vault_env_name = _VAULT_ENV_BY_EMPRESA.get(empresa_id)
        memory_env_name = _MEMORY_ENV_BY_EMPRESA.get(empresa_id)
        if not vault_env_name or not memory_env_name:
            print(
                f"[chat/managed] empresa {empresa_id} sin Vault asociado",
                file=sys.stderr,
            )
            return req._json(
                500,
                {"error": "Empresa no habilitada para el backend Managed Agents."},
            )
        vault_id = os.environ.get(vault_env_name)
        memory_store_id = os.environ.get(memory_env_name)
        if not vault_id or not memory_store_id:
            print(
                f"[chat/managed] Faltan {vault_env_name}/{memory_env_name}",
                file=sys.stderr,
            )
            return req._json(500, {"error": "Vault de la empresa no configurado."})

        # 6) Último mensaje del usuario + adjuntos opcionales (base64).
        messages = body.get("messages") or []
        last_user_content = _last_user_content(messages)
        attachments = body.get("attachments") or None
        if attachments and not isinstance(attachments, list):
            return req._json(400, {"error": "attachments debe ser una lista."})

        if attachments:
            msg_adjuntos = f"[El usuario adjuntó {len(attachments)} archivo(s) para procesar]"
            if last_user_content:
                last_user_content = f"{last_user_content}\n\n{msg_adjuntos}"
            else:
                last_user_content = msg_adjuntos

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

        if session_id is None:
            try:
                contexto = yoko_context_builder.construir_contexto_empresa(
                    empresa_id, user, modulos=modulos,
                )
            except AirtableError as e:
                print(f"[chat/managed] Airtable: {e}", file=sys.stderr)
                return req._json(502, {"error": "Error al consultar la base de datos."})

            try:
                session_id = mac.create_session(
                    agent_id=agent_id,
                    vault_id=vault_id,
                    memory_store_id=memory_store_id,
                    metadata={"empresa_id": empresa_id, "user_id": user_id},
                )
                # Inyectar contexto como primer evento de la session.
                mac.send_user_message(session_id, contexto)
            except mac.ManagedAgentsError as e:
                print(f"[chat/managed] No pude iniciar session: {e}", file=sys.stderr)
                return req._json(502, {"error": "Error iniciando la conversación."})

            try:
                yoko_session_store.store_session(
                    empresa_id, user_id, session_id,
                    extra_metadata={"agent_id": agent_id},
                )
            except Exception as e:
                # No bloqueante: si falla el cache, igual seguimos esta request.
                print(f"[chat/managed] KV store_session: {e}", file=sys.stderr)

            print(
                f"[chat/managed] session NUEVA {session_id} para "
                f"{empresa_id}/{user_id}",
                file=sys.stderr,
            )

        # 8) Loop de mensaje + tool calls
        auth_header = req.headers.get("Authorization") or ""
        try:
            text = _run_with_tool_loop(
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
        # Si el frontend manda content como array de blocks, concatenar el texto.
        if isinstance(content, list):
            chunks: list[str] = []
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    chunks.append(b.get("text", ""))
            return "".join(chunks)
    return ""


def _run_with_tool_loop(
    session_id: str,
    user_content: str,
    auth_header: str,
    attachments: list[dict] | None = None,
) -> str:
    """
    Manda `user_content` (+ adjuntos opcionales) a la session y procesa la
    respuesta. Si el agent pide tools, ejecuta cada uno y submit_tool_result
    hasta que la respuesta no tenga más tool_use o se llegue al cap.

    Devuelve el texto final acumulado del assistant.
    """
    accumulated: list[str] = []

    # Primer turno: mensaje del usuario.
    response = mac.send_user_message(session_id, user_content)

    for _ in range(_MAX_TOOL_ITERATIONS):
        text_blocks, tool_uses = _split_response(response)
        accumulated.extend(text_blocks)

        if not tool_uses:
            break

        # Ejecutar todos los tool_use de este turno.
        for tu in tool_uses:
            tool_name = tu.get("name") or ""
            tool_input = tu.get("input") or {}
            tool_use_id = tu.get("id") or tu.get("tool_use_id") or ""

            if tool_name == "yoko_procesar_archivos" and attachments:
                tool_input["files"] = attachments

            action = _TOOL_TO_ACTION.get(tool_name)
            if not action:
                print(
                    f"[chat/managed] tool desconocido del agent: {tool_name}",
                    file=sys.stderr,
                )
                tool_result: dict = {"error": f"Tool '{tool_name}' no soportado."}
            else:
                tool_result = _exec_local_tool(action, tool_input, auth_header)

            response = mac.submit_tool_result(session_id, tool_use_id, tool_result)

    return "".join(accumulated).strip()


def _split_response(response: dict) -> tuple[list[str], list[dict]]:
    """
    Separa los content blocks de la respuesta en (textos, tool_uses).
    Acepta tanto el formato de Messages API (`content: [...blocks]`) como
    una variante donde la respuesta venga "aplastada".
    """
    text_blocks: list[str] = []
    tool_uses: list[dict] = []

    blocks = response.get("content")
    if not isinstance(blocks, list):
        # Si la respuesta no tiene content[], buscar texto top-level.
        text = response.get("text") or response.get("output") or ""
        if isinstance(text, str) and text:
            text_blocks.append(text)
        return text_blocks, tool_uses

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text") or ""
            if t:
                text_blocks.append(t)
        elif btype == "tool_use":
            tool_uses.append(block)

    return text_blocks, tool_uses


def _exec_local_tool(action: str, input_args: dict, auth_header: str) -> dict:
    """
    Ejecuta un tool del agent haciendo HTTP loopback a la propia API Yoko
    en `/api/facturas?action=<action>` con el JWT del usuario reenviado.

    Devuelve dict para que el agent reciba como `tool_result`. Si la respuesta
    del endpoint es binaria (xlsx en download-chat), lo codifica en base64
    y lo manda como objeto.
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
