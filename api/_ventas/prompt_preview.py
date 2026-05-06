"""
ventas/prompt_preview.py — handler GET para /api/ventas?resource=prompt_preview

Devuelve el system prompt que el agente de ventas usaría AHORA con la config
actual del tenant. Sirve para que el cliente vea, desde la UI del wizard,
cómo queda el prompt resultante de sus elecciones — sin necesidad de mandar
un mensaje real al bot de WhatsApp.

El endpoint usa los mismos componentes que `chat.sales_chat_post`:
  - Carga productos del catálogo del tenant.
  - Carga `Config_Empresa` + `Config_Ventas` desde Airtable.
  - Llama a `_ventas._lib.prompt.build_prompt(config, ctx)`.

Pero NO toca OpenAI ni descarga conversaciones reales. Es read-only.

Requiere JWT: solo el dueño del tenant puede ver su propio prompt
(el dispatcher de api/ventas.py valida el token y pasa empresa_id).

Response shape:
    GET /api/ventas?resource=prompt_preview&empresa_id=<id>
    → 200 { prompt: "<string>", char_count: N, estimated_tokens: M }
"""

import sys

from _lib import config_loader
from _lib.airtable_client import AirtableError
from _ventas._lib import prompt as ventas_prompt
from _ventas._lib import tools as ventas_tools


# Sender ficticio para el preview (no se persiste, no se usa para auth).
_PREVIEW_SENDER = {"phone": "+51999999999", "nombre": "Cliente Demo"}


def prompt_preview_get(req, empresa_id: str) -> None:
    """
    Recibe (req, empresa_id) — empresa_id ya validado por el dispatcher.
    El query param `?empresa_id=` se ignora (el JWT manda).
    """
    # 1) Catálogo de productos
    try:
        productos_result = ventas_tools.consultar_productos(
            {"solo_disponibles": False},
            {"empresa_id": empresa_id},
        )
    except AirtableError as e:
        print(f"[ventas/prompt_preview] Airtable productos: {e}", file=sys.stderr)
        return req._json(502, {"error": "No se pudo cargar el catálogo."})

    productos = productos_result.get("productos", [])

    # 2) Config_Empresa + Config_Ventas — si Airtable falla, seguimos con
    # un dict mínimo. El prompt se construye igual con sus defaults.
    try:
        full_config = config_loader.load_full_config(empresa_id)
    except AirtableError as e:
        print(f"[ventas/prompt_preview] Config no disponible: {e}", file=sys.stderr)
        full_config = {"empresa": {}, "ventas": {}}
    except Exception as e:
        print(f"[ventas/prompt_preview] Error cargando config: {type(e).__name__}: {e}", file=sys.stderr)
        full_config = {"empresa": {}, "ventas": {}}

    empresa_full = full_config.get("empresa") or {}

    config = {
        "empresa": {
            "id":              empresa_id,
            "name":            empresa_full.get("name") or "",
            "razon_social":    empresa_full.get("razon_social") or "",
            "ruc":             empresa_full.get("ruc") or "",
            "info_extendida":  empresa_full.get("info_extendida", {}),
        },
        "ventas": full_config.get("ventas", {}),
    }

    # 3) Construir el prompt
    try:
        prompt_text = ventas_prompt.build_prompt(
            config,
            ctx={"productos": productos, "sender": _PREVIEW_SENDER},
        )
    except Exception as e:
        print(f"[ventas/prompt_preview] Error armando prompt: {type(e).__name__}: {e}", file=sys.stderr)
        return req._json(500, {"error": "Error interno armando el prompt."})

    char_count = len(prompt_text)
    # Heurística simple: 1 token ≈ 4 chars. Suficiente para mostrar al usuario.
    estimated_tokens = char_count // 4

    return req._json(200, {
        "prompt":           prompt_text,
        "char_count":       char_count,
        "estimated_tokens": estimated_tokens,
    })
