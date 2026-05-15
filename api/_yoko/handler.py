"""
yoko/handler.py — lógica del POST /api/chat (asistente Yoko).

Esta función la invoca el dispatcher delgado api/chat.py. Recibe el
BaseHTTPRequestHandler con el body crudo y delega:
  • lectura/validación de body
  • carga de config (Airtable + JSON)
  • armado de system prompt y tools (yoko/_lib/prompt.py)
  • loop OpenAI con tool calling (executor del registry de Yoko)
  • respuesta final {text, action}

Errores siempre en español, sin filtrar detalle interno:
  400 → JSON inválido o datos del usuario inválidos
  500 → configuración del servidor incompleta o error interno
  502 → falla del servicio IA o de la base de datos (Airtable)
"""

import json
import os
import sys

from _lib import auth, config_loader, openai_client, session, yoko_cart_store
from _lib.airtable_client import AirtableError
from _lib.auth import AuthError
from _yoko._lib import prompt as yoko_prompt
from _yoko._lib import tool_registry

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    # Si el SDK no carga, usamos Exception como sentinel para no romper el load.
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")


def _resolve_backend(req) -> str:
    """
    Decide qué backend usar para esta request.

    Precedencia:
      1. Header HTTP `X-Yoko-Backend` (si trae "managed_agents" u "openai") —
         lo mete el frontend cuando el usuario cambia el switch de UI, así
         alterna por request sin tocar Vercel.
      2. Env var `YOKO_BACKEND` (server-side default), valores idem.
      3. Fallback final: "openai" (back-compat).

    Cualquier valor desconocido (typo, header malformado) cae al siguiente
    nivel — no se "fail-loud" porque rompería el chat en producción si el
    cliente manda algo raro.
    """
    header = (req.headers.get("X-Yoko-Backend") or "").strip().lower()
    if header in ("managed_agents", "openai"):
        return header
    return (os.environ.get("YOKO_BACKEND") or "openai").strip().lower()


def handle_post(req) -> None:
    """Maneja un POST /api/chat. `req` es el BaseHTTPRequestHandler.

    El backend se resuelve por request via `_resolve_backend(req)`:
      - "managed_agents"  → delega en _yoko/handler_managed.py
                            (Anthropic Managed Agents).
      - "openai" (default) → flujo legacy de este archivo
                            (tool-calling con OpenAI).
    """
    if _resolve_backend(req) == "managed_agents":
        from _yoko import handler_managed
        return handler_managed.handle_post(req)

    try:
        # 1) Leer y parsear el body
        length = int(req.headers.get("Content-Length", 0))
        try:
            raw = req.rfile.read(length)
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return req._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

        # 2) Verificar variables de entorno requeridas
        missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
        if missing:
            print(f"[chat] Faltan env vars: {missing}", file=sys.stderr)
            return req._json(500, {"error": "Configuración del servidor incompleta."})

        # 3) Validar JWT — empresa_id viene del token, NO del body.
        try:
            auth_payload = auth.require_auth(req.headers)
        except AuthError as e:
            return req._json(e.status, {"error": str(e)})
        empresa_id = auth_payload["empresa_id"]

        # 4) Extraer y validar al usuario
        try:
            user = session.extract_user(body)
        except ValueError as e:
            print(f"[chat] User inválido: {e}", file=sys.stderr)
            return req._json(400, {"error": "Datos del usuario inválidos."})

        # 5) Cargar configuración de la empresa del JWT.
        # `config_loader` ya no lee `src/tenants/<id>/config.json` (Fase 4):
        # solo lee Airtable. `empresa.modules` viene vacío del loader; lo
        # inyectamos acá desde el JWT, que es la fuente autoritativa de
        # qué módulos tiene habilitados la empresa.
        try:
            config = config_loader.load_full_config(empresa_id)
        except AirtableError as e:
            print(f"[chat] AirtableError al cargar config: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error al consultar la base de datos."})

        modulos = auth_payload.get("modulos") or []
        if isinstance(modulos, list):
            config["empresa"]["modules"] = modulos

        # 6) Adjuntos para módulo facturas-inteligentes — persistir al
        # carrito server-side ANTES de armar el prompt, así el bloque
        # `[SISTEMA]` que inyectamos al último user message refleja el
        # total acumulado correcto.
        #
        # OpenAI es stateless (no tiene `session_id` nativo como
        # Anthropic Managed Agents), pero igual necesitamos una clave
        # para el carrito KV cross-turn. La derivamos de (empresa, dni)
        # del usuario JWT. TTL 4h sliding como en Managed.
        attachments = body.get("attachments") or None
        if attachments is not None and not isinstance(attachments, list):
            return req._json(400, {"error": "attachments debe ser una lista."})

        user_id = (user.get("dni") or "anonymous").strip()
        session_id = f"yoko-legacy:{empresa_id}:{user_id}"

        if attachments:
            try:
                yoko_cart_store.add_files(session_id, attachments)
            except Exception as e:
                print(
                    f"[chat] yoko_cart_store.add_files falló: "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                return req._json(502, {
                    "error": "Error guardando los adjuntos.",
                })

        # Inyectar hint para el LLM con el total del carrito (mismo patrón
        # que handler_managed.py:258-281). El bloque [SISTEMA] lo lee la
        # capa "MÓDULO FACTURAS INTELIGENTES" del system prompt.
        if attachments:
            try:
                total_carrito = yoko_cart_store.cart_size(session_id)
            except Exception:
                total_carrito = len(attachments)
            nombres = ", ".join(
                (a.get("filename") or "archivo") for a in attachments[:5]
                if isinstance(a, dict)
            )
            if len(attachments) > 5:
                nombres += f", ... y {len(attachments) - 5} más"
            msg_adjuntos = (
                f"[SISTEMA] El usuario adjuntó {len(attachments)} archivo(s) "
                f"en este turno: {nombres}. Total acumulado en carrito: "
                f"{total_carrito}. NO ves el contenido binario directamente, "
                f"NI están en ningún path del filesystem. Cuando el usuario "
                f"confirme tipo+mes, invocá `procesar_facturas` — el "
                f"orquestador inyecta los archivos automáticamente."
            )
            msgs = list(body.get("messages") or [])
            if msgs and isinstance(msgs[-1], dict) and msgs[-1].get("role") == "user":
                msgs[-1] = dict(msgs[-1])
                msgs[-1]["content"] = (
                    str(msgs[-1].get("content") or "") + "\n\n" + msg_adjuntos
                )
            else:
                msgs.append({"role": "user", "content": msg_adjuntos})
            body["messages"] = msgs

        # 7) Armar system prompt + tools list
        try:
            system = yoko_prompt.build_system_prompt(config, user)
            tools = yoko_prompt.build_tools_list(config)
        except Exception as e:
            print(f"[chat] Error armando prompt/tools: {type(e).__name__}: {e}", file=sys.stderr)
            return req._json(500, {"error": "Error interno del servidor."})

        # 8) Loop de chat con OpenAI usando el executor de Yoko (no el de ventas).
        # `empresa_id` viaja en el context para que las tools que escriben en
        # Airtable (acción) lo usen como filtro/poblamiento, sin leer env vars.
        # `session_id_for_cart` + `auth_header` van para las tools de facturas
        # (`procesar_facturas`, `cancelar_carrito`) que necesitan el carrito
        # y el JWT del usuario para hacer HTTP loopback a /api/facturas?action=*.
        try:
            result = openai_client.run_chat(
                system_prompt=system,
                messages=body.get("messages", []) or [],
                tools=tools,
                context={
                    "user":                user,
                    "config":              config,
                    "empresa_id":          empresa_id,
                    "session_id_for_cart": session_id,
                    "auth_header":         req.headers.get("Authorization") or "",
                },
                executor=tool_registry.execute_tool,
            )
        except OpenAIAPIError as e:
            print(f"[chat] OpenAI API error: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error del servicio IA."})
        except AirtableError as e:
            print(f"[chat] AirtableError durante run_chat: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error al consultar la base de datos."})

        # 7) Respuesta final
        return req._json(200, {
            "text":   result.get("text", ""),
            "action": result.get("action"),
        })

    except Exception as e:
        print(f"[chat] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error interno del servidor."})
