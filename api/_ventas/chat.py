"""
ventas/chat.py — handler del agente de ventas (resource=sales_chat).

POST /api/ventas?resource=sales_chat
   body: {empresa_id, phone, nombre, history: [{role, content}]}
   → carga catálogo del tenant, arma system prompt 8-capas, ejecuta loop
     OpenAI con las tools de ventas, devuelve {reply}.

Lo invoca el bot-baileys cuando un cliente final escribe a un WhatsApp
linkeado y la conversación está en modo AI. NO lo invoca la UI directa.
"""

import os
import sys

from _lib import config_loader, openai_client
from _lib.airtable_client import AirtableError
from _ventas._lib import prompt as ventas_prompt
from _ventas._lib import tools as ventas_tools

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")


def sales_chat_post(req) -> None:
    try:
        body = req._read_body()

        missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
        if missing:
            print(f"[ventas/sales_chat] Faltan env vars: {missing}", file=sys.stderr)
            return req._json(500, {"error": "Configuración del servidor incompleta."})

        empresa_id = (body.get("empresa_id") or "").strip()
        history = body.get("history") or []
        if not empresa_id:
            return req._json(400, {"error": "Falta 'empresa_id'."})
        if not isinstance(history, list) or not history:
            return req._json(400, {"error": "Falta 'history' o está vacío."})

        sender = {
            "phone":  (body.get("phone") or "").strip(),
            "nombre": (body.get("nombre") or "").strip(),
        }

        # Cargar productos del tenant (catálogo para el prompt)
        try:
            productos_result = ventas_tools.consultar_productos(
                {"solo_disponibles": False},
                {"empresa_id": empresa_id},
            )
        except AirtableError as e:
            print(f"[ventas/sales_chat] AirtableError productos: {e}", file=sys.stderr)
            return req._json(502, {"error": "No se pudo cargar el catálogo."})

        productos = productos_result.get("productos", [])

        # Cargar config de la empresa que vino en el body. Este endpoint NO
        # valida JWT (es server-to-server desde el bot de WhatsApp; el bot
        # lee `empresa_id` de su propio .env por sesión Baileys). Si Airtable
        # falla, seguimos con un dict mínimo: el agente responde igual,
        # solo sin los bloques opcionales. NO devolvemos 502.
        try:
            full_config = config_loader.load_full_config(empresa_id)
        except AirtableError as e:
            print(f"[ventas/sales_chat] Config dinámica no disponible: {e}", file=sys.stderr)
            full_config = {"empresa": {}, "ventas": {}}
        except Exception as e:
            print(f"[ventas/sales_chat] Error cargando config: {type(e).__name__}: {e}", file=sys.stderr)
            full_config = {"empresa": {}, "ventas": {}}

        empresa_full = full_config.get("empresa") or {}

        # Airtable (Config_Empresa) gana; el body es fallback transitorio.
        config = {
            "empresa": {
                "id":               empresa_id,
                "name":             empresa_full.get("name") or (body.get("name") or "").strip(),
                "razon_social":     empresa_full.get("razon_social") or (body.get("razon_social") or "").strip(),
                "ruc":              empresa_full.get("ruc") or (body.get("ruc") or "").strip(),
                "sistema_contable": empresa_full.get("sistema_contable") or (body.get("sistema_contable") or "").strip(),
                "info_extendida":   empresa_full.get("info_extendida", {}),
            },
            "ventas": full_config.get("ventas", {}),
        }

        try:
            system = ventas_prompt.build_prompt(
                config,
                ctx={"productos": productos, "sender": sender},
            )
        except Exception as e:
            print(f"[ventas/sales_chat] Error armando prompt: {type(e).__name__}: {e}", file=sys.stderr)
            return req._json(500, {"error": "Error interno armando prompt."})

        try:
            result = openai_client.run_chat(
                system_prompt=system,
                messages=history,
                tools=ventas_tools.TOOLS_OPENAI,
                context={
                    "empresa_id": empresa_id,
                    "sender":     sender,
                    # `enviar_catalogo` lo lee de acá en vez de re-consultar
                    # Airtable: la config ya se cargó arriba con load_full_config.
                    "ventas":     config.get("ventas") or {},
                },
                executor=ventas_tools.execute,
                max_iterations=4,
            )
        except OpenAIAPIError as e:
            print(f"[ventas/sales_chat] OpenAI API error: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error del servicio IA."})
        except AirtableError as e:
            print(f"[ventas/sales_chat] AirtableError run_chat: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error consultando catálogo."})

        reply = (result.get("text") or "").strip()
        if not reply:
            reply = "Disculpa, no entendí bien tu mensaje. ¿Podrías repetirlo?"

        return req._json(200, {"reply": reply})
    except Exception as e:
        print(f"[ventas/sales_chat] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error interno del servidor."})
