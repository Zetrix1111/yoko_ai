"""
ventas/chat.py — cerebro del agente de ventas.

Dos consumidores:
  1. `sales_chat_post(req)` — wrapper HTTP que invoca bot-baileys
     (S2S, sin JWT). POST /api/ventas?resource=sales_chat.
     Recibe `{empresa_id, phone, nombre, history}` y devuelve `{reply}`.
     bot-baileys ignora `media_urls` (no las entiende), por eso solo
     devolvemos texto.
  2. `meta_webhook_post(req)` (`_ventas.meta_webhook`) — para empresas
     en canal Meta Cloud API. Invoca `process_message(...)` directo
     en proceso y manda fotos + texto via WhatsApp Cloud API.

La lógica core (cargar productos + config + armar prompt + correr LLM)
vive en `process_message()` — función pura sin `req`. Ambos handlers
la reusan.
"""

import os
import sys

from _lib import config_loader, openai_client
from _lib.airtable_client import AirtableError
from _ventas._lib import history_loader
from _ventas._lib import prompt as ventas_prompt
from _ventas._lib import tools as ventas_tools

try:
    from openai import APIError as OpenAIAPIError
except ImportError:
    OpenAIAPIError = Exception  # type: ignore[assignment, misc]


_REQUIRED_ENV = ("OPENAI_API_KEY", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")


def process_message(
    empresa_id: str,
    phone: str,
    nombre: str,
    history: list[dict],
    channel: str = "baileys",
) -> dict:
    """
    Lógica core del cerebro de ventas. Función pura: no toca request HTTP.

    Carga catálogo + config + arma prompt + corre LLM con tools de
    ventas. Reusa `history_loader` para reconstruir el historial desde
    Airtable (cap server-side 50, evita el cap=20 de bot-baileys).

    Args:
      empresa_id: tenant.
      phone:      número WhatsApp del cliente (sin formato específico).
      nombre:     pushname del cliente (puede estar vacío).
      history:    history del caller (body de Baileys o último mensaje
                  del webhook Meta). Sirve como fallback + merge con
                  Airtable.
      channel:    "meta" si la request entró por Meta Cloud API (soporta
                  imágenes nativas), "baileys" si por bot-baileys (solo
                  texto). Define si el prompt anuncia
                  `enviar_fotos_productos` al LLM y si la tool acepta
                  invocaciones. Default "baileys" por compat.

    Returns:
      {
        "reply":      str (texto al cliente, nunca vacío),
        "media_urls": list[str] (URLs de imágenes a enviar antes del texto),
        "action":     dict | None (acción de navegación, raro en ventas),
      }

    Puede levantar AirtableError (config/productos inaccesibles) o
    OpenAIAPIError (LLM down). El caller decide cómo propagar.
    """
    # Reconstruir history desde Airtable (cap server-side 50).
    airtable_history = history_loader.load_history(empresa_id, phone)
    if airtable_history is not None:
        history = history_loader.merge_with_latest_user_message(
            airtable_history, history,
        )

    sender = {"phone": phone, "nombre": nombre}

    # Catálogo (para listar en prompt + decidir si anunciar tool fotos).
    productos_result = ventas_tools.consultar_productos(
        {"solo_disponibles": False},
        {"empresa_id": empresa_id},
    )
    productos = productos_result.get("productos", [])

    # Config de la empresa. Si Airtable falla, seguimos con dict mínimo —
    # el agente puede responder igual, solo sin bloques opcionales.
    try:
        full_config = config_loader.load_full_config(empresa_id)
    except AirtableError as e:
        print(f"[ventas/process_message] Config dinámica no disponible: {e}", file=sys.stderr)
        full_config = {"empresa": {}, "ventas": {}}
    except Exception as e:
        print(
            f"[ventas/process_message] Error cargando config: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        full_config = {"empresa": {}, "ventas": {}}

    empresa_full = full_config.get("empresa") or {}
    config = {
        "empresa": {
            "id":               empresa_id,
            "name":             empresa_full.get("name") or "",
            "razon_social":     empresa_full.get("razon_social") or "",
            "ruc":              empresa_full.get("ruc") or "",
            "sistema_contable": empresa_full.get("sistema_contable") or "",
            "info_extendida":   empresa_full.get("info_extendida", {}),
        },
        "ventas": full_config.get("ventas", {}),
    }

    system = ventas_prompt.build_prompt(
        config,
        ctx={
            "productos":  productos,
            "sender":     sender,
            "empresa_id": empresa_id,
            "channel":    channel,
        },
    )

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
            # `enviar_fotos_productos` revisa este flag para rechazar
            # si el canal no soporta imágenes nativas (defensa en
            # profundidad por si el LLM la invoca aunque no esté en el
            # prompt).
            "channel":    channel,
        },
        executor=ventas_tools.execute,
        max_iterations=4,
    )

    reply = (result.get("text") or "").strip()
    if not reply:
        reply = "Disculpa, no entendí bien tu mensaje. ¿Podrías repetirlo?"

    return {
        "reply":      reply,
        "media_urls": result.get("media_urls") or [],
        "action":     result.get("action"),
    }


def sales_chat_post(req) -> None:
    """
    Endpoint HTTP S2S invocado por bot-baileys (canal legacy).
    Devuelve solo `{reply}` — bot-baileys no entiende `media_urls`.
    """
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

        phone = (body.get("phone") or "").strip()
        nombre = (body.get("nombre") or "").strip()

        try:
            result = process_message(
                empresa_id, phone, nombre, history,
                channel="baileys",
            )
        except OpenAIAPIError as e:
            print(f"[ventas/sales_chat] OpenAI API error: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error del servicio IA."})
        except AirtableError as e:
            print(f"[ventas/sales_chat] AirtableError: {e}", file=sys.stderr)
            return req._json(502, {"error": "Error consultando catálogo."})

        # bot-baileys NO entiende `media_urls` — solo devolvemos texto.
        # El field se mantiene en la response solo si el caller es el
        # webhook Meta (que llama a process_message directo).
        return req._json(200, {"reply": result["reply"]})

    except Exception as e:
        print(f"[ventas/sales_chat] Error inesperado: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error interno del servidor."})
