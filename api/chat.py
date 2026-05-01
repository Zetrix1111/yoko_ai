"""
api/chat.py — handler conversacional con IA (function calling).

Reemplaza el proxy a Make. Ahora arma el system prompt en 5 capas
(identidad / capacidades / usuario / reglas / comportamiento), ejecuta
el loop de tool calling con OpenAI, y devuelve `{text, action}` al
frontend.

Body esperado:
    {
      "user":     {"dni": "...", "nombre": "...", "cargo": "..."},
      "messages": [{"role": "user"|"assistant", "content": "..."}, ...]
    }

Respuesta:
    {"text": "...", "action": {...} | null}

Errores (siempre en español, sin filtrar detalle interno):
    400 → JSON inválido o datos del usuario inválidos
    500 → configuración del servidor incompleta o error interno
    502 → falla del servicio IA o de la base de datos (Airtable)
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler


# ─────────────────────────────────────────────────────────────────────────
# Setup de imports: agregamos api/ al sys.path para poder hacer
# `from _lib import ...` tanto en local como en Vercel.
# ─────────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))   # /.../api
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import config_loader, openai_client, prompt_builder, session  # noqa: E402
from _lib.airtable_client import AirtableError                          # noqa: E402

try:
    from openai import APIError as OpenAIAPIError                       # noqa: E402
except ImportError:
    # Si por alguna razón el SDK no se carga, usamos Exception genérica
    # como sentinel para que el handler no se rompa al cargar.
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "TENANT_ID")


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            # 1) Leer y parsear el body
            length = int(self.headers.get("Content-Length", 0))
            try:
                raw = self.rfile.read(length)
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido en el cuerpo de la solicitud."})

            # 2) Verificar variables de entorno requeridas
            missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
            if missing:
                print(f"[chat] Faltan env vars: {missing}", file=sys.stderr)
                return self._json(500, {"error": "Configuración del servidor incompleta."})

            # 3) Extraer y validar al usuario
            try:
                user = session.extract_user(body)
            except ValueError as e:
                print(f"[chat] User inválido: {e}", file=sys.stderr)
                return self._json(400, {"error": "Datos del usuario inválidos."})

            # 4) Cargar configuración (estática + dinámica)
            try:
                config = config_loader.load_full_config()
            except AirtableError as e:
                print(f"[chat] AirtableError al cargar config: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error al consultar la base de datos."})

            # 5) Armar el system prompt y la lista de tools
            try:
                system = prompt_builder.build_system_prompt(config, user)
                tools = prompt_builder.build_tools_list(config)
            except Exception as e:
                print(f"[chat] Error armando prompt/tools: {type(e).__name__}: {e}", file=sys.stderr)
                return self._json(500, {"error": "Error interno del servidor."})

            # 6) Loop de chat con OpenAI (puede llamar tools varias veces)
            try:
                result = openai_client.run_chat(
                    system_prompt=system,
                    messages=body.get("messages", []) or [],
                    tools=tools,
                    context={"user": user, "config": config},
                )
            except OpenAIAPIError as e:
                print(f"[chat] OpenAI API error: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error del servicio IA."})
            except AirtableError as e:
                # Una tool puede haber tirado AirtableError adentro del loop;
                # tool_registry lo captura y lo devuelve como {"error":"interno"},
                # pero por si acaso lo manejamos aquí también.
                print(f"[chat] AirtableError durante run_chat: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error al consultar la base de datos."})

            # 7) Respuesta final
            return self._json(200, {
                "text":   result.get("text", ""),
                "action": result.get("action"),
            })

        except Exception as e:
            # Cualquier cosa que se nos haya escapado.
            print(f"[chat] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
