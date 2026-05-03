"""
api/sales_chat.py — el "cerebro" del agente de ventas.

Lo consume el servicio bot-baileys (Node.js) cuando un cliente final
escribe vía WhatsApp/IG/FB. Recibe el historial de la conversación y
devuelve la respuesta que el bot debe enviar.

Body esperado (POST):
{
  "empresa_id":  "cmejia",
  "phone":       "+51 987 654 321",        // del cliente final
  "nombre":      "Juan Pérez",              // pushname de WhatsApp
  "history":     [{"role": "user|assistant", "content": "..."}],
  "razon_social": "C.MEJIA CONTRATISTAS GENERALES SAC",  // opcional
  "ruc":          "20392546899"                            // opcional
}

Respuesta:
{
  "reply":       "Hola Juan, claro, tenemos taladros DeWalt desde S/ 1,690. ¿Te interesa alguno?"
}

Diferencias clave con /api/chat:
  • NO usa tool_registry (Yoko's tools). Usa tools.ventas.VENTAS_TOOLS_OPENAI.
  • NO usa prompt_builder con caja chica. Usa modo "ventas" → catálogo embebido.
  • NO requiere user con DNI. Usa sender (phone + nombre del cliente final).
  • NO devuelve "action" (el bot no navega; solo responde texto).
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Permitir importar desde api/_lib/
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _lib import airtable_client                                  # noqa: E402
from _lib import openai_client                                    # noqa: E402
from _lib import prompt_builder                                   # noqa: E402
from _lib.airtable_client import AirtableError                    # noqa: E402
from _lib.tools import ventas as ventas_tools                     # noqa: E402

try:
    from openai import APIError as OpenAIAPIError                 # noqa: E402
except ImportError:
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            try:
                raw = self.rfile.read(length)
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return self._json(400, {"error": "JSON inválido en el cuerpo."})

            # 1) Validar env vars
            missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
            if missing:
                print(f"[sales_chat] Faltan env vars: {missing}", file=sys.stderr)
                return self._json(500, {"error": "Configuración del servidor incompleta."})

            # 2) Validar inputs
            empresa_id = (body.get("empresa_id") or "").strip()
            history = body.get("history") or []
            if not empresa_id:
                return self._json(400, {"error": "Falta 'empresa_id'."})
            if not isinstance(history, list) or not history:
                return self._json(400, {"error": "Falta 'history' o está vacío."})

            sender = {
                "phone":  (body.get("phone") or "").strip(),
                "nombre": (body.get("nombre") or "").strip(),
            }

            # 3) Cargar productos del tenant (catálogo para el prompt)
            try:
                productos_result = ventas_tools.consultar_productos(
                    {"solo_disponibles": False},
                    {"empresa_id": empresa_id},
                )
            except AirtableError as e:
                print(f"[sales_chat] AirtableError productos: {e}", file=sys.stderr)
                return self._json(502, {"error": "No se pudo cargar el catálogo."})

            productos = productos_result.get("productos", [])
            if "error" in productos_result:
                print(
                    f"[sales_chat] Productos error: {productos_result.get('detail')}",
                    file=sys.stderr,
                )

            # 4) Armar config mínimo (sin cargar todo el config_loader, no hace falta
            # para este flujo). El prompt builder solo necesita razón social y RUC.
            config = {
                "empresa": {
                    "id":           empresa_id,
                    "razon_social": (body.get("razon_social") or "").strip() or None,
                    "ruc":          (body.get("ruc") or "").strip() or None,
                }
            }

            # 5) Construir system prompt en modo ventas
            try:
                system = prompt_builder.build_system_prompt(
                    config,
                    user=None,
                    extra_context={
                        "modo":      "ventas",
                        "productos": productos,
                        "sender":    sender,
                    },
                )
            except Exception as e:
                print(f"[sales_chat] Error armando prompt: {type(e).__name__}: {e}", file=sys.stderr)
                return self._json(500, {"error": "Error interno armando prompt."})

            # 6) Loop de chat con OpenAI usando tools de ventas
            try:
                result = openai_client.run_chat(
                    system_prompt=system,
                    messages=history,
                    tools=ventas_tools.VENTAS_TOOLS_OPENAI,
                    context={"empresa_id": empresa_id, "sender": sender},
                    executor=ventas_tools.execute_ventas_tool,
                    max_iterations=4,  # ventas no necesita más rounds que esto
                )
            except OpenAIAPIError as e:
                print(f"[sales_chat] OpenAI API error: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error del servicio IA."})
            except AirtableError as e:
                print(f"[sales_chat] AirtableError run_chat: {e}", file=sys.stderr)
                return self._json(502, {"error": "Error consultando catálogo."})

            reply = (result.get("text") or "").strip()
            if not reply:
                reply = "Disculpa, no entendí bien tu mensaje. ¿Podrías repetirlo?"

            return self._json(200, {"reply": reply})

        except Exception as e:
            print(f"[sales_chat] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
            return self._json(500, {"error": "Error interno del servidor."})

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
