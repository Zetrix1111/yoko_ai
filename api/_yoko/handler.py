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

from _lib import config_loader, openai_client, session
from _lib.airtable_client import AirtableError
from _yoko._lib import prompt as yoko_prompt
from _yoko._lib import tool_registry

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    # Si el SDK no carga, usamos Exception como sentinel para no romper el load.
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "TENANT_ID")


def handle_post(req) -> None:
    """Maneja un POST /api/chat. `req` es el BaseHTTPRequestHandler."""
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

        # 3) Extraer y validar al usuario
        try:
            user = session.extract_user(body)
        except ValueError as e:
            print(f"[chat] User inválido: {e}", file=sys.stderr)
            return req._json(400, {"error": "Datos del usuario inválidos."})

        # 4) Cargar configuración
        try:
            config = config_loader.load_full_config()
        except AirtableError as e:
            print(f"[chat] AirtableError al cargar config: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error al consultar la base de datos."})

        # 5) Armar system prompt + tools list
        try:
            system = yoko_prompt.build_system_prompt(config, user)
            tools = yoko_prompt.build_tools_list(config)
        except Exception as e:
            print(f"[chat] Error armando prompt/tools: {type(e).__name__}: {e}", file=sys.stderr)
            return req._json(500, {"error": "Error interno del servidor."})

        # 6) Loop de chat con OpenAI usando el executor de Yoko (no el de ventas)
        try:
            result = openai_client.run_chat(
                system_prompt=system,
                messages=body.get("messages", []) or [],
                tools=tools,
                context={"user": user, "config": config},
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
